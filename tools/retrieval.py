from __future__ import annotations

import re
import sqlite3


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


def route(db: sqlite3.Connection, query: str, intent: str) -> tuple[list[str], list[str]]:
    db.row_factory = sqlite3.Row
    rule = db.execute(
        "SELECT max_cards FROM router_rules WHERE intent=?", (intent,)
    ).fetchone()
    if not rule:
        raise ValueError(f"unknown retrieval intent: {intent}")
    max_cards = min(10, rule[0])
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

    selected: list[str] = []

    def add(card_id: str) -> None:
        if card_id in selected or len(selected) >= max_cards or not eligible(db, card_id, query):
            return
        row = db.execute("SELECT domain FROM cards WHERE id=?", (card_id,)).fetchone()
        if row and row[0] in active:
            selected.append(card_id)

    for row in db.execute(
        "SELECT card_id FROM route_pins WHERE intent=? ORDER BY position", (intent,)
    ):
        add(row[0])
    for row in db.execute("SELECT card_id FROM card_activation_rules ORDER BY card_id"):
        if activation_match(db, row[0], query):
            add(row[0])

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
    for row in fts(db, query, active):
        if len(selected) >= min(6, max_cards):
            break
        add(row["id"])
    return active, selected


def run_tests(db: sqlite3.Connection, ids: set[str] | None = None) -> list[dict]:
    db.row_factory = sqlite3.Row
    failures = []
    for test in db.execute("SELECT * FROM retrieval_tests ORDER BY id"):
        if ids and test["id"] not in ids:
            continue
        domains, cards = route(db, test["query"], test["intent"])
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
                    "active_domains": domains,
                    "selected_cards": cards,
                    "missing_cards": sorted(expected_cards - set(cards)),
                    "forbidden_cards": sorted(forbidden_cards.intersection(cards)),
                    "missing_domains": sorted(expected_domains - card_domains),
                    "forbidden_domains": sorted(forbidden_domains.intersection(card_domains)),
                }
            )
    return failures
