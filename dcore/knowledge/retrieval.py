from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

from dcore.knowledge.meta_resolution import effective_sources, visible
from dcore.knowledge.version_registry import normalize_product_version


INTENT_PRIORITY = (
    "full_audit", "refactor", "bugfix", "diagnose", "full_file",
    "performance_review", "visual_design", "new_mechanic", "teach",
    "quick_question",
)
MANDATORY_RELATIONS = {"requires", "requires_lifecycle", "requires_render_graph"}
DECISION_INTENTS = {
    "full_audit", "refactor", "bugfix", "full_file", "performance_review",
    "visual_design", "new_mechanic",
}


def tokens(text: str) -> list[str]:
    return re.findall(r"[\w]+", text.lower(), flags=re.UNICODE)


def matches(text: str, pattern: str) -> bool:
    source = tokens(text)
    wanted = re.findall(r"[\w]+\*?", pattern.lower(), flags=re.UNICODE)
    if not wanted or len(wanted) > len(source):
        return False
    for start in range(len(source) - len(wanted) + 1):
        if all(
            source[start + offset].startswith(part[:-1])
            if part.endswith("*")
            else source[start + offset] == part
            for offset, part in enumerate(wanted)
        ):
            return True
    return False


def classify_intent(db: sqlite3.Connection, query: str) -> tuple[str, dict[str, int]]:
    """Classify locally so callers do not have to guess the router intent."""
    known = {row[0] for row in db.execute("SELECT intent FROM router_rules")}
    scores = {intent: 0 for intent in known}
    for intent, term, weight in db.execute("SELECT intent,term,weight FROM intent_terms"):
        if matches(query, term):
            scores[intent] += weight

    lowered = query.lower()
    # Stable fallback signals also cover databases created before intent_terms.
    signals = {
        "full_audit": (("аудит", "проанализируй всё", "full audit"), 8),
        "refactor": (("рефактор", "перепиши архитектуру", "rewrite"), 7),
        "bugfix": (("почини", "исправь", "fix", "patch"), 6),
        "diagnose": (("почему", "не работает", "ошибка", "error", "console"), 5),
        "full_file": (("полный файл", "готовый файл", "production file"), 6),
        "performance_review": (("лаг", "нагруз", "hot path", "tick loop"), 5),
        "visual_design": (("shader", "шейдер", "item_display", "block_display", "resource pack", "портал"), 4),
        "new_mechanic": (("сделай механику", "новая механика", "design"), 3),
        "teach": (("объясни", "научи", "как устроено"), 4),
        "quick_question": (("синтаксис", "какой тег", "какая команда"), 3),
    }
    for intent, (phrases, weight) in signals.items():
        if intent in scores and any(phrase in lowered for phrase in phrases):
            scores[intent] += weight
    if not any(scores.values()):
        fallback = "new_mechanic" if "new_mechanic" in known else sorted(known)[0]
        return fallback, scores
    order = {intent: index for index, intent in enumerate(INTENT_PRIORITY)}
    chosen = max(scores, key=lambda intent: (scores[intent], -order.get(intent, 999)))
    return chosen, scores


def activation_match(db: sqlite3.Connection, card_id: str, query: str) -> bool | None:
    rule = db.execute(
        "SELECT min_hits FROM card_activation_rules WHERE card_id=?", (card_id,)
    ).fetchone()
    if not rule:
        return None
    hits = sum(
        matches(query, row[0])
        for row in db.execute(
            "SELECT term FROM card_activation_terms WHERE card_id=?", (card_id,)
        )
    )
    return hits >= rule[0]


def eligible(db: sqlite3.Connection, card_id: str, query: str) -> bool:
    result = activation_match(db, card_id, query)
    return True if result is None else result


def alias_rank(db: sqlite3.Connection, query: str, domains: list[str]) -> list[tuple]:
    if not domains:
        return []
    scores: dict[str, list] = {}
    marks = ",".join("?" * len(domains))
    rows = db.execute(
        f"""SELECT a.card_id,a.term,a.weight,c.priority,c.token_weight,c.domain
            FROM card_alias_terms a JOIN cards c ON c.id=a.card_id
            WHERE c.domain IN ({marks})""",
        domains,
    )
    for row in rows:
        if matches(query, row["term"]):
            score = scores.setdefault(
                row["card_id"],
                [0, row["priority"], row["token_weight"], row["domain"]],
            )
            score[0] += row["weight"]
    return sorted(
        ((card_id, *values) for card_id, values in scores.items()),
        key=lambda row: (-row[1], -row[2], row[3], row[0]),
    )


