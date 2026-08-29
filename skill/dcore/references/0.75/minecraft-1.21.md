# Minecraft 1.21.x compatibility profile

Minecraft 1.21.x is not one shader format. Pin the patch and resource-pack format. In 1.21.2-era pack formats, post-effect definitions moved from `assets/<namespace>/shaders/post` to `assets/<namespace>/post_effect`; their programs moved under `assets/<namespace>/shaders/post`, and graph fields changed to namespaced `program`, `inputs`, `output`, and mapped `targets`.

The modern definition format existing in a resource pack did **not** provide a general server command for applying any custom namespaced effect before the 26.3 `/posteffect` route. A custom JSON file being valid is not an activation path.

## Honest fallback routes

| Route | What it can do | What it cannot honestly claim |
|---|---|---|
| title/bossbar/actionbar/custom-font overlay | UI-layer tint or imagery | true post-processing of scene color/depth |
| pumpkin/GUI texture overlay | screen-space overlay under its UI rules | arbitrary shader algorithm or universal F1 behavior |
| core shader override + marker/carrier | unsupported render-route manipulation with per-viewer encodings | stable supported API or collateral-free fullscreen trigger |
| hardcoded vanilla post-effect trigger | use an effect the client already activates for a vanilla condition | arbitrary custom namespaced activation |
| `entity_outline` mask | mask pixels when outline target is populated | magic fullscreen activation or arbitrary server state |
| client mod | explicit runtime/API, uniforms, packets, effects | resource-pack-only deployment |

Choose based on requirements. If the requirement is real post-processing on arbitrary server command with no client mod, state that 1.21.x lacks the 26.3 native route. Offer an overlay only if the user accepts overlay semantics.

## Legacy proof requirements

Core overrides require route census and exact client files. Test marked/unmarked controls, hand/inventory/world collateral, F1, F5, GUI scale, resize, graphics modes, pack order/reload, and multiplayer viewer isolation. Record the installed pack list because another pack can replace the same `minecraft` shader.

Do not port the 26.3 example by only changing `pack_format`: activation and shader/compiler interfaces differ.
