# Core shader pipeline

## Route census first

A core shader is selected by Minecraft's render pipeline and vertex format, not by a filename that sounds relevant. Inspect the final merged pack and the exact client JAR/profile. Inventory every overridden core program, source stage, include, attribute, sampler, uniform, and affected vanilla draw. Prove the route with a harmless unique output before adding screen math.

Mojang describes core-shader overriding as unsupported resource-pack behavior; internal programs can change between versions. Prefer a supported post-effect route when the target provides one.

## Vertex and fragment stages

The vertex stage receives attributes required by the selected vertex format. JSON declarations and GLSL inputs must agree in name, type, and route. It transforms object/world/view data to clip coordinates. The fragment stage samples textures, applies color/fog/masks, and emits framebuffer color/depth. Interpolated varyings must match across stages; `flat` values must match qualifiers.

Do not guess available globals. `GameTime`, `ScreenSize`, matrices, fog values, and samplers are profile-specific. Prove they exist in the exact program definition or generated interface. A declared uniform with a default is not proof that the engine updates it every frame.

## Coordinates and NDC

Clip position is divided by `w` to normalized device coordinates. Visible NDC is normally `x,y` in `[-1,1]`; depth range depends on backend/profile. A fullscreen screen quad should map its provided vertex position to clip space and derive UV consistently. Validate Y orientation and half-texel behavior with a quadrant test.

Aspect-correct radial math:

```glsl
vec2 centered = uv - 0.5;
centered.x *= ScreenSize.x / max(ScreenSize.y, 1.0);
float radius = length(centered);
```

If `ScreenSize` is not evidenced, derive from an evidenced target-size uniform. Do not hardcode 16:9.

## Samplers and uniforms

Each sampler needs a producer, binding name, filter/wrap assumption, and color/depth interpretation. Each uniform needs type, count, default, update owner, and target profile. Avoid read/write feedback: a pass should not sample the same attachment it writes unless the API explicitly defines it. Use a swap target for composition.

## Blend, depth, and culling

- Blend combines source and destination. An ordinary copy pass uses source replacement; alpha tint often uses source-alpha/one-minus-source-alpha. State syntax is version-specific.
- Depth test/write determines occlusion. Fullscreen post passes typically operate on color targets and should not accidentally write scene depth.
- Culling removes triangles by winding. A reversed or differently generated screen quad can disappear when culling is enabled.

Record state rather than assuming vanilla defaults. Test translucent and Fabulous/OIT routes separately when relevant.

## Core-route proof ladder

1. No-op replacement reproduces vanilla.
2. Unique constant color proves the exact draw route.
3. Marked and unmarked controls prove selection.
4. Clip/NDC transform proves screen placement.
5. Inventory, hand, world, GUI, F1/F5, transparency, graphics modes, resize, and reload reveal collateral.
6. Client logs and FPS capture complete runtime evidence.

Stop at the first failed layer. Do not hide a route failure behind entity loops or marker encodings.