def fts(db: sqlite3.Connection, query: str, domains: list[str]) -> list[sqlite3.Row]:
    words = list(dict.fromkeys(tokens(query)))
    if not words or not domains:
        return []
    expression = " OR ".join(f'"{word}"' for word in words)
    marks = ",".join("?" * len(domains))
    return db.execute(
        f"""SELECT s.id,bm25(card_search) score,c.priority,c.token_weight,c.domain
            FROM card_search s JOIN cards c ON c.id=s.id
            WHERE card_search MATCH ? AND c.domain IN ({marks})
            ORDER BY score,c.priority DESC,c.token_weight ASC LIMIT 100""",
        [expression, *domains],
    ).fetchall()


def route(db: sqlite3.Connection, query: str, intent: str = "auto") -> tuple[list[str], list[str]]:
    db.row_factory = sqlite3.Row
    if intent == "auto":
        intent, _ = classify_intent(db, query)
    rule = db.execute(
        "SELECT max_cards FROM router_rules WHERE intent=?", (intent,)
    ).fetchone()
    if not rule:
        raise ValueError(f"unknown retrieval intent: {intent}")
    complex_request = len(tokens(query)) >= 28 or query.count("\n") >= 3
    policy_room = 0 if intent in {"quick_question", "teach"} else 2
    max_cards = min(14, max(rule[0] + policy_room, 10 if complex_request else rule[0]))
    rows = db.execute(
        "SELECT domain,required FROM route_domains WHERE intent=? "
        "ORDER BY required DESC,domain",
        (intent,),
    ).fetchall()
    active = [row["domain"] for row in rows if row["required"]]
    for row in rows:
        if row["required"]:
            continue
        domain_hit = any(
            matches(query, term[0])
            for term in db.execute(
                "SELECT term FROM domain_terms WHERE domain=?", (row["domain"],)
            )
        )
        if domain_hit:
            active.append(row["domain"])

    # Exact domain and activation terms may activate a domain that was not an
    # optional member of the primary intent. This is how multi-capability
    # requests retain shader/math/addon evidence without preloading everything.
    for domain, in db.execute("SELECT key FROM domains ORDER BY key"):
        if domain in active:
            continue
        if any(matches(query, term[0]) for term in db.execute(
            "SELECT term FROM domain_terms WHERE domain=?", (domain,)
        )):
            active.append(domain)
    activated: list[str] = []
    for card_id, in db.execute("SELECT card_id FROM card_activation_rules ORDER BY card_id"):
        if activation_match(db, card_id, query):
            activated.append(card_id)
            domain = db.execute("SELECT domain FROM cards WHERE id=?", (card_id,)).fetchone()
            if domain and domain[0] not in active:
                active.append(domain[0])

    selected: list[str] = []

    def add(card_id: str, *, dependency: bool = False) -> None:
        if card_id in selected or len(selected) >= 14:
            return
        row = db.execute("SELECT domain FROM cards WHERE id=?", (card_id,)).fetchone()
        if not row:
            return
        if dependency and row[0] not in active:
            active.append(row[0])
        if len(selected) >= max_cards and not dependency:
            return
        if (dependency or eligible(db, card_id, query)) and row[0] in active:
            selected.append(card_id)

    # Task-specific exact activations go before generic policy pins.
    for card_id in activated:
        add(card_id)
    for row in db.execute(
        "SELECT card_id FROM route_pins WHERE intent=? ORDER BY position", (intent,)
    ):
        add(row[0], dependency=True)

    ranked_aliases = alias_rank(db, query, active)
    for domain in active:
        if any(
            db.execute("SELECT domain FROM cards WHERE id=?", (card,)).fetchone()[0]
            == domain
            for card in selected
        ):
            continue
        candidate = next(
            (row[0] for row in ranked_aliases if row[4] == domain and eligible(db, row[0], query)),
            None,
        )
        if not candidate:
            candidate = next(
                (row["id"] for row in fts(db, query, [domain]) if eligible(db, row["id"], query)),
                None,
            )
        if candidate:
            add(candidate)
            continue
        fallback = db.execute(
            "SELECT card_id FROM domain_pins WHERE domain=?", (domain,)
        ).fetchone()
        if fallback:
            add(fallback[0])
    for row in ranked_aliases:
        add(row[0])
    fill_target = max_cards
    for row in fts(db, query, active):
        if len(selected) >= fill_target:
            break
        add(row["id"])

    # Required links are dependency closure, not optional ranking hints.
    link_columns = {row[1] for row in db.execute("PRAGMA table_info(card_links)")}
    frontier = list(selected)
    seen = set(frontier)
    while frontier and len(selected) < 14:
        source = frontier.pop(0)
        if "mandatory" in link_columns:
            links = db.execute(
                "SELECT to_id FROM card_links WHERE from_id=? AND mandatory=1 ORDER BY to_id",
                (source,),
            )
        else:
            marks = ",".join("?" for _ in MANDATORY_RELATIONS)
            links = db.execute(
                f"SELECT to_id FROM card_links WHERE from_id=? AND relation IN ({marks}) ORDER BY to_id",
                (source, *sorted(MANDATORY_RELATIONS)),
            )
        for linked in links:
            target = linked[0]
            add(target, dependency=True)
            if target in selected and target not in seen:
                seen.add(target)
                frontier.append(target)
    return active, selected


