# Post-effect engineering

## Render graph

A post effect runs after ordinary scene rendering and reads framebuffer attachments. `minecraft:main` denotes the main rendered color target in the modern profile. A pass reads one or more input targets, runs a fullscreen program, and writes an output target. Multi-pass effects alternate main/swap or named targets; the final pass must return the composed result to the target expected by the profile.

Never read and write one attachment in the same pass without an explicit API guarantee. A typical two-pass structure is:

```text
minecraft:main -> swap       (effect or horizontal blur)
swap -> minecraft:main       (compose or vertical blur)
```

The screen quad supplies vertices for every pixel. Its vertex stage produces clip coordinates and UVs. Verify UV direction with a corner-color test before debugging the algorithm.

## `entity_outline` masks

`minecraft:entity_outline` can be sampled when that target exists and contains marked geometry in the active render graph. It can mask an effect: outline alpha selects pixels. It does not itself activate an arbitrary fullscreen post effect, create per-player server state, or guarantee that the target is populated in every graphics route.

## Time and size

`GameTime` and `ScreenSize` are useful only when the exact profile exposes and updates them. `GameTime` may wrap; use periodic math that tolerates wrap. Normalize pixel offsets by actual target dimensions. After resize, reacquire size from the engine-provided value; never cache stale dimensions in resource-pack-only code.

## Algorithms

### Temporal pulse envelope

Use a periodic phase and two narrow smooth pulses. With `phase = fract(time * beatsPerSecond)`:

```glsl
float pulse(float x, float center, float width) {
    float d = abs(x - center);
    return 1.0 - smoothstep(0.0, width, d);
}
float beat = max(pulse(phase, 0.08, 0.06), 0.72 * pulse(phase, 0.24, 0.07));
```

Multiply by an explicit level scalar. Keep the baseline at zero so removal or missing control is visually neutral.

### Vignette

Compute aspect-correct radius from screen center, then `smoothstep(inner, outer, radius)`. Tint or darken only the vignette contribution. Ensure edges do not clip abruptly at unusual aspect ratios.

### Chromatic aberration

Sample R/G/B at small opposing radial offsets. Normalize offsets by size and clamp UV. Keep level 1 near subpixel scale; large offsets are expensive and nauseating.

### Radial distortion

Map centered UV with `uv' = center + centered * (1 + k*r*r)`. Clamp or define border behavior. Couple `k` to the pulse envelope rather than accumulating it frame to frame.

### Blur

Use separable passes and a swap target. Horizontal then vertical taps reduce cost from a 2-D kernel. Record tap count, target resolution, and GPU/FPS delta. Avoid blur at zero intensity by selecting a bypass route when the profile allows it.

### Color grading

Apply exposure/contrast/saturation or a LUT after distortion/blur unless the desired composition says otherwise. Work in the profile's actual color space; do not claim linear-light correctness without evidence.

### Screen shake

Offset UV with bounded periodic/noise motion scaled by inverse target size. Return to zero on stop. Server-side player teleport is not a cosmetic post-process shake.

### Temporal effects

History requires a persistent target and explicit initialization/reset. Clear history on activation, resize, resource reload, world/dimension changes, and stop. A shader with no evidenced previous-frame attachment cannot implement true temporal accumulation.

## Composition order

State the order because results differ. A practical temporal-effect order is bounded distortion -> optional chromatic sampling -> source color -> tint/vignette -> final compose. Blur may precede grading. Keep each pass single-purpose until proof.
