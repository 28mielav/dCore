# 0.82 audit and release boundaries

## Publication review — 2026-09-11

Reviewed the repository's component map, release history, build paths, workflows, licensing and security-sensitive operations. The previous public release was 0.70 without attached distributions; 0.75 and 0.76 changes existed in Git history. The 0.82 release adds downloadable CLI, Skill and GPT archives with SHA-256 sums, built by GitHub Actions from the release tag.

Local verification: 317 tests and 17 subtests passed; one POSIX permission test was skipped on Windows and is included in the Linux release job. Bandit scanned approximately 19,700 Python lines, reporting 18 low and 25 medium findings, with no high-severity findings. Reviewed SQL warnings use parameter placeholders or maintained schema identifiers; subprocess calls use argument lists, and network access belongs to explicit source-import/update commands. These scanner observations are not a certification of safety.

The manual review fixed unchecked restore paths before any restored file is written, restricted new/replaced POSIX master-key files to owner access and excluded Python caches from Skill bundles. Regression cases cover traversal and Windows-style paths, preservation of an existing key and cache exclusion. Private vulnerability reporting was enabled and confirmed on GitHub.

pip-audit found no known vulnerabilities in the installed optional runtime and test dependency versions checked on this date: cryptography 50.0.0, cffi 2.1.1, pycparser 3.0, pytest 9.1.1, pluggy 1.6.0, iniconfig 2.3.0, packaging 26.3 and colorama 0.4.6. A pattern scan of publishable files, including database bytes, found no matching private-key blocks or common GitHub, AWS and API credential formats. This is a scoped review, not an exhaustive penetration test or a guarantee against every secret format.

Starting point: `c1c7a1e7aaecc9bb8afd0402ba4edb5866ce3f46`, clean tree, package 0.76. No applicable AGENTS.md was found in the workspace or its ancestors. Before source changes, all 1,565 repository files were copied outside the repository and verified by SHA-256. Initial suite: 207 tests and 14 subtests passed.

## Component map

| Component | Actual behavior at baseline | Problem and 0.82 response |
|---|---|---|
| CLI | Dispatcher calls shared Python modules; table and JSON lint outputs exist | Retrieval default DB depended on cwd. Resolve beside the installed package; add reusable dcore.toml targets |
| Skill | Bundle contained instructions and runtime as siblings | Installing only dcore lost runtime; adapters used checkout paths. Nest runtime inside installed Skill and add an anchored launcher |
| GPT | Zip import bootstrap plus separate SQLite upload | Filesystem-based examples/data could not resolve within a zip. Extract runtime and place database beside it; test the actual bootstrap with site packages/source path excluded |
| Event lint | Any flag-looking text before cancellation counted as a guard | Reproduced comment/player-flag bypass. Query IR branch paths; recognize a conservative context-object predicate subset, report uncertainty as warning |
| Loops | wait/session/timeout substrings suppressed diagnostics | Reproduced comments and narrate bypass. Query branch outcomes, recognize immediate exit and early next, do not call a possible conditional exit a finite bound |
| Semantic core | Selected Denizen-Core behavior, separate command builder | while next was treated as nested while and could multiply analysis work. Add loop controls. Full frontend unification remains incomplete |
| Shader lint | Legacy/mid-era JSON checked by shape; namespace accepted as target | Add audited schema selection, direct stages, block-uniform shape, texture inputs, external-target diagnostics and render-mode context |
| Retrieval | Up to 14 cards including communication rules; exact API available separately | Return concise API matches alongside recipes, rank exact command names, normalize selected Russian colloquialisms/typos, keep communication cards outside content output |
| Knowledge | 176 cards, 39 contrasts, 10 route patterns, 5 visual sources | No identical guidance duplicates. Repair 13 selected cards, retain provenance and historical APIs. This is a targeted content review, not a claim that all cards now have complete recipes |
| Visual references | Five local upstream snapshots; historical pack versions | Inspect files/licensing and selected mechanisms; record local inventory hashes. Preserve sources; no unlicensed code copied |
| Build parity | Mostly file-existence assertions | Add actual isolated CLI/Skill/GPT runs with the same multifile corpus, API query and shader pack; compare returned findings |
| Runtime report | PASS plus case names could unlock READY | Bind to normalized project content hash, versions and origin. User reports remain RUNTIME_USER_REPORTED and never become independent execution |
| README / CI / licenses | Module-oriented README; CI lacked explicit pytest install; MIT plus confusing private-GPT wording | Task-first entry, SVG illustrations, practical examples; explicit test dependencies; public GPT license clarified, brand policy kept separate |

## Content decisions

Rewritten: CORE-027/028, TEACH-003/005, DEN-025, PERF-002, VER-002/021, VIS-006/024/027/033/041. Communication entries now have their own kind and do not appear as API/recipe content in ordinary CLI retrieval. Historical Meta and all attribution records remain.

Retained: the remaining cards pending deeper example/version review; no identical guidance bodies warranted deletion. Related math/local-frame cards and repeated lifecycle advice may benefit from a future semantic merge, but deleting them without evaluating their links and version scopes would erase useful distinctions. The present migration deliberately does not claim that work was done.

