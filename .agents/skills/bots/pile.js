// A pile of bot marks as soft bodies: they drop in, collide on their real outlines, squash like jelly, follow a drag and scatter on a shake. Needs matter-js.
// Copy beside the component. createPile({ stage, pieces, hulls }) takes the stage element, one absolutely placed element per bot and each bot's markHull from marks.js.
// It returns { shake, bounds, wake, destroy }. Every value in PILE is tuned on a 300px stage of 25 bots, so keep them as written.

import Matter from "matter-js";

const { Bodies, Body, Composite, Constraint, Engine, Events, Sleeping, Vertices } = Matter;

export const PILE = {
  gravity: 1.05,
  restitution: 0.38,
  friction: 0.14,
  frictionAir: 0.018,
  sleepThreshold: 36,
  // Contact squash per unit of overlap, capped so a buried bot never folds.
  squash: 3,
  maxSquash: 0.3,
  // Stretch along the velocity, per px a frame.
  stretch: 0.016,
  maxStretch: 0.18,
  jellyStiffness: 0.22,
  jellyDamping: 0.74,
  maxSpeed: 24,
  // Closing speeds in px a frame. Soft blinks, hard spins, loud is full volume.
  softHit: 1.2,
  hardHit: 4.5,
  loudHit: 6,
  bumpGap: 300,
  soundGap: 60,
  tapSlop: 6,
  grip: { stiffness: 0.16, damping: 0.1 },
  shakeJolt: 18,
  shakeGap: 1000,
  settleSteps: 720,
};

