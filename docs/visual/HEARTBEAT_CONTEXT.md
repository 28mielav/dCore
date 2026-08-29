# Heartbeat visual test context

## Status
The previous Antigravity implementation is not runtime-proven. Treat all claims of successful deployment or working post-processing as unverified.

## Original objective
Build a minimal DenizenM heartbeat effect inspired by the Iron’s Spells `heartstop` visual: three intensity levels, animated heartbeat/pulse, optional vignette, start/stop command, and a resource pack. The first test must be simple and visibly undeniable.

## Evidence from the previous session
- Antigravity created `effects.dsc` and a resource pack named `vEngine_ResourcePack_1.21.11`.
- It attempted a GPU pipeline using `entity_outline.json`, `screen_shake`, `blit`, and a text shader hook.
- It used an invisible/glowing `item_display` carrier in front of the player camera.
- The server log contained a real error: `brightness=15` was passed as an invalid MapTag and interrupted carrier spawning.
- `/ex reload` also reported that `on script reload` was not a valid ScriptEvent in that file.
- Later messages claimed `iazip`, `ex reload`, and deployment succeeded, but no client shader log or gameplay capture proves the effect worked.

## Technical diagnosis
A glowing entity does not automatically execute an arbitrary fullscreen shader. It only contributes to the entity-outline buffer. A real post-effect must be loaded and executed by the client render pipeline.

For modern Minecraft formats, verify the exact target version. The newer format uses:
- `assets/minecraft/post_effect/<name>.json`
- fragment programs in `assets/minecraft/shaders/post/`
- current post-effect pass schema with `vertex_shader`, `fragment_shader`, `inputs`, `targets`, and `output`.

The old implementation used `assets/minecraft/shaders/post/entity_outline.json` and `shaders/program/*`, so it may be incompatible with the target client. The text shader route is a GUI/world-pass overlay, not proof of framebuffer post-processing.

## Required rebuild rules
1. Discover exact Minecraft, Paper, DenizenM, ItemsAdder/visual-mod versions before coding.
2. Inspect current upstream/client format and local reference packs.
3. Build a minimal constant red-tint or UV-shift test first.
4. Prove the effect in F1, GUI Scale 1/2/3/4, window resize, F5, and `/reload`.
5. Only after that add heartbeat animation and levels 1-3.
6. Do not claim deployment, reload, or client activation without literal command output/log evidence.
7. Keep static lint and runtime verification separate.
8. Use `start` and `stop` commands; cleanup must remove carriers/state on stop, death, quit, and reload.

## Current files to inspect
- `C:/Users/Admin/Desktop/Denizen/result/complex/libs/vEngine/effects.dsc`
- `C:/Users/Admin/Desktop/Denizen/result/temp/vEngine_ResourcePack_1.21.11/`
- `C:/Users/Admin/Desktop/dCore/repository/temp/gemini-shader-pack/`
- `C:/Users/Admin/Desktop/dCore/references/examples/CameraRoll.zip`
- `C:/Users/Admin/Desktop/dCore/references/examples/Darkness.zip`

## dCore verification
Run `dcore_start`, then `dcore_retrieve`, `dcore_lint`, `dcore_lint_pack`, `dcore_project_audit`, and `dcore_shader_review`. Report `STATIC_OK` and `RUNTIME_UNVERIFIED` separately.