def run_tests(db: sqlite3.Connection, ids: set[str] | None = None) -> list[dict]:
    db.row_factory = sqlite3.Row
    failures = []
    for test in db.execute("SELECT * FROM retrieval_tests ORDER BY id"):
        if ids and test["id"] not in ids:
            continue
        routed_intent = test["intent"]
        intent_mismatch = False
        if test["id"].startswith("AUTO"):
            routed_intent, _ = classify_intent(db, test["query"])
            intent_mismatch = routed_intent != test["intent"]
        domains, cards = route(db, test["query"], routed_intent)
        card_domains = {
            db.execute("SELECT domain FROM cards WHERE id=?", (card,)).fetchone()[0]
            for card in cards
        }
        split = lambda value: set(filter(None, (value or "").split(",")))
        expected_domains = split(test["expected_domains"])
        forbidden_domains = split(test["forbidden_domains"])
        expected_cards = split(test["expected_cards"])
        forbidden_cards = split(test["forbidden_cards"])
        ok = (
            not intent_mismatch
            and
            expected_domains <= card_domains
            and not forbidden_domains.intersection(card_domains)
            and expected_cards <= set(cards)
            and not forbidden_cards.intersection(cards)
        )
        if not ok:
            failures.append(
                {
                    "id": test["id"],
                    "query": test["query"],
                    "expected_intent": test["intent"],
                    "routed_intent": routed_intent,
                    "active_domains": domains,
                    "selected_cards": cards,
                    "missing_cards": sorted(expected_cards - set(cards)),
                    "forbidden_cards": sorted(forbidden_cards.intersection(cards)),
                    "missing_domains": sorted(expected_domains - card_domains),
                    "forbidden_domains": sorted(forbidden_domains.intersection(card_domains)),
                }
            )
    return failures


def card_applicability(
    db: sqlite3.Connection, card_ids: list[str], target: dict[str, str], addons: tuple[str, ...]
) -> dict[str, dict]:
    """Turn card scopes into an explicit gate, never an implicit text caveat."""
    if not card_ids or not table_exists(db, "card_version_scopes"):
        return {}
    declared = {
        item.partition("@")[0].strip().casefold(): item.partition("@")[2].strip()
        for item in addons if item.strip()
    }
    marks = ",".join("?" for _ in card_ids)
    rows = db.execute(
        f"SELECT * FROM card_version_scopes WHERE card_id IN ({marks})", card_ids
    ).fetchall()
    output = {}
    for row in rows:
        item = dict(row)
        scope = item["scope_type"]
        if scope == "invariant":
            status, reason = "applicable", "Version-neutral invariant."
        elif scope == "minecraft_target":
            status, reason = ("applicable_target_pinned", "Minecraft target is declared.") if target.get("minecraft") else ("target_required", "Declare --minecraft before using version-sensitive visual advice.")
        elif scope == "denizen_target":
            pinned = target.get("denizenm") if target.get("profile") == "denizenm" else target.get("denizen")
            status, reason = ("applicable_target_pinned", "Exact Denizen-family build is declared.") if pinned else ("target_required", "Declare --denizenm or --denizen-version before using API advice.")
        elif scope == "addon_target":
            addon = item["addon"].casefold()
            if addon and addon not in declared:
                status, reason = "not_applicable", f"This card applies only when {addon}@version is declared."
            elif addon and not declared[addon]:
                status, reason = "addon_version_required", f"Declare {addon}@version."
            elif not declared:
                status, reason = "target_required", "Declare the relevant addon@version."
            else:
                status, reason = "applicable_addon_pinned", "Addon version is declared; use compatibility evidence for the final route."
        else:
            complete = bool(target.get("minecraft")) and bool(target.get("denizenm") or target.get("denizen"))
            status, reason = ("applicable_target_matrix", "Minecraft and Denizen-family target are declared.") if complete else ("target_matrix_required", "Declare Minecraft plus Denizen/DenizenM build before applying this policy.")
        item["status"] = status
        item["reason"] = reason
        output[item["card_id"]] = item
    return output


