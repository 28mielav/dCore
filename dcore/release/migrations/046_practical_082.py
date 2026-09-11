"""dCore 0.82: repair advice without erasing historical API/provenance."""
import argparse
import sqlite3
from pathlib import Path


REVISIONS = {
    'CORE-027': ('Scale the workflow to the requested result',
        'For a small fix inspect the affected path, implement the repair and run a focused regression. For a complex mechanic compare feasible routes and include setup, ownership and cleanup. Deliver the requested complete artifact; do not substitute a probe for the result.'),
    'CORE-028': ('Natural language and useful names',
        'Use natural speech in the user\'s language, with normal capitalization. Preserve meaningful script names. Do not insert dcore into permissions, flags or user containers without a functional reason. The installed Skill directory is named dcore.'),
    'TEACH-005': ('Review mechanisms with clear repairs',
        'Describe the failing behavior, its cause and the next useful repair or test. Do not use personal jabs, forced lowercase, or speculative AI-authorship labels. In teaching mode explain one transferable mechanism and check understanding.'),
    'TEACH-003': ('Build understanding through a small working step',
        'When the user wants to learn, show a worked example, ask them to predict one change, and check the outcome. When they ask for implementation, deliver it. Do not withhold requested code as a lesson or infer authorship from style.'),
    'DEN-025': ('Cancellation filters must dominate affected paths',
        'Task: restrict cancellation to marked entities. Example:\n'
        'on player right clicks entity:\n'
        '- stop if:<context.entity.has_flag[owned].not>\n'
        '- determine cancelled\n'
        'The context-object predicate rejects unrelated objects before cancellation. Review who sets owned. Reading <player.flag[anything]> or writing a comment is not an identity check. An if branch that only narrates also does not protect a later sibling cancellation. The linter recognizes a conservative subset and reports unknown guards as advice, not proof of a bug.'),
    'PERF-002': ('Bound repeated work and review exit progress',
        'A long-lived yielding loop can be valid. A finite repeat count is easier to prove; for example repeat 20: with a wait 1t in its body has at most 20 body executions. A conditional stop in while true is only a possible exit unless its condition progresses. Words like session, expire or timeout in messages/comments prove nothing. Repeatedly scheduling new queues does not establish finite lifetime. Review ownership, cancellation and cleanup on actual paths.'),
    'VER-021': ('Bind reported runtime evidence to inputs and origin',
        'Use the run result project_sha256 when recording cases. Include matching environment versions and provenance with runner, timestamp and method. A changed project or mismatched target invalidates the report. A supplied PASS remains RUNTIME_USER_REPORTED: dCore did not independently execute or authenticate it, and it cannot produce READY. Missing and partial reports stay explicit.'),
    'VER-002': ('Refined diagnostics supplement the portable engine',
        'dCore contains selected Refined-style diagnostics and a source-derived Denizen-Core semantic subset. This is not a complete Refined runtime integration. Use the installed editor tooling where available, then inspect target Meta and project paths. Preserve NOTICE and LICENSE for the semantic core.'),
    'VIS-024': ('1.21.8 outline trigger, mask and scene access',
        'Task: inspect an entity silhouette or process scene color without spectator. On vanilla Java 1.21.8 (pack 64), a visible glowing entity takes the outline path. Source inspection shows OUTLINE_TARGETS includes minecraft:main and minecraft:entity_outline. Examples: dcore/examples/visual/outline-mask and outline-scene-blur. Summon a tagged glowing pig in a disposable world, then remove it to disable. Mask alpha selects covered entity pixels; a separate pass can instead sample main and write the outline output for composition. This is a hardcoded route, not arbitrary /posteffect activation. Culling, absent carriers, panorama, mods and pack conflicts affect it; no game run is claimed.'),
    'VIS-027': ('Select post schema and framebuffer graph by client',
        '1.21/1.21.1 use legacy post paths/intarget/outtarget. 1.21.2-1.21.4 use post_effect, mapped targets and program/inputs/output. 1.21.5 removes program JSON in favor of direct vertex_shader/fragment_shader. 1.21.6-1.21.8 use per-block uniforms with typed value entries. A namespace does not create a target. For separable blur use main -> swap -> destination; never sample the attachment being written. Match external targets to the render route. See the three complete 1.21.8 packs in dcore/examples/visual.'),
    'VIS-033': ('Instrument the actual route with a removable probe',
        'Use a small constant color or variable display to locate the draw route before adding a complex effect. VariablesViewer provides an MIT historical variable-encoding mechanism, but its pack format 34 and legacy files are not a 1.21.8 interface. Its texture generator requires Pillow. Test a marked and unmarked object, then remove the probe. See visual-workbench.md for the inspected local references and version limits.'),
    'VIS-041': ('Resolve stages using the selected schema',
        'Resolve the merged custom files and client-owned imports separately. Modern 1.21.8 passes name vertex_shader and fragment_shader directly; demanding a program JSON is wrong. Example files in dcore/examples/visual use an original quad.vsh and fragment stages plus the client projection.glsl interface. Verify sampler names and uniform block layout as well as input/output targets. Static parsing is not GPU compilation or render evidence.'),
    'VIS-006': ('Fullscreen behavior depends on the activation route',
        'For 1.21.8 use a verified hardcoded route such as entity_outline or menu blur, or an explicitly supported mod route. Do not generalize one route\'s GUI or spectator restrictions. For 26.3 Snapshot 3, official notes introduce /posteffect add/remove/clear/list and always-on minecraft:end_of_frame; later snapshots change pipeline interfaces. No future Denizen/DenizenM wrapper is assumed. Pin the implementation and client before generating commands.'),
}