Practical material added: three original complete 1.21.8 teaching packs and one shared workbench explaining targets, activation, mask versus scene, menu versus UI, Fabulous, intensity, cleanup and cost. Local VariablesViewer and JNNGL custom_blur declare pack 34; they are not current interfaces merely because their mechanisms remain useful.

## Public claims and evidence

| Claim | Evidence / limit |
|---|---|
| All deliveries perform primary analysis independently | Execution parity test uses installed launchers/bootstrap outside checkout under isolated Python; hosted GPT upload behavior is a separate manual check |
| Event comments cannot prove ownership | Negative regression tests plus positive dominating context-filter cases |
| while true is not automatically a bug | Immediate while stop avoids busy/bound advice; conditional progress remains advisory |
| 1.21.8 has a non-spectator outline route | Official client/mappings hashes, mapped bytecode and target bundle inspected; no Minecraft session executed |
| Shader examples are working gameplay demonstrations | **Not claimed**: original complete lessons have source/interface and static checks; GPU compilation/render matrix are unrun |
| Refined is fully integrated | **Not claimed**: selected diagnostics and a Denizen-Core semantic subset, with NOTICE/LICENSE preserved |
| A supplied PASS is independent runtime proof | **Rejected**: reports preserve user origin even when binding fields match |
| Every Denizen/Reflect construct and historical shader profile is supported | **Not claimed**: conservative subsets and unknown-target warnings remain |
| All knowledge has been comprehensively rebuilt | **Not claimed**: selected repairs and routing improvements; further card-by-card recipe validation remains |

## Remaining release limitations

- Full shared frontend/dataflow migration is unfinished: the existing lint parser and semantic core builder still coexist with the IR. Do not delete either based on current test coverage.
- Dynamic calls, callbacks, alias-based ownership predicates, compound conditions and all dialect extensions need broader path modeling. Some legacy lifecycle/shape heuristics still exist.
- The shader linter does not implement every snapshot codec, renderer interface, uniform ABI or GPU compiler. Unknown schemas stay explicit; custom renderer declarations are not validated integrations.
- No Paper server, Minecraft client, hosted Custom GPT session or GPU compiler was run. F5/F1/resize/GUI-scale/reload/transparency/pack conflict matrices are provided as instructions, not fabricated results.
- ShaderSelectorV2/common-shaders lineage is unresolved. No upstream shader implementation from those sources is redistributed.
- Runtime scenario selection is still heuristic and cannot replace a project-specific test plan.

## Codex for Open Source

The [official program page](https://developers.openai.com/community/codex-for-oss), checked during this work, describes six months of ChatGPT Pro with Codex, conditional Codex Security access and API credits. It invites core maintainers or widely used public projects, and also projects with an important ecosystem role. The page does not guarantee approval or establish a response deadline for this application.

No repeat application or message was sent. A README redesign is not an approval criterion or a promise. Reproducible installation, useful fixes, real user examples and correct licensing are valuable independently. No downloads, adoption, testimonials or contributor-history explanations were invented.

## Verified delivery state

The independent delivery test uses real CLI/Skill/GPT entrypoints under isolated Python outside the checkout and compares multi-file lint, historical API retrieval, 1.21.8 and 1.21.11 pack analysis and all 34 bundled client profiles. It does not verify the hosted GPT interface.

Historical source profiles and their exact SHA values are documented in historical-targets.md. Core dependencies are date-associated and explicitly unverified as binary pairings. The old `duration:` and newer `expire:` flag options are both in code cards and checked against selected Meta. Empty target scopes and historical tag tombstones cannot inherit current types. The official 1.16.5 client shader files were inspected after SHA-1 verification; its legacy post schema and absence of the modern core route are tested.

## Visual route repair follow-up

Exact visual asset/interface inventories cover all 34 stable clients from 1.16.5 through 26.2; 1.21.11 and 1.21.8 remain priorities. Each client jar was verified against official SHA-1 before extracting metadata. Fixed skipped pack.mcmeta parsing, modern format ranges, target-format disagreement, unavailable vanilla stages and the 1.21.11 post vertex interface. Eight existing visual cards now distinguish entity attachment, draw submission/culling, control decoding and scene composition. Parsed display-follow and mount diagnostics are conservative advice, not a universal ban on mounts. No new shader pack was added.

The new regressions cover these interfaces, wrong-version stages, malformed/ranged metadata, ordinary command/comment controls and reused save names. Independent delivery execution now includes both primary visual targets as well as historical Denizen retrieval. Server/client visual output is still unverified; these fixes repair dCore analysis and guidance, not the deployed effects from the other tasks.

The full-range follow-up adds version-selected overlay merging, exact graph paths, standalone offline coverage output and pre-1.19.4 display-entity diagnostics. Interface selection comes from the exact client graph and built-in vertex stage, not a nearest-version guess. Source/profile evidence is distinct from tested Denizen jar pairings and from GPU/client runtime proof. The release-time importer retains metadata caches outside the repository and removes temporary downloaded jars; no new shaders are shipped.