def card_contract(db: sqlite3.Connection, card_id: str) -> dict:
    """Return the machine-readable contract the router expects for one card."""
    db.row_factory = sqlite3.Row
    row = db.execute("SELECT * FROM cards WHERE id=?", (card_id,)).fetchone()
    if not row:
        return {"card_id": card_id, "contract_complete": False, "gaps": ["card_missing"]}
    card = dict(row)
    activation_terms = [
        item[0] for item in db.execute(
            "SELECT term FROM card_activation_terms WHERE card_id=? ORDER BY term", (card_id,)
        )
    ]
    alias_terms = [
        item[0] for item in db.execute(
            "SELECT term FROM card_alias_terms WHERE card_id=? ORDER BY term", (card_id,)
        )
    ]
    card_terms = [
        item[0] for item in db.execute(
            "SELECT term FROM card_terms WHERE card_id=? ORDER BY term", (card_id,)
        )
    ]
    scopes = [dict(item) for item in db.execute(
        "SELECT * FROM card_version_scopes WHERE card_id=? ORDER BY scope_type,addon", (card_id,)
    )]
    tests = [
        test_id for test_id, expected in db.execute(
            "SELECT id,expected_cards FROM retrieval_tests ORDER BY id"
        )
        if card_id in set(filter(None, (expected or "").split(",")))
    ]
    trigger_terms = list(dict.fromkeys(activation_terms + alias_terms + card_terms))
    required = {
        "summary": card.get("summary"),
        "guidance": card.get("guidance"),
        "non_triggers": card.get("reject_when"),
        "verification": card.get("verification"),
        "version_scope": card.get("version_scope"),
        "source_basis": card.get("source_basis"),
        "trigger_terms": trigger_terms,
        "version_scope_rows": scopes,
        "retrieval_tests": tests,
    }
    gaps = []
    for field in ("summary", "guidance", "non_triggers", "verification", "version_scope", "source_basis"):
        if not str(required[field] or "").strip():
            gaps.append(field)
    if not trigger_terms:
        gaps.append("trigger_terms")
    if not scopes:
        gaps.append("version_scope_rows")
    if not tests:
        gaps.append("retrieval_tests")
    try:
        priority_rank = int(card.get("priority") or 0)
    except (TypeError, ValueError):
        priority_rank = 0
    severity = "warning" if priority_rank >= 90 else "suggestion"
    return {
        "card_id": card_id,
        "domain": card.get("domain"),
        "title": card.get("title"),
        "trigger_terms": trigger_terms,
        "non_triggers": card.get("reject_when") or "",
        "severity": severity,
        "priority_rank": priority_rank,
        "verification": card.get("verification") or "",
        "version_scope": card.get("version_scope") or "",
        "version_scope_rows": scopes,
        "runtime_boundary": "runtime proof required" if "runtime" in str(card.get("verification", "")).casefold() else "static guidance",
        "required_retrieval_tests": tests,
        "gaps": gaps,
        "contract_complete": not gaps,
    }


def card_contract_audit(
    db: sqlite3.Connection,
    card_ids: list[str] | None = None,
) -> dict:
    """Audit selected cards or the whole corpus without hiding incomplete cards."""
    ids = card_ids or [row[0] for row in db.execute("SELECT id FROM cards ORDER BY id")]
    contracts = [card_contract(db, card_id) for card_id in ids]
    incomplete = [item for item in contracts if not item["contract_complete"]]
    return {
        "status": "complete" if not incomplete else "incomplete",
        "checked": len(contracts),
        "complete": len(contracts) - len(incomplete),
        "incomplete": len(incomplete),
        "gaps": {item["card_id"]: item["gaps"] for item in incomplete},
    }


