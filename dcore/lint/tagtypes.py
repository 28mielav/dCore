"""Type-check Denizen tag chains against the selected Meta snapshot.

The linter could already say "this command does not exist", but never "this
tag chain does not typecheck", even though the Meta carries everything needed:
every one of the ~3400 tag entries records an `attribute` (`<EntityTag.location>`)
and a `returns` (`LocationTag`), and every object type records its `base`
(PlayerTag -> EntityTag) and its root tag name (`player`).

That is enough to walk `<player.name.lore>` step by step: `player` resolves to
PlayerTag, `.name` returns ElementTag, and ElementTag has no `lore`, so the
chain is wrong before the server ever loads it.

The checker is deliberately fail-open. Any unknown root, unknown attribute
owner, dynamic segment or unresolved parameter stops the walk silently rather
than guessing, because a false "this tag is invalid" is far more expensive to
the user than a missed one.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

#: `<EntityTag.collides_at[<location>]>` -> owner EntityTag, attribute collides_at
ATTRIBUTE_PATTERN = re.compile(r"^<([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z0-9_]+)")
#: `ElementTag(Boolean)` and `ListTag(ItemTag)` both resolve to their outer type.
RETURN_PATTERN = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)")

#: Roots that are namespaces rather than object types. They own attributes but
#: are never the result of a tag, so they may only appear first in a chain.
NAMESPACE_ROOTS = frozenset({"server", "util", "context", "queue", "script", "player", "npc"})

#: Segments that end a walk because their result is not statically known.
DYNAMIC_SEGMENT = re.compile(r"^(?:<|\[)")

#: Types that carry no useful attribute surface of their own. A tag returning
#: one of these says "some object", so the walk must stop instead of demanding
#: that the next attribute exist on the placeholder. `<server.flag[x].keys>` is
#: valid even though `keys` is a MapTag attribute and `flag` returns ObjectTag.
OPAQUE_RETURNS = frozenset({
    "objecttag", "flaggableobject", "customobjecttag", "none", "",
    # ElementTag is Denizen's universal scalar and accepts a very wide surface in
    # practice; treating it as authoritative produced false positives on known-good
    # production script (`<player.location.yaw.simple>`, `<player.exists.not>`).
    "elementtag",
})


@dataclass
class TagTypeIndex:
    """Attribute ownership and return types for one resolved Meta snapshot."""

    #: (owner_type_lower, attribute_lower) -> return type
    attributes: dict[tuple[str, str], str] = field(default_factory=dict)
    #: type_lower -> base type (PlayerTag -> EntityTag)
    bases: dict[str, str] = field(default_factory=dict)
    #: type_lower -> interfaces it implements (PlayerTag -> FlaggableObject),
    #: which own real attributes: `flag`/`has_flag` live on FlaggableObject, not
    #: on any concrete type, so ignoring these invented false positives.
    interfaces: dict[str, tuple[str, ...]] = field(default_factory=dict)
    #: root tag name (player) -> object type (PlayerTag)
    roots: dict[str, str] = field(default_factory=dict)
    #: every known object type, so an unknown owner can fail open
    known_types: set[str] = field(default_factory=set)
    #: (owner_type_lower, attribute_lower) -> the deprecation notice Meta records.
    #: Meta already names the replacement ("use 'aggressive'"), which is exactly
    #: the advice a user wants, so it is passed through verbatim.
    deprecations: dict[tuple[str, str], str] = field(default_factory=dict)

    def available(self) -> bool:
        return bool(self.attributes)

    def ancestry(self, type_name: str) -> list[str]:
        """The type and its bases, nearest first, guarding against cycles."""
        chain: list[str] = []
        pending = [type_name.casefold()]
        while pending:
            current = pending.pop(0)
            if not current or current in chain:
                continue
            chain.append(current)
            base = self.bases.get(current, "")
            if base:
                pending.append(base)
            pending.extend(self.interfaces.get(current, ()))
        # Every Denizen object is an ObjectTag, and attributes like `exists` are
        # only recorded there. Without this the universal surface looks missing
        # from every concrete type.
        if "objecttag" not in chain:
            chain.append("objecttag")
        return chain

    def attribute_owner(self, type_name: str, attribute: str) -> str | None:
        for candidate in self.ancestry(type_name):
            key = (candidate, attribute.casefold())
            if key in self.attributes:
                return candidate
        return None

    def returns(self, type_name: str, attribute: str) -> str | None:
        owner = self.attribute_owner(type_name, attribute)
        if owner is None:
            return None
        return self.attributes[(owner, attribute.casefold())]

    def deprecation(self, type_name: str, attribute: str) -> str | None:
        """The deprecation notice for this attribute, if Meta records one."""
        owner = self.attribute_owner(type_name, attribute)
        if owner is None:
            return None
        return self.deprecations.get((owner, attribute.casefold()))

    def knows_attribute(self, attribute: str) -> bool:
        """Whether any indexed type owns this attribute name at all."""
        needle = attribute.casefold()
        return any(name == needle for _, name in self.attributes)

    def describes(self, type_name: str) -> bool:
        """Whether the snapshot describes this type well enough to reject a chain.

        A type with no indexed attributes anywhere in its ancestry says nothing
        about what is valid on it, so the walk must stop instead of reporting.
        """
        owners = {owner for owner, _ in self.attributes}
        return any(candidate in owners for candidate in self.ancestry(type_name))


@dataclass(frozen=True)
class TypeFault:
    """A chain step whose attribute does not exist on the incoming type."""

    chain: str
    segment: str
    owner_type: str


@dataclass(frozen=True)
class DeprecatedStep:
    """A chain step that resolves, but whose attribute Meta marks deprecated."""

    chain: str
    segment: str
    owner_type: str
    notice: str


TAG_IN_TEXT = re.compile(r"<(?P<body>[A-Za-z_][A-Za-z0-9_]*(?:\.[^<>]*?)?)>")


def split_segments(body: str) -> list[str] | None:
    """Split a tag body on top-level dots, or None when it is not statically walkable."""
    segments: list[str] = []
    depth = 0
    current = ""
    for character in body:
        if character in "[(":
            depth += 1
        elif character in "])":
            depth -= 1
            if depth < 0:
                return None
        if character == "." and depth == 0:
            segments.append(current)
            current = ""
            continue
        current += character
    if depth != 0:
        return None
    segments.append(current)
    return [segment for segment in segments if segment]


def check_chain(index: TagTypeIndex, body: str) -> TypeFault | None:
    """Walk one tag body and return the first step that cannot typecheck.

    Fails open at every point where the snapshot stops being authoritative:
    an unknown root, an undescribed type, a dynamic segment or a fallback all
    end the walk without a finding.
    """
    if not index.available():
        return None
    segments = split_segments(body)
    if not segments or len(segments) < 2:
        return None
    if "||" in body:
        # A fallback means the author already accepts the chain may not resolve.
        return None

    root = segments[0].casefold()
    if DYNAMIC_SEGMENT.match(segments[0]) or "[" in segments[0]:
        return None
    current = index.roots.get(root)
    if current is None:
        if root in index.known_types:
            current = segments[0]
        else:
            return None

    for segment in segments[1:]:
        if DYNAMIC_SEGMENT.match(segment):
            return None
        attribute = segment.split("[", 1)[0].strip()
        if not attribute or not re.fullmatch(r"[A-Za-z0-9_]+", attribute):
            return None
        if current.casefold() in OPAQUE_RETURNS or not index.describes(current):
            return None
        returns = index.returns(current, attribute)
        if returns is None:
            # Only report when the snapshot knows this attribute on some other
            # type. An attribute it has never heard of is far more likely an
            # unindexed addon tag than a real mistake, and guessing there
            # produced false positives across the whole reference corpus.
            if not index.knows_attribute(attribute):
                return None
            return TypeFault(body, attribute, current)
        current = returns
    return None


def deprecated_steps(index: TagTypeIndex, body: str) -> list[DeprecatedStep]:
    """Every resolvable step in this chain that Meta marks deprecated.

    Unlike check_chain this reports on steps that are perfectly valid today, so
    it keeps walking past the first hit: a chain can touch more than one
    deprecated attribute and the user wants all of them.
    """
    if not index.available():
        return []
    segments = split_segments(body)
    if not segments or len(segments) < 2:
        return []
    root = segments[0].casefold()
    if DYNAMIC_SEGMENT.match(segments[0]) or "[" in segments[0]:
        return []
    current = index.roots.get(root)
    if current is None:
        if root not in index.known_types:
            return []
        current = segments[0]

    found: list[DeprecatedStep] = []
    for segment in segments[1:]:
        if DYNAMIC_SEGMENT.match(segment):
            break
        attribute = segment.split("[", 1)[0].strip()
        if not attribute or not re.fullmatch(r"[A-Za-z0-9_]+", attribute):
            break
        if current.casefold() in OPAQUE_RETURNS:
            break
        notice = index.deprecation(current, attribute)
        if notice:
            found.append(DeprecatedStep(body, attribute, current, notice.strip()))
        returns = index.returns(current, attribute)
        if returns is None:
            break
        current = returns
    return found


def deprecations_in_text(index: TagTypeIndex, text: str) -> list[DeprecatedStep]:
    """Every deprecated tag step in one line of script text."""
    found: list[DeprecatedStep] = []
    for match in TAG_IN_TEXT.finditer(text):
        found.extend(deprecated_steps(index, match.group("body")))
    return found


def faults_in_text(index: TagTypeIndex, text: str) -> list[TypeFault]:
    """Every type fault in one line of script text."""
    found: list[TypeFault] = []
    for match in TAG_IN_TEXT.finditer(text):
        fault = check_chain(index, match.group("body"))
        if fault is not None:
            found.append(fault)
    return found


def _clean_return(value: str) -> str:
    match = RETURN_PATTERN.match(value.strip())
    return match.group(1) if match else ""


def build_index(db_path: Path | None, source_ids: set[str] | None = None) -> TagTypeIndex:
    """Index tag attributes and object-type bases from the Meta snapshot.

    `source_ids` scopes the index to the same effective sources the rest of the
    linter resolved, so a historical target cannot borrow current tag types.
    """
    index = TagTypeIndex()
    if not db_path or not Path(db_path).is_file():
        return index
    with sqlite3.connect(db_path) as db:
        db.row_factory = sqlite3.Row
        scope = ""
        parameters: tuple[str, ...] = ()
        if source_ids:
            marks = ",".join("?" for _ in source_ids)
            scope = f" AND e.source_id IN ({marks})"
            parameters = tuple(sorted(source_ids))

        for row in db.execute(
            "SELECT a.value AS attribute, r.value AS returns, e.deprecated AS deprecated FROM meta_entries e"
            " JOIN meta_fields a ON a.entry_id=e.entry_id AND a.field_name='attribute'"
            " JOIN meta_fields r ON r.entry_id=e.entry_id AND r.field_name='returns'"
            f" WHERE e.category='tag'{scope}",
            parameters,
        ):
            match = ATTRIBUTE_PATTERN.match(str(row["attribute"] or ""))
            if not match:
                continue
            owner, attribute = match.group(1).casefold(), match.group(2).casefold()
            returns = _clean_return(str(row["returns"] or ""))
            if returns:
                index.attributes.setdefault((owner, attribute), returns)
            notice = str(row["deprecated"] or "").strip()
            if notice:
                index.deprecations.setdefault((owner, attribute), notice)

        for row in db.execute(
            "SELECT e.name AS name, e.entry_id AS entry_id FROM meta_entries e"
            f" WHERE e.category='objecttype'{scope}",
            parameters,
        ):
            name = str(row["name"] or "")
            if not name:
                continue
            index.known_types.add(name.casefold())
            for field_row in db.execute(
                "SELECT field_name,value FROM meta_fields WHERE entry_id=? AND field_name IN ('base','implements','exampletagbase')",
                (row["entry_id"],),
            ):
                value = str(field_row["value"] or "").strip()
                if not value:
                    continue
                if field_row["field_name"] == "base":
                    index.bases.setdefault(name.casefold(), _clean_return(value).casefold())
                elif field_row["field_name"] == "implements":
                    existing_interfaces = index.interfaces.get(name.casefold(), ())
                    added = tuple(
                        part.casefold()
                        for part in re.split(r"[\s,|]+", value)
                        if part
                    )
                    index.interfaces[name.casefold()] = existing_interfaces + added
                else:
                    for root in re.split(r"[\s,|]+", value):
                        if not root:
                            continue
                        root = root.casefold()
                        # Several types advertise the same root: EntityTag and
                        # PlayerTag both example `player`. The most specific
                        # wins, otherwise `<player.gamemode>` looks invalid
                        # because gamemode lives on PlayerTag, not EntityTag.
                        existing = index.roots.get(root)
                        if existing is None or f"{root}tag" == name.casefold():
                            index.roots[root] = name
    return index
