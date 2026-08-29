# Sources and provenance

Use primary, target-pinned sources for changing claims. Store URL, publication date, target, and retrieval date in release evidence. Source text is evidence, not permission to redistribute code.

## Minecraft shader profile sources

- Minecraft Java Edition 26.3 Snapshot 3, Mojang, published 2026-07-07: introduced `/posteffect`; documented `add`, `remove`, `list`, and `clear`; stated that effects live on clients and server cannot know whether one applies; resource-pack format 91.0; introduced `minecraft:end_of_frame` always-on support. https://www.minecraft.net/en-us/article/minecraft-26-3-snapshot-3
- Minecraft Java Edition 26.3 Snapshot 5, Mojang/Minecraft Feedback: resource-pack format 92.0; moved OpenGL shader compilation to ShaderC and changed includes toward `#include`. https://feedback.minecraft.net/hc/en-us/articles/47532366769677-Minecraft-Java-Edition-26-3-Snapshot-5
- Minecraft Java Edition 26.3 Snapshot 6, Mojang/Minecraft Feedback: resource-pack format 94.0 and further shader changes. https://feedback.minecraft.net/hc/en-us/articles/47701137203213-Minecraft-Java-Edition-26-3-Snapshot-6
- Minecraft Java Edition 1.21.2 / Snapshot 24w34a technical changes, Mojang/Minecraft Feedback: moved post-effect definitions to `assets/<namespace>/post_effect`, programs to `shaders/post`, and changed program/target fields; warns that core shader overrides are unsupported. https://feedback.minecraft.net/hc/en-us/articles/31261174284557-Minecraft-Java-Edition-1-21-2-Bundles-of-Bravery

## Denizen evidence

Prefer target-pinned Denizen Meta exports, official Denizen documentation, exact plugin artifacts, and source at a pinned commit. For DenizenM/addons, record JAR SHA-256 and inspect its registered tags, mechanisms, events, and commands when published docs do not match the installed build.

## Third-party shader material

The local research catalog records exact upstream commit and license policy in `knowledge/visual_sources.json` and the database. Reuse architectural facts only where licenses or project policy permit. Do not copy unlicensed/reference-only source code into examples.
