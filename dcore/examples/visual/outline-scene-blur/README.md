# outline-scene-blur

Target: **Minecraft Java 1.21.8, resource-pack format 64, vanilla renderer**.
Graphics modes: Fast/Fancy/Fabulous are source-level candidates for this route; client matrix not run.

## Activate and expected image

Load only this lesson pack. Summon the same visible glowing pig as the mask lesson. Keep the camera on it. Remove it to disable. This is a diagnostic trigger, not a stable per-viewer production controller.

Expected (not a screenshot or runtime result): Scene color is blurred while the glowing-entity outline pass runs. The pass replaces the outline buffer with opaque scene color for its later composition. HUD/GUI coverage is not promised.

## Mechanism

The JSON graph owns one full-size swap target. Each pass reads a different attachment from its output. The original lesson shader uses the 1.21.8 Position/Projection/SamplerInfo interface. `minecraft:projection.glsl` is supplied by the exact client, not copied into this pack. The blur uses five texture reads per pixel per pass; its direction is normalized by textureSize, and Intensity=0 returns the input. Changing JSON requires F3+T.

## Checks and limits

Source review: official client archive and mappings matched Mojang SHA-1 metadata; route/target interfaces inspected with javap and extracted assets. Static checks are reproduced by verification/test_visual_lessons.py. No Minecraft client/server or GPU compilation was executed during preparation.

Test F3+T, resize, F5, F1, GUI scale, graphics modes, visible/culled carrier, removal and another pack overriding the same JSON. These lessons override vanilla paths: the last selected resource wins. The two outline lessons conflict and must be loaded one at a time. Remove the pack to restore vanilla behavior. There is no persistent history buffer or server worker.

Cost: two fullscreen passes, one additional color target (about 4*width*height bytes for RGBA8, excluding driver overhead and existing buffers). Blur uses ten reads/pixel across both passes; half-size buffers would reduce area to one quarter but change quality and need a separate version-specific implementation.

## License and source

Lesson code: MIT, copyright 2026 dCore contributors (see bundled LICENSE). No upstream shader implementation is redistributed. Interface facts were checked against Mojang's 1.21.8 client, obtained via https://piston-meta.mojang.com/mc/game/version_manifest_v2.json . See ../SOURCE_REVIEW.json for hashes and method evidence. Runtime compatibility is unverified.
