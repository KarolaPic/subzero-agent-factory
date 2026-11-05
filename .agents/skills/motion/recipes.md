# Recipes

Code for the motion rules in `SKILL.md`. Swap the literal values for the project's tokens where they exist.

## Route transitions

```tsx
<AnimatePresence initial={false} mode="wait">
  <motion.div
    key={pathname}
    initial={{ opacity: 0 }}
    animate={{ opacity: 1 }}
    exit={{ opacity: 0 }}
    transition={{ duration: 0.15, ease: [0.77, 0, 0.175, 1] }}
  >
    {children}
  </motion.div>
</AnimatePresence>
```

Opacity only, no `x`, `y` or `scale`. With `initial={false}` the first page renders in place and only later switches fade.

## Curves and durations

```css
:root {
  --ease-out: cubic-bezier(0.23, 1, 0.32, 1);
  --ease-in-out: cubic-bezier(0.77, 0, 0.175, 1);
  --ease-drawer: cubic-bezier(0.32, 0.72, 0, 1);
}
```

| Motion | Duration | Curve |
| --- | --- | --- |
| Hover colour | Instant | None |
| Press and hover movement | `150ms` | `--ease-out` |
| Tooltip | `125ms` | `--ease-out` |
| Toggle or small state change | `200ms` | `--ease-out` |
| Modal or popover entering | `200ms` | `--ease-out` |
| Modal or popover leaving | `150ms` | `--ease-out` |
| Panel or drawer entering | `400ms` | `--ease-drawer` |
| Panel or drawer leaving | `350ms` | `--ease-drawer` |
| Staged entrance | `100ms` between parts | `--ease-out` |
| Page change under `mode="wait"` | `150ms` each way | `--ease-in-out` |
| Toast | `200ms` | `--ease-out` |
| Progress bar | `100ms` per step | `linear` |
| Drag release | Spring | `stiffness: 500, damping: 30` |

In Motion, pass the same curves as arrays, such as `ease: [0.23, 1, 0.32, 1]`.

Similar controls share one duration. A spring that visibly oscillates, such as `stiffness: 1000` with `damping: 5`, is too loose.

## Drag release

```tsx
const x = useMotionValue(0);

function onDragEnd(_: PointerEvent, info: PanInfo) {
  animate(x, 0, {
    type: "spring",
    stiffness: 500,
    damping: 30,
    velocity: info.velocity.x,
  });
}

<motion.div drag="x" style={{ x }} onDragEnd={onDragEnd} />;
```

The built-in `drag` inertia already carries velocity. This is for a release the code animates itself.

## Flick to dismiss

```ts
const DISMISS_DISTANCE = 120;
const DISMISS_VELOCITY = 0.11;

function shouldDismiss(distance: number, startedAt: number) {
  const velocity = Math.abs(distance) / (Date.now() - startedAt);
  return Math.abs(distance) >= DISMISS_DISTANCE || velocity > DISMISS_VELOCITY;
}

function dampen(overshoot: number) {
  return Math.sign(overshoot) * Math.sqrt(Math.abs(overshoot)) * 4;
}
```

Run `dampen` on the distance dragged past a boundary, so the sheet slows rather than stopping. Call `setPointerCapture` on pointer-down and ignore a second pointer while one is dragging.

## Icon swap

```tsx
<AnimatePresence mode="popLayout" initial={false}>
  <motion.span
    key={copied ? "check" : "copy"}
    initial={{ opacity: 0, scale: 0.25, filter: "blur(4px)" }}
    animate={{ opacity: 1, scale: 1, filter: "blur(0px)" }}
    exit={{ opacity: 0, scale: 0.25, filter: "blur(4px)" }}
    transition={{ type: "spring", duration: 0.3, bounce: 0 }}
  >
    {copied ? <CheckIcon /> : <CopyIcon />}
  </motion.span>
</AnimatePresence>
```

Keep `bounce` at `0`. Without a motion library, keep both icons in the DOM and cross-fade them over `300ms` with `cubic-bezier(0.2, 0, 0, 1)`. An icon that changes on every hover or tab switch swaps instantly instead.

## Icon morph

```tsx
const reduce = useReducedMotion();
const paths = copied ? checkPaths : copyPaths;

<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.5} aria-hidden>
  {paths.map((d, index) => (
    <motion.path
      key={index}
      initial={false}
      animate={{ d }}
      transition={reduce ? { duration: 0 } : { duration: 0.24, ease: [0.77, 0, 0.175, 1] }}
    />
  ))}
</svg>
```

Both icons share one morph form, so path `index` in one meets path `index` in the other. Key the paths by index, never by icon, or they remount instead of morphing. Under reduced motion, wrap the swap in the cross-fade above. Without a motion library, `transition: d 240ms cubic-bezier(0.77, 0, 0.175, 1)` morphs in browsers that animate `d`. Elsewhere it swaps at once.