function seeded(start) {
  let seed = start;
  return () => {
    seed += 0x6d2b79f5;
    let t = seed;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// The largest mark size, from 40px to 90px, whose rows still fit the stage.
function plan(width, height, count) {
  const pad = 14;
  let size = 40;
  let columns = 1;
  for (let next = 40; next <= 90; next++) {
    const radius = next * 0.46;
    const span = width - pad * 2 - next;
    const cols = Math.max(1, Math.floor(span / (radius * 2 + 3)));
    if (Math.ceil(count / cols) * (radius * 2 + 3) <= height - pad * 2) {
      size = next;
      columns = cols;
    }
  }
  return {
    size,
    columns,
    radius: size * 0.46,
    minX: pad + size / 2,
    maxX: width - pad - size / 2,
    maxY: height - pad - size / 2,
  };
}

// iOS asks for motion access only from inside a gesture, so request() runs on the Shake Bots tap.
function watchShake(onShake) {
  if (typeof DeviceMotionEvent === "undefined") return { request() {}, stop() {} };
  const permission = DeviceMotionEvent.requestPermission;
  let previous = null;
  let shookAt = 0;
  let listening = false;
  const motion = (event) => {
    const g = event.accelerationIncludingGravity;
    if (!g) return;
    const current = [g.x ?? 0, g.y ?? 0, g.z ?? 0];
    const before = previous;
    previous = current;
    if (!before) return;
    const jolt = Math.hypot(current[0] - before[0], current[1] - before[1], current[2] - before[2]);
    const now = performance.now();
    if (jolt < PILE.shakeJolt || now - shookAt < PILE.shakeGap) return;
    shookAt = now;
    onShake();
  };
  const listen = () => {
    if (listening) return;
    listening = true;
    window.addEventListener("devicemotion", motion);
  };
  if (!permission) listen();
  return {
    request() {
      if (listening || !permission) return;
      permission
        .call(DeviceMotionEvent)
        .then((state) => state === "granted" && listen())
        .catch(() => {});
    },
    stop() {
      window.removeEventListener("devicemotion", motion);
    },
  };
}

/**
 * hulls: one convex outline per piece in viewBox units, centred on `center` and `span` wide.
 * on.bump(index, hard) fires per bot on impact. on.sound(strength) fires at most every 60ms.
 * on.grab() fires on pointerdown, the moment to unlock audio. on.pick(index | null) fires on a tap.
 * on.frame() fires after every drawn frame, the moment to place a name label with bounds(index).
 * canStart() holds the first drop, such as until a fade-in ends. Call wake() when it may have changed.
 */
export function createPile({ stage, pieces, hulls, center, span, on = {}, canStart = () => true }) {
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const coarse = window.matchMedia("(pointer: coarse)").matches;
  const width = stage.clientWidth;
  const height = stage.clientHeight;
  const { size, columns, radius, minX, maxX, maxY } = plan(width, height, pieces.length);
  const rand = seeded(42);

  const engine = Engine.create({
    enableSleeping: true,
    gravity: { x: 0, y: PILE.gravity, scale: 0.001 },
    positionIterations: 14,
    velocityIterations: 8,
  });
  const walls = [
    Bodies.rectangle(width / 2, maxY + radius + 40, width + 80, 80, { isStatic: true }),
    Bodies.rectangle(minX - radius - 40, height / 2, 80, height * 4, { isStatic: true }),
    Bodies.rectangle(maxX + radius + 40, height / 2, 80, height * 4, { isStatic: true }),
  ];

  const scale = size / span;
  const outlines = hulls.map((hull) =>
    Vertices.clockwiseSort(hull.map(([x, y]) => ({ x: (x - center) * scale, y: (y - center) * scale }))),
  );
  // Bodies sit on their hull's centroid, not the mark's centre, so drawing pulls this offset back out.
  const offsets = outlines.map((outline) => Vertices.centre(outline));
  const bodies = pieces.map((_, index) => {
    const column = index % columns;
    const row = Math.floor(index / columns);
    const x = minX + ((column + 0.5) / columns) * (maxX - minX) + (rand() - 0.5) * 3;
    const body = Body.create({
      restitution: PILE.restitution,
      friction: PILE.friction,
      frictionAir: PILE.frictionAir,
      slop: 0,
      sleepThreshold: PILE.sleepThreshold,
      vertices: outlines[index],
      position: { x: Math.min(maxX, Math.max(minX, x)), y: -radius * 3 - row * (radius * 2 + 8) - rand() * 12 },
      angle: (rand() - 0.5) * 1.4,
    });
    Body.setAngularVelocity(body, (rand() - 0.5) * 0.12);
    return body;
  });
  Composite.add(engine.world, [...walls, ...bodies]);

  const cleanup = [];
  const listen = (target, type, handler) => {
    target.addEventListener(type, handler);
    cleanup.push(() => target.removeEventListener(type, handler));
  };

  // Jelly is a symmetric 2x2 matrix [p q; q r] per bot, sprung toward the squash its contacts ask for.
  const slots = new Map(bodies.map((body, index) => [body.id, index]));
  const jelly = bodies.map(() => ({ p: 1, q: 0, r: 1, vp: 0, vq: 0, vr: 0 }));
  const pressure = bodies.map(() => ({ p: 0, q: 0, r: 0 }));
  const press = (index, x, y, depth) => {
    const slot = pressure[index];
    if (!slot) return;
    slot.p += depth * x * x;
    slot.q += depth * x * y;
    slot.r += depth * y * y;
  };

  const draw = (instant = false) => {
    for (const slot of pressure) slot.p = slot.q = slot.r = 0;
    for (const pair of engine.pairs.list) {
      if (!pair.isActive) continue;
      const { normal, depth } = pair.collision;
      const d = Math.min(depth / radius, 0.5);
      press(slots.get(pair.bodyA.id), normal.x, normal.y, d);
      press(slots.get(pair.bodyB.id), normal.x, normal.y, d);
    }

    pieces.forEach((node, index) => {
      const body = bodies[index];
      const shape = jelly[index];
      const push = pressure[index];
      const centre = offsets[index];
      const load = push.p + push.r;
      const squash = load * PILE.squash > PILE.maxSquash ? PILE.maxSquash / load : PILE.squash;
      let tp = 1 - squash * push.p;
      let tq = -squash * push.q;
      let tr = 1 - squash * push.r;
      const { x: vx, y: vy } = body.velocity;
      const speed = Math.hypot(vx, vy);
      if (speed > 0.01) {
        const s = Math.min(speed * PILE.stretch, PILE.maxStretch);
        tp += (s * vx * vx) / speed ** 2;
        tq += (s * vx * vy) / speed ** 2;
        tr += (s * vy * vy) / speed ** 2;
      }

      if (instant) {
        Object.assign(shape, { p: tp, q: tq, r: tr, vp: 0, vq: 0, vr: 0 });
      } else {
        shape.vp = (shape.vp + (tp - shape.p) * PILE.jellyStiffness) * PILE.jellyDamping;
        shape.vq = (shape.vq + (tq - shape.q) * PILE.jellyStiffness) * PILE.jellyDamping;
        shape.vr = (shape.vr + (tr - shape.r) * PILE.jellyStiffness) * PILE.jellyDamping;
        shape.p += shape.vp;
        shape.q += shape.vq;
        shape.r += shape.vr;
      }
      // Clamped and normalised to a determinant of 1, so a squashed bot keeps its area and never turns inside out.
      shape.p = Math.min(1.3, Math.max(0.7, shape.p));
      shape.q = Math.min(0.3, Math.max(-0.3, shape.q));
      shape.r = Math.min(1.3, Math.max(0.7, shape.r));
      const area = 1 / Math.sqrt(Math.max(shape.p * shape.r - shape.q ** 2, 0.2));
      const p = shape.p * area;
      const q = shape.q * area;
      const r = shape.r * area;
      const cos = Math.cos(body.angle);
      const sin = Math.sin(body.angle);
      const a = p * cos + q * sin;
      const b = q * cos + r * sin;
      const c = q * cos - p * sin;
      const d = r * cos - q * sin;
      const x = body.position.x - (a * centre.x + c * centre.y) - size / 2;
      const y = body.position.y - (b * centre.x + d * centre.y) - size / 2;
      node.style.width = `${size}px`;
      node.style.height = `${size}px`;
      node.style.transform = `translate3d(${x.toFixed(2)}px, ${y.toFixed(2)}px, 0) matrix(${[a, b, c, d].map((v) => v.toFixed(4)).join(", ")}, 0, 0)`;
    });
    on.frame?.();
  };

  const wobbling = () => jelly.some((s) => Math.abs(s.vp) + Math.abs(s.vq) + Math.abs(s.vr) > 0.0005);

  // Upward and sideways only, so the pile jumps inside the stage instead of leaving it.
  const scatter = () => {
    on.pick?.(null);
    for (const body of bodies) {
      Sleeping.set(body, false);
      Body.setVelocity(body, { x: (Math.random() - 0.5) * 12, y: -(3 + Math.random() * 4) });
      Body.setAngularVelocity(body, (Math.random() - 0.5) * 0.4);
    }
  };

  let moved = false;
  let picked = null;
  const pick = (index) => {
    picked = index;
    on.pick?.(index);
  };
  pieces.forEach((node, index) => {
    listen(node, "click", () => {
      if (!moved) pick(picked === index ? null : index);
    });
  });
  listen(stage, "click", (event) => {
    if (pieces.some((node) => node.contains(event.target))) return;
    if (event.target.closest("a, button")) return;
    pick(null);
  });

  let visible = false;
  let shakeNow = () => {};
  const motion = watchShake(() => {
    if (visible || reduced) shakeNow();
  });
  cleanup.push(motion.stop);

  const api = {
    shake() {
      if (coarse) motion.request();
      shakeNow();
    },
    bounds(index) {
      return bodies[index]?.bounds ?? null;
    },
    wake() {},
    destroy() {
      for (const undo of cleanup) undo();
      Composite.clear(engine.world, false);
      Engine.clear(engine);
    },
  };

  // Reduced motion: run the drop offline and draw the settled pile once. A shake reshuffles instantly.
  if (reduced) {
    const settle = () => {
      for (let step = 0; step < PILE.settleSteps; step++) Engine.update(engine, 1000 / 60);
      for (const body of bodies) Sleeping.set(body, true);
      draw(true);
    };
    settle();
    shakeNow = () => {
      scatter();
      settle();
    };
    return api;
  }

  const felt = bodies.map(() => Number.NEGATIVE_INFINITY);
  let heard = Number.NEGATIVE_INFINITY;
  const hit = (event) => {
    const now = performance.now();
    let loudest = 0;
    for (const { bodyA, bodyB, collision } of event.pairs) {
      const { normal } = collision;
      const speed = Math.abs(
        (bodyA.velocity.x - bodyB.velocity.x) * normal.x + (bodyA.velocity.y - bodyB.velocity.y) * normal.y,
      );
      if (speed < PILE.softHit) continue;
      loudest = Math.max(loudest, speed);
      for (const body of [bodyA, bodyB]) {
        const index = slots.get(body.id);
        if (index === undefined || now - felt[index] < PILE.bumpGap) continue;
        felt[index] = now;
        on.bump?.(index, speed > PILE.hardHit);
      }
    }
    if (loudest && now - heard > PILE.soundGap) {
      heard = now;
      on.sound?.(Math.min(1, loudest / PILE.loudHit));
    }
  };
  Events.on(engine, "collisionStart", hit);
  cleanup.push(() => Events.off(engine, "collisionStart", hit));

  let frame = 0;
  let last = 0;
  let drag = null;
  const stop = () => {
    cancelAnimationFrame(frame);
    frame = 0;
  };
  cleanup.push(stop);
  const loop = (now) => {
    const dt = last ? Math.min(now - last, 32) : 1000 / 60;
    last = now;
    if (drag) Sleeping.set(drag.body, false);
    Engine.update(engine, dt);
    for (const body of bodies) {
      if (Body.getSpeed(body) > PILE.maxSpeed) Body.setSpeed(body, PILE.maxSpeed);
    }
    draw();
    if (!drag && !wobbling() && bodies.every((body) => body.isSleeping)) return stop();
    frame = requestAnimationFrame(loop);
  };
  const start = () => {
    if (frame) return;
    last = 0;
    frame = requestAnimationFrame(loop);
  };
  shakeNow = () => {
    scatter();
    start();
  };

  // The drag is a spring, not a teleport, and the world keeps stepping, so the held bot shoves its neighbours.
  const point = (event) => {
    const box = stage.getBoundingClientRect();
    return {
      x: Math.min(maxX, Math.max(minX, event.clientX - box.left)),
      y: Math.min(maxY, Math.max(radius, event.clientY - box.top)),
    };
  };
  const release = () => {
    if (!drag) return;
    Composite.remove(engine.world, drag.grip);
    delete drag.node.dataset.dragging;
    drag = null;
  };
  pieces.forEach((node, index) => {
    listen(node, "pointerdown", (event) => {
      if (event.button !== 0) return;
      const body = bodies[index];
      on.grab?.();
      release();
      moved = false;
      const here = point(event);
      const grip = Constraint.create({
        pointA: here,
        bodyB: body,
        pointB: { x: here.x - body.position.x, y: here.y - body.position.y },
        length: 0,
        ...PILE.grip,
      });
      Composite.add(engine.world, grip);
      drag = { body, node, grip, pointer: event.pointerId, x: event.clientX, y: event.clientY };
      node.dataset.dragging = "";
      Sleeping.set(body, false);
      node.setPointerCapture(event.pointerId);
      start();
    });
  });
  listen(stage, "pointermove", (event) => {
    if (!drag || event.pointerId !== drag.pointer) return;
    if (Math.hypot(event.clientX - drag.x, event.clientY - drag.y) > PILE.tapSlop) moved = true;
    drag.grip.pointA = point(event);
  });
  const up = (event) => {
    if (drag && event.pointerId === drag.pointer) release();
  };
  listen(stage, "pointerup", up);
  listen(stage, "pointercancel", up);

  api.wake = () => {
    if (visible && !frame && canStart()) start();
  };
  const observer = new IntersectionObserver(([entry]) => {
    visible = Boolean(entry?.isIntersecting);
    if (visible) api.wake();
    else stop();
  });
  observer.observe(stage);
  cleanup.push(() => observer.disconnect());

  return api;
}
