# Historical targets and evidence

dCore is multiversion: the intended range is Minecraft 1.16.5 through the latest Minecraft version supported by Denizen. 1.21.8 and 1.21.11 are priority targets, not an allowlist or upper bound. Select evidence for the actual target; gaps in indexed schemas remain explicit.

Select the actual installed Denizen build as well as Minecraft. Minecraft alone does not identify the Denizen or Core jar.

| Query target | Denizen source | Core source | Evidence limit |
|---|---|---|---|
| 1.1.4-source-7f9353e83 | 7f9353e83a935b1b48808e54f493c4247dd33bbf | 732068a87c80a822f89b78646ef9e46be2e89818 | Source profile, not a numbered build; historical 1.12.2 era |
| 1.2.6-b1782 | 2354775a8cfe687aa612e8216fd564f7e50c48e2 | addc82e8f8919a58dab69c39b5d15542bd7681b3 | CI polling source association; historical 1.16.5 recommendation |
| 1.3.0-b1804 | a063ef49c9261eb30ad3304359fb93c6fdd0cb3e | 9e3ea88b6702ff12e590bb2f668b1a7db8b05f3e | CI polling source association; 1.17.1/1.18.2/1.19.4/1.20.4 recommendation |

All Core sources above are associated by date, not resolved from a verified binary dependency. The linter emits an evidence warning. Missing historical Core sources are omitted, with an explicit gap; current Core must not substitute silently. Source syntax is useful evidence, not a server compatibility certificate. Earlier Denizen releases exist; no claim about its first release is made. DenizenM historical overlays retain their existing version boundaries.

The author-maintained [distribution page](https://www.spigotmc.org/resources/denizen.21039/) lists historical builds back to Minecraft 1.8.8. Only the indexed profiles above are added in this release; unindexed targets remain visible gaps. Source archives can be reproduced with `python -m dcore.release.import_history --references ../references` using local Denizen and Denizen-Core git clones. Immutable SHA values are built into that importer.

For Minecraft 1.16.5, the official client jar was checked against Mojang download SHA-1 and its shader files inspected. `entity_outline.json` uses shaders/post, name/intarget/outtarget and a list of uniforms; program JSON uses vertex/fragment. This differs from post_effect plus direct stages and uniform blocks in 1.21.8. The vanilla replaceable core shader pipeline was introduced in [21w10a](https://www.minecraft.net/en-us/article/minecraft-snapshot-21w10a). The [Denizen resource-pack guide](https://guide.denizenscript.com/guides/non-denizen/resource-packs.html) documents pack format 6 for 1.16.5. No GPU runtime was executed.

Card code is selected against its structured targets. Incompatible examples retain their labels but omit copyable files. A missing target asks for a target rather than silently offering the modern variant. Version-neutral bounded repeat/wait code is shared. Every stable client from 1.16.5 through 26.2 has an exact asset/schema inventory (34 versions). Unindexed snapshots and future releases remain unverified rather than being interpolated from neighboring versions.

Upper-bound source check on 2026-09-10: official Denizen dev commit ec61942095eaec10660b31fba079096e6a04c86b includes v26_2 and v26_1 modules. Thus 1.21.11 must not be treated as the latest Denizen target. This is source-module evidence, not runtime certification or proof that all dCore shader codecs for those clients are implemented.

## Exact visual range

`python -m dcore.cli versions --minecraft-profiles` lists every indexed client offline, including the SHA-1 of its verified official jar, resource format, graph hash, post schema, uniform shape and vertex interface. This is separate from Denizen build Meta and binary dependency evidence above. Downloads for this inventory are explicit release-time work, never part of ordinary lint. Reproduce with `python -m dcore.release.shader_inventory --cache <external-cache> --output dcore/lint/shader_profiles.py --versions <exact versions>`; downloaded temporary jars are removed after extraction. Existing local reference jars are retained.

| Stable clients | Post interface |
|---|---|
| 1.16.5 through 1.21.1 | Legacy shaders/post, named programs, intarget/outtarget |
| 1.21.2 through 1.21.4 | post_effect, program reference, mapped targets, inputs/output |
| 1.21.5 | Direct vertex/fragment stages, list uniforms |
| 1.21.6 through 1.21.8 | Direct stages, block uniforms |
| 1.21.9 through 26.2 | Direct stages, block uniforms, vertex-ID fullscreen post geometry |

Each patch has its own built-in asset inventory; shared schema does not mean shared shader filenames or ABI. The linter selects resource-pack overlays for the exact target and applies later matching overlays last. Missing core override paths produce an advisory instead of pretending to replace a vanilla route. Display/interaction entities are rejected on pre-1.19.4 targets ([official release notes](https://www.minecraft.net/en-us/article/minecraft-java-edition-1-19-4)). GPU execution, renderer modifications and all possible shader ABI details remain outside this source-interface coverage.