def router_trace(
    db: sqlite3.Connection,
    query: str,
    intent: str = "auto",
    target: dict[str, str] | None = None,
    addons: tuple[str, ...] = (),
) -> dict:
    """Explain every selected card and expose coverage gaps to the caller."""
    if intent == "auto":
        routed_intent, scores = classify_intent(db, query)
    else:
        routed_intent, scores = intent, {}
    active, selected = route(db, query, routed_intent)
    target = target or {}
    contracts = [card_contract(db, card_id) for card_id in selected]
    reasons: dict[str, list[str]] = {}
    pinned = {row[0] for row in db.execute(
        "SELECT card_id FROM route_pins WHERE intent=?", (routed_intent,)
    )}
    domain_pins = {row[0] for row in db.execute("SELECT card_id FROM domain_pins")}
    for card_id in selected:
        why: list[str] = []
        if activation_match(db, card_id, query):
            why.append("activation_rule")
        if card_id in pinned:
            why.append("intent_pin")
        alias_hit = any(
            matches(query, row[0]) for row in db.execute(
                "SELECT term FROM card_alias_terms WHERE card_id=?", (card_id,)
            )
        )
        if alias_hit:
            why.append("alias_match")
        card_domain = db.execute("SELECT domain FROM cards WHERE id=?", (card_id,)).fetchone()
        if card_id in domain_pins:
            why.append("domain_pin")
        if not why:
            why.append("ranked_search")
        reasons[card_id] = why
    all_domains = {row[0] for row in db.execute("SELECT key FROM domains ORDER BY key")}
    scope = card_applicability(db, selected, target, addons)
    scope_gaps = {
        card_id: item for card_id, item in scope.items()
        if item.get("status") not in {"applicable", "applicable_target_pinned", "applicable_addon_pinned", "applicable_target_matrix"}
    }
    incomplete = [item for item in contracts if not item["contract_complete"]]
    return {
        "intent": routed_intent,
        "intent_scores": scores,
        "active_domains": active,
        "excluded_domains": sorted(all_domains - set(active)),
        "selected_cards": selected,
        "selection_reasons": reasons,
        "card_contracts": contracts,
        "coverage": {
            "status": "complete" if not incomplete and not scope_gaps else "incomplete",
            "selected": len(selected),
            "contract_gaps": {item["card_id"]: item["gaps"] for item in incomplete},
            "version_scope_gaps": scope_gaps,
        },
        "required_verification": [
            {"card_id": item["card_id"], "verification": item["verification"]}
            for item in contracts if item["verification"]
        ],
    }


def card_payload(
    db: sqlite3.Connection, card_ids: list[str], target: dict[str, str] | None = None,
    addons: tuple[str, ...] = (),
) -> list[dict]:
    if not card_ids:
        return []
    db.row_factory = sqlite3.Row
    marks = ",".join("?" for _ in card_ids)
    rows = db.execute(
        f"SELECT * FROM cards WHERE id IN ({marks})", card_ids
    ).fetchall()
    by_id = {row["id"]: dict(row) for row in rows}
    scopes = card_applicability(db, card_ids, target or {}, addons)
    for card_id, scope in scopes.items():
        if card_id in by_id:
            by_id[card_id]["version_scope_structured"] = scope
    return [by_id[card_id] for card_id in card_ids if card_id in by_id]


