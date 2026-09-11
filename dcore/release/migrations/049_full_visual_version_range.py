"""Expose exact-client coverage without equating schema checks with runtime."""
import argparse
import sqlite3


def migrate(db):
    db.execute("UPDATE cards SET guidance=? WHERE id='VIS-038'", (
        "Run lint-pack on the final pack with the actual Minecraft target. The bundled inventory covers all 34 stable clients from 1.16.5 through 26.2, with 1.21.8 and 1.21.11 as priorities, not exclusive targets. It checks each client's resource format, post schema, built-in stage/include names, uniform shape and post vertex interface. It selects matching overlays in declared order before analysis; inactive version files must not contaminate findings. List exact evidence with versions --minecraft-profiles. Legacy post graphs last through 1.21.1; program-based graphs start at 1.21.2, direct stages at 1.21.5, blocks at 1.21.6, vertex-ID post geometry at 1.21.9. Preserve custom renderer uncertainty. Asset existence and STATIC_OK do not prove route activation, carrier visibility, GPU correctness or lifecycle behavior.",))
    db.execute("UPDATE cards SET guidance=guidance || ? WHERE id='VIS-032' AND instr(guidance,'Display entities themselves')=0", (
        " Display entities themselves require Minecraft 1.19.4 or later; do not prescribe ItemDisplay/TextDisplay to a 1.16.5 server. A newer Denizen build cannot provide missing vanilla entity types.",))
    db.executemany("INSERT OR REPLACE INTO metadata(key,value) VALUES(?,?)", [
        ("visual.version_range", "1.16.5 through 26.2; 34 stable exact-client source inventories"),
        ("visual.coverage_proof", "official client SHA-1 + asset/interface extraction; runtime unverified"),
    ])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    args = parser.parse_args()
    with sqlite3.connect(args.db) as db:
        migrate(db)
