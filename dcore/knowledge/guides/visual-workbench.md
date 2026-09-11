# Visual workbench

Start from the intended input: scene color, entity silhouette, menu background, or UI contents. Pin client, pack format, renderer and graphics mode before choosing files.

## Complete lessons

The original MIT packs live in `dcore/examples/visual/` in every runtime. Copy one lesson directory into resourcepacks. Each README explains activation, expected image, cost and cleanup.

| Java 1.21.8 / pack 64 lesson | Data path | Trigger |
|---|---|---|
| outline-mask | entity_outline → swap → entity_outline | visible glowing entity |
| outline-scene-blur | main → swap → entity_outline | visible glowing entity |
| menu-background-blur | main → swap → main | a screen invoking background blur |

Source/interface inspection and static checks are available. No Minecraft or GPU run is claimed. The two outline lessons overwrite the same resource: load only one. These are mechanism lessons, not production per-viewer controllers.

Use the tagged glowing pig command in the lesson README in a disposable command-enabled world. Keep the pig visible, then remove the tagged probe to disable. Ordinary Glowing is shared entity metadata; viewer-specific control needs a verified API and cleanup.

## Source evidence for 1.21.8

The official client and mappings matched Mojang's SHA-1 metadata. `SOURCE_REVIEW.json` identifies the downloads. Mapped javap inspection found:

- `Minecraft.shouldEntityAppearGlowing` accepts the entity's glowing state independently of the spectator shortcut.
- `LevelRenderer.shouldShowEntityOutlines` checks non-panorama rendering, an allocated outline target and a player.
- `LevelRenderer.renderEntities` selects OutlineBufferSource for qualifying entities; their geometry fills the mask.
- `LevelTargetBundle.OUTLINE_TARGETS` contains both main and entity_outline.
- `LevelRenderer.doEntityOutline` composites the outline target. An opaque scene result in that target differs from a sparse silhouette.
- `GameRenderer.processBlurEffect` loads the blur chain with MAIN_TARGETS.

Culling and producer absence affect activation. This establishes a non-spectator route, not arbitrary namespaced activation, stable carrier visibility, HUD coverage or modded-renderer compatibility. The lessons have no chasing server queue.

## Three different blur boundaries

Scene blur samples main when the outline graph runs. Check transparency and final composition in Fast, Fancy and Fabulous: the captured scene can differ by pass order.

Menu background blur is invoked by particular screens. Enable the client's background blur option and test the intended screen. Closing the screen restores the scene route. This does not establish control over every screen.

UI text/buttons drawn after background processing cannot be blurred by that earlier pass. Find a later capture/composition boundary or render the intended UI into its own sampled target using an available mechanism. Do not call world blur or a translucent overlay UI-content blur. No universal GUI/post order is asserted for other versions or injection points.

## Core shader decisions

Identify the render layer: solid, cutout, translucent, particle, text, GUI or another pipeline. Check attributes, flat/interpolated varyings, textures, uniform blocks, output attachments and blend/depth/cull state. A fragment shader cannot restore geometry already culled. Declaring a uniform does not prove the engine updates it.

Start with the unchanged target-version interface, then a distinct color, then selection of a marked object. Preserve ordinary draws. The inspected Charcoal stage recognizes atlas header/tint values before changing texture coordinates; its transferable mechanism is a reserved marker and neutral decode. Its legacy stage needs porting for 1.21.8.

In the inspected 1.21.8 LevelTargetBundle, the Fabulous transparency set includes main, translucent, item_entity, particles, weather and clouds. Those names are not automatically available on other routes. A namespace does not allocate a framebuffer. The linter records caller-supplied external target evidence and diagnoses unknown external resources.

## Intensity, cleanup and cost

The blur uses a BlurSettings block: vec2 Direction followed by float Intensity. Direction is normalized by textureSize; Intensity=0 returns the source. JSON changes require F3+T. Resource-pack code cannot read arbitrary server values; live control needs an evidenced transport and neutral missing-state value.

Two five-tap passes use ten texture reads per pixel. One full-size RGBA8 target is roughly 4×width×height bytes: 7.9 MiB at 1920×1080, excluding existing attachments and driver overhead. Half-width/half-height has one quarter of the pixels with different quality. Persistent history needs initialization and reset after resize/reload; these lessons have no history.

Check F5/observer views, F1, resize/aspect ratio, GUI scale, reload, visible/culled producer, missing state, removal, world change, graphics modes and competing pack order. Measure frame cost with and without the effect. Preserve failures and unrun matrix cells.

## Inspected local references

| Source | Files/mechanism examined | License and boundary |
|---|---|---|
| JNNGL/vanilla-shaders | README version matrix; custom_blur pack 34; position_tex menu handling, cutout encoding and blur graph | MIT present; historical module-specific versions |
| midorikuma/VariablesViewer | VariablesViewerRP pack 34; values.glsl selector, display.txt, generator docs | MIT present; Python/Pillow generator; historical interfaces |
| CloudWolfYT/ShaderSelectorV2 | README attribution and transparency sampler graph | CC0 present, but credits common-shaders; mechanism-only pending lineage review |
| HalbFettKaese/common-shaders | README and resourcepack layout | No root license found; reference-only, no code redistribution |
| ps-dps/mc-Charcoal | particle.vsh header/tint selection and atlas coordinates; setup docs | MIT present; legacy interface and particle override conflict |

No zip/jar/7z/rar files were found in the initial references tree. The official client JAR obtained for review is retained separately. No upstream material was deleted. Old visual_sources commit labels are preserved as provenance, not claimed to have been revalidated from a Git checkout. Local hashes are in verification/visual-reference-inventory.json.

## Version sources

- [24w34a / 1.21.2 changes](https://www.minecraft.net/en-us/article/minecraft-snapshot-24w34a): post paths and graph fields.
- [1.21.5](https://www.minecraft.net/en-us/article/minecraft-java-edition-1-21-5): program JSON removed.
- [1.21.6](https://www.minecraft.net/en-us/article/minecraft-java-edition-1-21-6): uniform blocks and persistent targets.
- [26.3 Snapshot 3](https://www.minecraft.net/en-us/article/minecraft-26-3-snapshot-3): /posteffect and always-on minecraft:end_of_frame, pack 91.0. Server success cannot prove client rendering.
- [26.3 Snapshot 8](https://www.minecraft.net/en-us/article/minecraft-26-3-snapshot-8): further text/OIT changes; do not generalize Snapshot 3 compatibility.

No future Denizen/DenizenM wrapper is assumed without an exact implementation/build. “Vision” is not a dCore subsystem; resolve the intended command, pack or effect from context.