def table_exists(db: sqlite3.Connection, name: str) -> bool:
    return db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def contrast_payload(
    db: sqlite3.Connection, query: str, domains: list[str], limit: int = 2
) -> list[dict]:
    """Return a tiny labelled good/bad pair set, never the whole corpus."""
    if limit <= 0 or not table_exists(db, "contrast_examples"):
        return []
    db.row_factory = sqlite3.Row
    query_tokens = set(tokens(query))
    scores: dict[str, int] = {}
    for row in db.execute(
        "SELECT example_id,term,weight FROM contrast_terms ORDER BY example_id,term"
    ):
        if matches(query, row["term"]):
            scores[row["example_id"]] = scores.get(row["example_id"], 0) + row["weight"] * 8
    rows = db.execute(
        "SELECT * FROM contrast_examples ORDER BY priority DESC,id"
    ).fetchall()
    ranked = []
    for row in rows:
        if row["domain"] not in domains and not (
            row["domain"] == "denizen" and "core" in domains
        ):
            continue
        searchable = " ".join(
            str(row[key]) for key in (
                "title", "diagnostic_code", "bad_reason", "invariant"
            )
        )
        overlap = len(query_tokens.intersection(tokens(searchable)))
        score = scores.get(row["id"], 0) + overlap * 2
        ranked.append((score, row["priority"], row["id"], dict(row)))
    ranked.sort(key=lambda item: (-item[0], -item[1], item[2]))
    return [item[3] for item in ranked[:limit] if item[0] > 0] or [
        item[3] for item in ranked[:1]
    ]


def route_pattern_payload(
    db: sqlite3.Connection,
    query: str,
    domains: list[str],
    selected_cards: list[str],
    limit: int = 4,
) -> list[dict]:
    """Suggest genuinely different, evidence-linked candidates for dcore_design."""
    if limit <= 0 or not table_exists(db, "route_patterns"):
        return []
    db.row_factory = sqlite3.Row
    term_scores: dict[str, int] = {}
    for row in db.execute(
        "SELECT route_id,term,weight FROM route_pattern_terms ORDER BY route_id,term"
    ):
        if matches(query, row["term"]):
            term_scores[row["route_id"]] = term_scores.get(row["route_id"], 0) + row["weight"] * 5
    selected = set(selected_cards)
    ranked = []
    for row in db.execute("SELECT * FROM route_patterns ORDER BY provider_rank DESC,id"):
        if row["domain"] not in domains and not (
            row["domain"] == "denizen" and "core" in domains
        ):
            continue
        evidence = set(json.loads(row["evidence_cards_json"]))
        score = term_scores.get(row["id"], 0) + len(evidence.intersection(selected)) * 4
        if row["domain"] in domains:
            score += 1
        item = dict(row)
        for key in ("requires_json", "forbids_json", "evidence_cards_json", "cost_json"):
            item[key.removesuffix("_json")] = json.loads(item.pop(key))
        ranked.append((score, row["provider_rank"], row["id"], item))
    ranked.sort(key=lambda item: (-item[0], -item[1], item[2]))
    return [item[3] for item in ranked[:limit]]