## Exits

```tsx
<AnimatePresence mode="popLayout">
  {items.map((item) => (
    <motion.li
      key={item.id}
      layout
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{
        opacity: 0,
        scale: 0.96,
        transition: { duration: 0.15, ease: [0.23, 1, 0.32, 1] },
      }}
      transition={{ duration: 0.2, ease: [0.23, 1, 0.32, 1] }}
    />
  ))}
</AnimatePresence>
```

Key by id, never by index, or the wrong item exits. A reordering list uses `mode="popLayout"` so the leaving item drops out of flow. Under `mode="sync"`, take the leaving element out of flow yourself.

Nested `AnimatePresence` sets `propagate`, or children vanish when the parent exits. Keep parent and child exit durations close.

Inside an exiting child, `useIsPresent` turns off interaction, as in `disabled={!isPresent}`. Async cleanup uses `usePresence` and calls `safeToRemove` when it finishes.

## Container bounds

```tsx
function AnimatedHeight({ children }: { children: React.ReactNode }) {
  const [node, setNode] = useState<HTMLDivElement | null>(null);
  const [height, setHeight] = useState(0);

  useEffect(() => {
    if (!node) return;
    const observer = new ResizeObserver(([entry]) => {
      setHeight(entry.contentRect.height);
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, [node]);

  return (
    <motion.div
      animate={{ height: height > 0 ? height : "auto" }}
      transition={{ duration: 0.2, delay: 0.05 }}
      style={{ overflow: "hidden" }}
    >
      <div ref={setNode}>{children}</div>
    </motion.div>
  );
}
```

The callback ref attaches the observer when the node mounts. The `auto` guard stops the first frame growing from zero. When the outer node collapses to `0`, give the inner node its open size, such as `width: 256px`, so its content does not reflow. Keep this for content that changes size, such as a label swap or an accordion, not for static sections.

## Motion blur

```sh
npm install @web-kits/motion-blur
```

The element that moves is the host. Its first child is the layer, which holds everything visible.

```tsx
import { useMotionBlur } from "@web-kits/motion-blur/react";

const blur = useMotionBlur();

<motion.div ref={blur.ref} animate={{ x: open ? 320 : 0 }}>
  <div className="card-face">…</div>
</motion.div>;
```

Without React it is one call, `motionBlur(element)`. CSS transitions, CSS animations, the Web Animations API and inline transform changes are picked up on their own.

`MotionBlurProvider` sets the technique, shutter and reduced motion for a tree. Options on a blur win, and `shutter={0}` on a provider turns off every blur inside it.

```tsx
import { echo } from "@web-kits/motion-blur";
import { MotionBlurProvider } from "@web-kits/motion-blur/react";

<MotionBlurProvider technique={echo({ spacing: 1 })} shutter={270}>
  <App />
</MotionBlurProvider>;
```

| Technique | Options | Draws |
| --- | --- | --- |
| `echo()` | `spacing = 1.5`, `copies = 16` | Copies of the layer along the path, added with `plus-lighter` |
| `squeeze()` | `factor = 16` | One CSS blur stretched along the motion |
| `svg()` | | `feGaussianBlur` along one axis, turned to the motion |
| `smear()` | `limit = 1.05` | The layer stretched along the motion, with no blur |

## Motion blur by hand

For a physics loop or any position you work out yourself, call `render` once a frame. The first call stops the automatic watching.

```ts
blur.render(previous, current);
```

When the motion bends, pass a path. `t` is in frames, so `path(-0.5)` is half a frame back.

```ts
element.style.transform = at(angle).toString();
blur.render((t) => at(angle + t * speed * frameTime));
```

## Custom technique

```ts
import { sigmaFor, type Technique } from "@web-kits/motion-blur";

const soft: Technique = ({ layer }) => ({
  paint({ dx, dy }) {
    layer.style.filter = `blur(${sigmaFor(Math.hypot(dx, dy))}px)`;
  },
  clear() {
    layer.style.removeProperty("filter");
  },
});
soft.key = "soft";
```

Each frame carries `path(t)`, `matrix`, `dx` and `dy` in the element's own px, `streak` in screen px, and `origin`, `width` and `height`.

## Checking motion blur

Freeze the motion at its fastest point, with a ¼× control or a paused timeline. At that point:

- Sideways motion keeps its top and bottom edges sharp, and only the leading and trailing edges soften.
- Echo shows no steps at the streak length you ship.
- The streak at 60Hz is twice as long as at 120Hz.
- Nothing stays blurred once the element stops.

`onFrame` reports the streak length in px each frame. A background tab throttles `requestAnimationFrame` and stretches every streak, so check in a focused tab.