def migrate(db):
    for card_id, (title, guidance) in REVISIONS.items():
        db.execute('UPDATE cards SET title=?,guidance=? WHERE id=?', (title, guidance, card_id))
    for card in ('CORE-007', 'CORE-014', 'CORE-022', 'CORE-023', 'CORE-024', 'CORE-025', 'CORE-028'):
        db.execute("UPDATE cards SET kind='communication' WHERE id=?", (card,))
    db.execute("UPDATE cards SET kind='communication' WHERE domain='teaching'")
    db.execute("UPDATE cards SET version_scope=? WHERE id='VIS-024'",
               ('Minecraft Java 1.21.8, pack format 64, vanilla renderer; source inspected, runtime unverified',))
    db.execute("UPDATE cards SET source_basis=source_basis || ? WHERE id IN ('VIS-024','VIS-027','VIS-033','VIS-041') AND instr(source_basis,'0.82 review:')=0",
               ('; 0.82 review: official 1.21.8 client/mappings, SHA-1 checked; dcore/examples/visual/SOURCE_REVIEW.json; original lesson code MIT',))
    # Keep original provenance/links and historical scopes; corrected guidance
    # supersedes the behavioral advice without deleting API snapshots.
    for card_id, terms in {'VIS-024': ('обводка', 'outline scene blur', 'без spectator'),
                           'VIS-027': ('блюр', 'menu blur', 'blur фона меню', 'uniform blocks'),
                           'VIS-041': ('1.21.8', 'vertex_shader', 'shader stage')}.items():
        for term in terms:
            db.execute('INSERT OR IGNORE INTO card_alias_terms(card_id,term,weight) VALUES(?,?,?)', (card_id, term, 12))
    db.execute("UPDATE contrast_examples SET invariant=?,verification=? WHERE id='CX-DEN-004'",
               ('Every repeating path yields or exits; a possible conditional exit is not a proven finite bound.',
                'Test comments, text markers, dead branches, while next before wait, immediate exit and finite repeat. Review progress and cleanup separately.'))
    db.executemany('INSERT OR REPLACE INTO metadata(key,value) VALUES(?,?)',
                   [('name','dCore 0.82'), ('release.version','0.82'),
                    ('knowledge.review.082','13 guidance repairs; no identical guidance duplicates; historical API/provenance retained; remaining cards require deeper example review')])


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--db',type=Path,required=True)
    args=parser.parse_args()
    with sqlite3.connect(args.db) as db:
        migrate(db)


if __name__ == '__main__':
    main()