def resolve_meta(
    db: sqlite3.Connection,
    query: str,
    profile: str = "denizenm",
    addons: tuple[str, ...] = (),
    limit: int = 20,
    denizen_version: str | None = None,
    denizenm_version: str | None = None,
) -> dict:
    """Return target-first Meta evidence without treating fallback as native proof."""
    denizenm_version = normalize_product_version("DenizenM", denizenm_version)
    words = list(dict.fromkeys(tokens(query)))
    if not words:
        return {"resolution_order": [], "matches": []}
    products = ["DenizenM", "Denizen-Core", "Denizen"] if profile == "denizenm" else ["Denizen", "Denizen-Core"]
    normalized_addons = tuple(item.partition("@")[0].strip().lower() for item in addons)
    addon_products = {"reflect": "denizen-reflect", "voxizen": "Voxizen"}
    addon_sources = {"reflect": "denizen_reflect_public_main", "voxizen": "voxizen_public_main"}
    products.extend(addon_products[name] for name in normalized_addons if name in addon_products)
    expression = " OR ".join(f'"{word}"' for word in words)
    source_ids = []
    missing_version_meta = []
    for product, version, current_source in (
        ("DenizenM", denizenm_version, "denizenm_public_master"),
        ("Denizen", denizen_version, "denizen_official_dev"),
    ):
        if product not in products:
            continue
        if version:
            rows = db.execute(
                "SELECT m.source_id FROM version_artifacts v JOIN meta_sources m ON m.artifact_id=v.artifact_id "
                "WHERE lower(v.product)=lower(?) AND lower(v.version)=lower(?) ORDER BY m.source_id",
                (product, version),
            ).fetchall()
            if rows:
                source_ids.extend(row[0] for row in rows)
            else:
                missing_version_meta.append({"product": product, "version": version})
        else:
            source_ids.append(current_source)
    if "Denizen-Core" in products:
        source_ids.append("denizencore_official_master")
    source_ids.extend(addon_sources[name] for name in normalized_addons if name in addon_sources)
    source_ids = list(dict.fromkeys(source_ids))
    marks = ",".join("?" for _ in products)
    effective_source_ids, overlay = effective_sources(db, source_ids)
    source_marks = ",".join("?" for _ in effective_source_ids)
    ranking = "CASE p.product " + " ".join(
        f"WHEN '{product}' THEN {index}" for index, product in enumerate(products)
    ) + " ELSE 99 END"
    db.row_factory = sqlite3.Row
    rows = db.execute(
        f"""SELECT p.entry_id,p.source_id,p.product,p.category,p.name,p.object_type,p.syntax,
                   p.summary,p.deprecated,p.commit_sha,p.source_file,p.source_line,
                   bm25(meta_search) AS text_score
            FROM meta_search s JOIN meta_preferred p ON p.entry_id=s.entry_id
            WHERE meta_search MATCH ? AND p.product IN ({marks}) AND p.source_id IN ({source_marks})
            ORDER BY {ranking},text_score,p.category,p.name LIMIT ?""",
        (expression, *products, *effective_source_ids, max(limit * 12, 120)),
    ).fetchall()
    rows = [row for row in rows if visible(row, overlay)][:limit]
    entry_ids = [row["entry_id"] for row in rows]
    fields_by_entry: dict[int, list[dict[str, str]]] = {}
    if entry_ids:
        field_marks = ",".join("?" for _ in entry_ids)
        for entry_id, name, value in db.execute(
            f"SELECT entry_id,field_name,value FROM meta_fields "
            f"WHERE entry_id IN ({field_marks}) ORDER BY entry_id,field_name,ordinal",
            entry_ids,
        ):
            fields_by_entry.setdefault(entry_id, []).append({"name": name, "value": value})
    output = []
    for row in rows:
        item = dict(row)
        item["fields"] = fields_by_entry.get(row["entry_id"], [])
        output.append(item)
    return {
        "resolution_order": products,
        "source_scope": source_ids,
        "missing_version_meta": missing_version_meta,
        "matches": output,
    }


def version_key(value: str) -> tuple[tuple[int, object], ...]:
    """Natural comparison for Minecraft and addon version components."""
    return tuple((0, int(part)) if part.isdigit() else (1, part.casefold()) for part in re.split(r"[._+\-]", value) if part)


def compatibility_advice(
    db: sqlite3.Connection, addons: tuple[str, ...], minecraft: str | None, paper: str | None
) -> list[dict]:
    if not table_exists(db, "compatibility_rules"):
        return []
    db.row_factory = sqlite3.Row
    answers = []
    for declaration in addons:
        subject, separator, release = declaration.partition("@")
        subject = subject.strip().casefold()
        if not separator or not release.strip():
            answers.append({"addon": subject, "status": "version_unpinned", "message": "Declare addon@version for compatibility advice."})
            continue
        rules = [dict(row) for row in db.execute(
            "SELECT * FROM compatibility_rules WHERE lower(subject)=? AND lower(release_family)=? ORDER BY rule_id",
            (subject, release.strip().casefold()),
        ).fetchall()]
        if not rules:
            answers.append({"addon": subject, "release": release.strip(), "status": "no_recorded_rule", "message": "No compatibility record: require the exact JAR and focused runtime probe."})
            continue
        matches = []
        for rule in rules:
            if minecraft and rule["minecraft_min"] and version_key(minecraft) < version_key(rule["minecraft_min"]):
                continue
            if minecraft and rule["minecraft_max"] and version_key(minecraft) > version_key(rule["minecraft_max"]):
                continue
            if paper and rule["paper_min"] and version_key(paper) < version_key(rule["paper_min"]):
                continue
            if paper and rule["paper_max"] and version_key(paper) > version_key(rule["paper_max"]):
                continue
            matches.append(rule)
        answers.append({
            "addon": subject, "release": release.strip(),
            "status": matches[0]["status"] if matches else "target_outside_recorded_range",
            "rules": matches or rules,
        })
    return answers


