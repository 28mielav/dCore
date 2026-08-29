# dCore agent instructions

Served as `dcore://instructions`. This is the operating contract for any agent
one client could read.

Use the repository as the source of truth. Never paste the SQLite database or raw
retrieval rows into a response.

## mandatory local-evidence gate

For every Denizen/dCore question, use local evidence before browser search,
memory or generic documentation. The order is strict:

1. resolve the target and call `dcore_retrieve` (`intent: auto`; use `query` for a
   focused topic and `meta_query` with `profile: denizenm` for API syntax);
2. inspect `target_context`, `version_scope_structured`, applicability and
   provenance before forming an answer;
3. browse only after a recorded `not_indexed`, `no_recorded_rule`,
   `target_required`, `runtime_unverified` or an explicit current/upstream/URL
   request;
4. treat web material as supplemental verification, never as a silent replacement
   for target-pinned local facts. If sources conflict, report the conflict and
   mark the claim `INCOMPLETE`.

Never claim a database-backed answer when retrieval was not run. If local
retrieval is unavailable, say `LOCAL_RETRIEVAL_NOT_RUN` and stop at the proof
boundary unless the user explicitly asks for web-only research.

## seven-step execution gate

1. inspect the project, dirty Git state, requested gameplay contract, files,
   ownership, lifetime, persistence, failure paths and cleanup;
2. resolve the target from explicit Minecraft, Paper, Java, Denizen/DenizenM,
   addon and JAR versions; never silently merge facts from incompatible builds;
3. query the matching Meta/source evidence and compare native DenizenM, a
   dedicated addon and Reflect; use Reflect only behind one narrow adapter;
4. design the smallest complete state shape with one authoritative writer, one
   lifecycle owner, one cleanup owner and bounded loops/scans/queues;
5. implement the complete requested change when the user asks to change, fix,
   build or refactor; use bounded teaching fragments only for teaching/review;
6. call `dcore_lint` over the whole supplied project, with `closed_world: true`
   when the project is complete, then run design, retrieval and gate checks;
7. report exact changed files, static results, JAR evidence, runtime proof and
   remaining unknowns; never call static success runtime success.

## target-aware lint

Pass the target explicitly for multi-version work:

```json
{
  "paths": ["scripts/"],
  "profile": "denizenm",
  "minecraft": "1.21.11", "paper": "1.21.11", "java": "25",
  "denizenm": "b7299M",
  "addons": ["reflect@2.4.2"],
  "jars": {"reflect": "path/to/denizen-reflect.jar"},
  "strict_warnings": true
}
```

Use `require_jar_evidence: true` when version-sensitive APIs must be blocked
without exact artifacts. A saved target is only a convenience; the facts are
selected by the declared target matrix.

Historical DenizenM builds use separate Meta snapshots. `denizenm: 7268M` must
never receive syntax from `7299M`; if the exact snapshot is absent, stop at the
proof boundary. Declare every addon as `name@version`; compatibility advice is
valid only when the release and Minecraft/Paper range match a recorded
evidence-backed rule.

Every returned card carries a structured applicability result. Use only
`applicable` or `applicable_target_*` guidance; resolve a missing target or addon
version before using a deferred card as a recommendation.

Historical Meta is stored as a current base plus per-build overrides and
tombstones. Resolve that overlay before asserting whether a target build has an
API; compact storage never permits fallback to current syntax.

## Reflect rules

Treat Reflect as a dialect and provider boundary, not as a blanket exemption. The
linter may validate the visible invoke shape and addon declaration, but it must
not claim a Java class, method, overload, type, nullability or thread contract
without exact JAR evidence. Keep calls in one adapter and keep gameplay state in
Denizen. Prefer native DenizenM first.

## clean production rules

- narrow events and identity guards precede mutation or cancellation;
- one authoritative writer owns each connected fact;
- every acquired entity, queue, task, temporary flag and listener has one cleanup
  owner;
- no hidden permanent entities, chunk tickets, dormant queues or unbounded scans;
- after a wait, revalidate or re-resolve live references;
- state machines use explicit phases and legal terminal transitions;
- movement has one owner per session;
- do not add managers, helpers, permissions or forwarding tasks ceremonially;
- keep direct Java/Reflect calls out of broad gameplay handlers;
- use natural lowercase Russian prose, including after a sentence-ending period;
  preserve normal case only for code, paths, API names and acronyms.

## official Denizen semantics

Use the [official Denizen Beginner's Guide](https://guide.denizenscript.com/) as a
compact semantic source, not as a current versioned grammar. The guide is official
but incomplete and may contain older examples. Let selected Meta, exact JAR
evidence and runtime proof override it.

Apply only these high-signal invariants:

- a procedure must determine a value; use a task for side-effect-only work;
- definitions are queue-local; do not treat them as cross-event or persistent
  state;
- a live entity/player/location captured before `wait` must be re-resolved or
  revalidated before later mutation;
- lore, display names and other presentation text are not authoritative data;
- player names are presentation, not persistent identity keys;
- `/ex` is a privileged interactive test tool, never a production dispatch path;
- prefer a proven native Denizen command over console `execute` when the selected
  Meta contains that native command.

The linter emits these as `procedure_missing_determine`,
`stale_live_reference_after_wait`, `display_value_used_as_data`,
`player_name_used_as_identity`, `ex_command_in_production` and
`execute_native_command`. Keep the findings evidence-backed and do not extend them
into broad style policing.

## delivery

For a change request, finish the in-scope implementation and verification. For a
diagnosis, do not silently edit. For teaching, give a bounded fragment, ask for the
invariant and reduce help over time. Always show a compact table: severity, code,
location, problem and fix.

Raw retrieval, route dossiers and machine lint JSON stay backstage. The user sees
the table and the conclusion, not the transport.

## proof boundaries

`dcore_design_compare` cannot declare runtime success. `READY_FOR_PROOF` means one
route is the unique proven pre-code candidate for the supplied facts.
`DECISION_REPRODUCED` means only that verification recomputed the same artifact.

`dcore_release_gate` returns `READY` only with explicit target, retrieval, route
when applicable, addon/JAR evidence, clean static checks and a passing runtime
report. `RELEASE_BLOCKED` is the correct result when Minecraft runtime was not run.

`dcore_shadow` is a low-memory queue/reservation/capacity/cleanup simulation. It is
an intermediate proof layer and never replaces a server runtime report.

Static lint and `/ex reload` are different checks. A clean report does not replace
loading the scripts on the same Denizen/Paper build.

## obfuscation

Obfuscation is opt-in. Use it only when the user explicitly asks to hide, protect,
package, obfuscate or restore source.

Build the semantic chain before choosing names: parse all files with
`dcore.semantics.ir`, build the call/state graph with `dcore.semantics.graph`,
classify the surface with `dcore.semantics.surface`, then use
`dcore.semantics.transform`. Keep registered `item`, `command` and `world`
containers and persistent server state public. Rename only proven internal
containers and queue-local definitions.

Treat unresolved, dynamic, ambiguous, unsupported or externally callable symbols as
`unknown` and stop the transformer; never guess from spelling or from a single file.
The transformer edits exact spans in place, so it preserves preambles, settings
sections, comments and non-semantic text; it deliberately does not rewrite `spawn`
targets or public item identities. Its default `verify=True` runs
`dcore.semantics.proof`: reparse the output, compare canonical source, sections,
calls, definitions, state and surface, and reject any mismatch.

Do not re-enable the old regex splitter as a fallback for an unknown surface.
