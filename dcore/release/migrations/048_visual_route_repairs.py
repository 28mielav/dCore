"""Repair visual advice from observed failures; no shader packs are added."""
import argparse
import sqlite3

REPAIRS = {
    "VIS-022": "Separate five observations: the selected final-pack post pass executes; the intended producer is drawn; its control data is decoded; the effect changes the intended scene output; neutral/reset and viewer isolation work. A constant red diagnostic proves only pass execution. A missing second band identifies an unproven stage, not an exact root cause. Clean reload/compiler logs and uploaded hashes do not prove visible output. Remove probes only after the relevant stage is observed, and never report an assistant's earlier claim as runtime evidence when later user tests contradict it.",
    "VIS-023": "For view-relative content separate entity attachment, draw visibility and final client projection. Mount attaches a carrier to an entity; pivot and translation do not supply the client camera transform or guarantee screen coverage. A server eye-location follow loop can lag rapid camera motion. If the goal is scene-wide post-processing, retain a scene-color post route; an item model or skybox is not the requested effect. A carrier can transport control state only after its actual draw route is proved. Declare F1/F5 behavior and verify the target client rather than prescribing one universal mount recipe.",
    "VIS-024": "Primary client targets are Java 1.21.8 and 1.21.11; retain historical profiles. On 1.21.8 the inspected outline route exposes main and entity_outline. On 1.21.11 the official entity_outline graph also consumes and writes minecraft:entity_outline, uses core/screenquad vertex-ID rendering and per-block uniforms. This graph is an existing client route, not arbitrary namespaced activation. Producer visibility, route selection and composition need separate evidence. Existing 1.21.8 lesson files are not automatically 1.21.11-compatible; swapping pack_format is insufficient. Neither client profile is GPU/runtime certification.",
    "VIS-030": "Keep independent effect channels, levels, start time, duration, amplitude and a bounded envelope. A shake effect must not accidentally enable heartbeat or vignette; visual displacement must not mutate authoritative player look unless requested. Tie pulse and sound to one session clock, with explicit units and restart behavior; GameTime is not automatically elapsed time since activation. Switching off one effect preserves other owners and restores its neutral value. Verify level changes, overlapping starts, reconnect and stale session cleanup.",
    "VIS-031": "Inspect the exact final merged pack and renderer before naming a core route. A pass compiling or executing does not prove a particular ItemDisplay enters it. Distinguish producer absence, wrong route, CPU frustum culling, marker decoding and output composition with separate observations. Preserve unmarked rendering and inspect normal-pass visibility so a transport marker does not become visible paper or a white square. Do not infer that glow_color is the ordinary item shader Color attribute; inspect the target producer/consumer interface. Test the actual 1.21.8 or 1.21.11 interface independently.",
    "VIS-032": "Entity tracking and screen projection have separate responsibilities. Moving vertices into clip space happens after the carrier is submitted; it cannot recover a draw discarded by CPU frustum/entity culling. Raising view_range changes distance visibility, not every culling decision or camera-relative attachment. Mount, pivot=center, zero display dimensions, negative scale and a marker armor stand are not interchangeable proofs of no hitbox, no latency or full coverage. Verify full yaw/pitch, FOV 30 and 110, F1/F5, movement, resize and GUI scale; verify attack/use rays and other viewers. Do not promise stability from a single successful camera angle.",
    "VIS-034": "Reserve viewer-scoped control channels and define absent/invalid state as neutral. Verify both the ordinary rendering branch (no visible carrier) and the decoder branch (state still reaches the post pass). Transparent textures may be discarded or altered by atlas/filtering before decoding; disappearance of paper is not proof that the channel works. Keep heartbeat and shake channels separate. Reconnect, new viewers, reload, death, world change and stop must not leave carriers or stale control pixels. A packet-only carrier needs independent submission and visibility evidence, just like a real entity.",
    "VIS-038": "Run lint-pack on the final merged pack with an exact target. Primary checks cover 1.21.8 (resource format 64) and 1.21.11 (75.0, min_format/max_format). Validate actual pack.mcmeta, stage existence, shader interfaces, inputs/outputs and merged overrides. 1.21.11 post passes use core/screenquad and a vertex-ID triangle; a Position-buffer shader from 1.21.8 is not automatically compatible. Keep old version profiles and mark unknown schemas explicitly. STATIC_OK means only implemented static checks passed, not that an effect is visible, attached or gameplay-safe.",
}


def migrate(db):
    for card, guidance in REPAIRS.items():
        db.execute("UPDATE cards SET guidance=? WHERE id=?", (guidance, card))
    db.execute("UPDATE cards SET title=?,version_scope=? WHERE id='VIS-024'",
               ("1.21.8 and 1.21.11 outline route boundaries", "Java 1.21.8 and 1.21.11; exact client assets inspected, runtime unverified"))
    for card in ("VIS-024", "VIS-031", "VIS-032", "VIS-038"):
        for term in ("1.21.11", "1.21.8", "крепление шейдера", "видимая бумага", "fov 30"):
            db.execute("INSERT OR IGNORE INTO card_alias_terms(card_id,term,weight) VALUES(?,?,?)", (card, term, 12))
    db.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('visual.primary_targets','1.21.11,1.21.8')")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    args = parser.parse_args()
    with sqlite3.connect(args.db) as db:
        migrate(db)