def target_context(
    db: sqlite3.Connection,
    profile: str,
    denizen_version: str | None = None,
    denizenm_version: str | None = None,
    minecraft: str | None = None,
    paper: str | None = None,
    java: str | None = None,
) -> dict:
    """Describe the requested build and expose version proof status."""
    denizenm_version = normalize_product_version("DenizenM", denizenm_version)
    target = {
        "profile": profile,
        "denizen_version": denizen_version,
        "denizenm_version": denizenm_version,
        "minecraft": minecraft,
        "paper": paper,
        "java": java,
    }
    target = {key: value for key, value in target.items() if value not in (None, "")}
    if not table_exists(db, "version_artifacts"):
        return {"target": target, "version_proof": "registry_missing", "artifacts": []}
    requested = []
    if denizen_version:
        requested.append(("Denizen", denizen_version))
    if denizenm_version:
        requested.append(("DenizenM", denizenm_version))
    artifacts = []
    db.row_factory = sqlite3.Row
    for product, version in requested:
        rows = db.execute(
            "SELECT artifact_id,product,version,repository,tag,commit_sha,channel,"
            "status,meta_status,runtime_status FROM version_artifacts "
            "WHERE lower(product)=lower(?) AND lower(version)=lower(?) "
            "ORDER BY channel,artifact_id",
            (product, version),
        ).fetchall()
        artifacts.extend(dict(row) for row in rows)
    if not requested:
        proof = "target_unpinned"
    elif not artifacts:
        proof = "version_not_catalogued"
    elif any(item["runtime_status"] == "verified" for item in artifacts):
        proof = "runtime_verified"
    elif any(item["meta_status"] == "indexed" for item in artifacts):
        proof = "meta_indexed_runtime_unverified"
    else:
        proof = "source_catalogued_only"
    return {"target": target, "version_proof": proof, "artifacts": artifacts}


def main() -> int:
    parser = argparse.ArgumentParser(description="dCore intent classifier and dependency-aware card router")
    parser.add_argument("--db", type=Path, default=Path("knowledge/dcore.sqlite"))
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--query")
    mode.add_argument("--meta-query")
    parser.add_argument("--intent", default="auto")
    parser.add_argument("--ids-only", action="store_true")
    parser.add_argument("--contrast-limit", type=int, default=2)
    parser.add_argument("--route-limit", type=int, default=4)
    parser.add_argument("--profile", choices=("denizenm", "official"), default="denizenm")
    parser.add_argument("--addon", action="append", default=[], help="Addon name or addon@version; repeatable")
    parser.add_argument("--minecraft")
    parser.add_argument("--paper")
    parser.add_argument("--java")
    parser.add_argument("--denizen-version")
    parser.add_argument("--denizenm")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    with sqlite3.connect(args.db) as db:
        declared_target = {
            "profile": args.profile,
            "minecraft": args.minecraft or "",
            "paper": args.paper or "",
            "java": args.java or "",
            "denizen": args.denizen_version or "",
            "denizenm": args.denizenm or "",
        }
        if args.meta_query:
            payload = resolve_meta(
                db, args.meta_query, args.profile, tuple(args.addon),
                denizen_version=args.denizen_version, denizenm_version=args.denizenm,
            )
        else:
            intent, scores = classify_intent(db, args.query) if args.intent == "auto" else (args.intent, {})
            domains, cards = route(db, args.query, intent)
            decision_required = intent in DECISION_INTENTS or (
                "visual" in domains and len(tokens(args.query)) >= 8
            )
            payload = {
                "intent": intent,
                "intent_scores": scores,
                "active_domains": domains,
                "selected_cards": cards if args.ids_only else card_payload(
                    db, cards, declared_target, tuple(args.addon)
                ),
                "router_trace": router_trace(
                    db, args.query, intent, declared_target, tuple(args.addon)
                ),
                "decision_required": decision_required,
                "candidate_route_patterns": route_pattern_payload(
                    db, args.query, domains, cards, args.route_limit
                ) if decision_required else [],
                "contrast_examples": contrast_payload(
                    db, args.query, domains, args.contrast_limit
                ),
            }
            payload["route_status"] = (
                "ROUTE_READY"
                if payload["router_trace"]["coverage"]["status"] == "complete"
                else "ROUTE_INCOMPLETE"
            )
        payload["target_context"] = target_context(
            db, args.profile, args.denizen_version, args.denizenm,
            args.minecraft, args.paper, args.java,
        )
        payload["compatibility_advice"] = compatibility_advice(
            db, tuple(args.addon), args.minecraft, args.paper
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
