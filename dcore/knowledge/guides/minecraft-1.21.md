# Minecraft 1.21.x compatibility profile

Minecraft 1.21.x is not one shader format. Pin the patch and resource-pack format. In 1.21.2-era pack formats, post-effect definitions moved from `assets/<namespace>/shaders/post` to `assets/<namespace>/post_effect`; their programs moved under `assets/<namespace>/shaders/post`, and graph fields changed to namespaced `program`, `inputs`, `output`, and mapped `targets`.

The modern definition format existing in a resource pack did **not** provide a general server command for applying any custom namespaced effect before the 26.3 `/posteffect` route. A custom JSON file being valid is not an activation path.

Priority targets are **1.21.11 and 1.21.8** within the full 1.16.5–26.2 stable-client inventory. 1.21.5 removes program JSON and uses direct stages; 1.21.6 onward uses uniform blocks. 1.21.11 resource format is 75.0 and its post passes use `minecraft:core/screenquad` with a vertex-ID fullscreen triangle. A custom `in vec3 Position` post vertex shader from 1.21.8 is not a valid drop-in replacement. The pack section uses `min_format`/`max_format` (integer or `[major, minor]`); 1.21.8 uses format 64. See [the workbench](visual-workbench.md) for complete 1.21.8 packs.

## Available routes

| Route | What it can do | What it cannot honestly claim |
|---|---|---|
| title/bossbar/actionbar/custom-font overlay | UI-layer tint or imagery | true post-processing of scene color/depth |
| pumpkin/GUI texture overlay | screen-space overlay under its UI rules | arbitrary shader algorithm or universal F1 behavior |
| core shader override + marker/carrier | unsupported render-route manipulation with per-viewer encodings | stable supported API or collateral-free fullscreen trigger |
| hardcoded vanilla post-effect trigger | use an effect the client already activates for a vanilla condition | arbitrary custom namespaced activation |
| 1.21.8 `entity_outline` route | glowing mask and main-color sampling; non-spectator trigger | arbitrary namespaced command, server state, or guaranteed carrier visibility |
| client mod | explicit runtime/API, uniforms, packets, effects | resource-pack-only deployment |

Choose based on requirements. If the requirement is real post-processing on arbitrary server command with no client mod, state that 1.21.x lacks the 26.3 native route. The workbench demonstrates a hardcoded non-spectator route with different constraints. Offer an overlay when its semantics meet the task.

## Legacy proof requirements

Core overrides require route census and exact client files. Test marked/unmarked controls, hand/inventory/world collateral, F1, F5, GUI scale, resize, graphics modes, pack order/reload, and multiplayer viewer isolation. Record the installed pack list because another pack can replace the same `minecraft` shader.

Do not port the 26.3 example by only changing `pack_format`: activation and shader/compiler interfaces differ.

## Attachment failures

Mount establishes an entity relationship; it does not prove camera-relative projection. Moving a carrier to eye_location every server tick can trail rapid client camera movement. Increasing view_range, using negative scale or changing pivot does not establish full FOV coverage. Clip-space vertex placement cannot prevent the CPU from culling the carrier before the shader runs.

Verify the final route, carrier submission, marker decode and scene composition separately. A red probe confirms only its own pass. No compiler errors do not prove visible pixels. The ordinary pass must hide a control marker while the decoding pass still receives valid state; an invisible discarded texture can break both. Do not assume ordinary item Color carries glow_color. Keep viewer ownership and independent effect channels intact through reconnect, stop and reload. Test attack/use rays as well as FOV 30/110, full pitch/yaw, F1/F5, GUI scale and resize.

The inventories in dcore/lint/shader_profiles.py cover 34 official stable clients from 1.16.5 through 26.2 with download SHA-1 checked. They prove asset existence, not rendering. The metadata format follows the [official 25w31a change](https://www.minecraft.net/en-us/article/minecraft-snapshot-25w31a). No new effect implementation is included in these repairs.
