// Max's animated character: one React component plus a small animation engine.
//
//   <MaxCharacter state="idle" size={160} />
//
// The body is an orange cartoon cloud (puffy bumps on top, wide soft base). It is ONE smooth SVG path,
// built from a soft union of circles and a rounded base, so bumps can jiggle after a move.
// The white pill eyes sit on an imaginary sphere, so they turn with a 3D feel.
// Motion uses springs (smooth blends, never snaps), squash & stretch that keeps volume,
// anticipation before jumps, follow-through, and a ground shadow that reacts to height.
// One requestAnimationFrame loop per instance; it pauses when off-screen or when the tab is hidden.
import { useEffect, useId, useLayoutEffect, useRef, useState, type CSSProperties } from "react";

export const MAX_COLOR = "#F7630C";

export const MAX_STATES = [
  "idle", "listening", "thinking", "speaking", "happy", "celebrate", "surprised", "sleepy",
  "confused", "sorry", "wink", "squint", "lookLeft", "lookRight", "lookUp", "lookDown",
] as const;
export type MaxState = (typeof MAX_STATES)[number];

export const MAX_STATE_INFO: Record<MaxState, { label: string; emoji: string }> = {
  idle: { label: "Idle", emoji: "😐" },
  listening: { label: "Listening", emoji: "👂" },
  thinking: { label: "Thinking", emoji: "🤔" },
  speaking: { label: "Speaking", emoji: "🗣️" },
  happy: { label: "Happy", emoji: "😊" },
  celebrate: { label: "Celebrate", emoji: "🎉" },
  surprised: { label: "Surprised", emoji: "😲" },
  sleepy: { label: "Sleepy", emoji: "😴" },
  confused: { label: "Confused", emoji: "😕" },
  sorry: { label: "Sorry", emoji: "😔" },
  wink: { label: "Wink", emoji: "😉" },
  squint: { label: "Squint", emoji: "😑" },
  lookLeft: { label: "Look left", emoji: "👈" },
  lookRight: { label: "Look right", emoji: "👉" },
  lookUp: { label: "Look up", emoji: "☝️" },
  lookDown: { label: "Look down", emoji: "👇" },
};

/** Seconds after entering a state where it shows its nicest frozen pose (used for screenshots). */
export const MAX_FREEZE_POSE: Record<MaxState, number> = {
  idle: 1.2, listening: 1.3, thinking: 1.5, speaking: 2.26, happy: 0.33, celebrate: 0.34, surprised: 0.2,
  sleepy: 2.6, confused: 1.4, sorry: 1.4, wink: 0.42, squint: 1.0, lookLeft: 1.1, lookRight: 1.1,
  lookUp: 1.1, lookDown: 1.1,
};

export interface MaxCharacterProps {
  state?: MaxState;
  /** Rendered width and height in px (20 to 400). At 40 px or less a simpler silhouette is used. */
  size?: number;
  /** Voice or mic level 0..1. While speaking, leave it undefined to use a built-in talk rhythm. */
  level?: number;
  followCursor?: boolean;
  color?: string;
  /** Render the idle pose without animation (static icons). */
  still?: boolean;
  /** Freeze the state at this many seconds after entering it (screenshots). */
  freezeAt?: number;
  /** Override the system "reduce motion" setting. */
  reducedMotion?: boolean;
  /** Darker ground shadow for dark backgrounds. */
  onDark?: boolean;
  title?: string;
  className?: string;
  style?: CSSProperties;
}

// ---------------------------------------------------------------- geometry (base centre = 0,0; y up is negative)

interface Circle { x: number; y: number; r: number }
// Base: a wide box with big round bottom corners, tiny top corners and a gentle bulge at the bottom.
// The outer bumps touch the base sides tangentially, so the side runs smoothly into the bumps.
const BASE = { cy: -59.5, hx: 149, hy: 50.5, r: 56, rTop: 4, bulge: 10 };
const BUMPS_FULL: Circle[] = [
  { x: -106, y: -114, r: 44 },
  { x: -38, y: -162, r: 58 },
  { x: 50, y: -160, r: 58 },
  { x: 110, y: -110, r: 40 },
];
const BUMPS_COMPACT: Circle[] = [
  { x: -98, y: -110, r: 52 },
  { x: -6, y: -160, r: 64 },
  { x: 96, y: -112, r: 54 },
];
const SMOOTH = 15;            // softness of the valleys between bumps
const SMOOTH_BASE = 8;        // softness where the bumps meet the base
const RAYS = 96;
const RAY_CY = -106;
const BODY_H = 222;           // height of the tallest bump above the ground
const FACE_Y = -94;
const SPHERE_R = 112;
const VIEW_FULL = "-200 -325 400 400";
const VIEW_TIGHT = "-160 -272 320 320";

const smin = (a: number, b: number, k: number) => {
  const h = Math.max(k - Math.abs(a - b), 0) / k;
  return Math.min(a, b) - h * h * k * 0.25;
};

function sdBase(x: number, y: number) {
  let py = y;
  if (y > BASE.cy) {
    const u = Math.min(1, (x / BASE.hx) ** 2);
    const ramp = Math.min(1, (y - BASE.cy) / BASE.hy);
    py = y - BASE.bulge * (1 - u) * ramp;   // gentle downward bulge in the middle of the base
  }
  const r = py > BASE.cy ? BASE.r : BASE.rTop;
  const qx = Math.abs(x) - BASE.hx + r;
  const qy = Math.abs(py - BASE.cy) - BASE.hy + r;
  return Math.hypot(Math.max(qx, 0), Math.max(qy, 0)) + Math.min(Math.max(qx, qy), 0) - r;
}

function sdCloud(x: number, y: number, bumps: Circle[], ox: number[], oy: number[]) {
  let d = 1e9;
  for (let i = 0; i < bumps.length; i++) {
    const b = bumps[i];
    d = smin(d, Math.hypot(x - b.x - ox[i], y - b.y - oy[i]) - b.r, SMOOTH);
  }
  return smin(sdBase(x, y), d, SMOOTH_BASE);
}

/** Outline as one smooth closed path: cast rays from the middle, find the outer edge, join with Catmull-Rom curves.
 *  `radii` (optional) holds last frame's edge distance per ray, so the search starts close to the answer. */
function cloudPath(bumps: Circle[], ox: number[], oy: number[], radii?: number[]) {
  const pts: [number, number][] = [];
  for (let i = 0; i < RAYS; i++) {
    const a = (i / RAYS) * Math.PI * 2;
    const dx = Math.cos(a), dy = Math.sin(a);
    let r = radii?.[i] !== undefined ? radii[i] + 18 : 250;
    while (r > 0 && sdCloud(dx * r, RAY_CY + dy * r, bumps, ox, oy) > 0) r -= 6;
    let lo = r, hi = r + 6;
    for (let j = 0; j < 9; j++) {
      const m = (lo + hi) / 2;
      if (sdCloud(dx * m, RAY_CY + dy * m, bumps, ox, oy) > 0) hi = m; else lo = m;
    }
    const rr = (lo + hi) / 2;
    if (radii) radii[i] = rr;
    pts.push([dx * rr, RAY_CY + dy * rr]);
  }
  const n = pts.length, f = (v: number) => v.toFixed(1);
  let d = `M${f(pts[0][0])} ${f(pts[0][1])}`;
  for (let i = 0; i < n; i++) {
    const p0 = pts[(i - 1 + n) % n], p1 = pts[i], p2 = pts[(i + 1) % n], p3 = pts[(i + 2) % n];
    d += `C${f(p1[0] + (p2[0] - p0[0]) / 6)} ${f(p1[1] + (p2[1] - p0[1]) / 6)} ${f(p2[0] - (p3[0] - p1[0]) / 6)} ${f(p2[1] - (p3[1] - p1[1]) / 6)} ${f(p2[0])} ${f(p2[1])}`;
  }
  return d + "Z";
}

const restPathCache = new Map<boolean, string>();
function restPath(compact: boolean) {
  let p = restPathCache.get(compact);
  if (!p) {
    const bumps = compact ? BUMPS_COMPACT : BUMPS_FULL;
    p = cloudPath(bumps, bumps.map(() => 0), bumps.map(() => 0));
    restPathCache.set(compact, p);
  }
  return p;
}

// ---------------------------------------------------------------- colours

function rgb(hex: string) {
  const n = parseInt(hex.replace("#", "").padEnd(6, "0").slice(0, 6), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}
function mix(hex: string, to: string, f: number) {
  const a = rgb(hex), b = rgb(to);
  return "#" + a.map((v, i) => Math.round(v + (b[i] - v) * f).toString(16).padStart(2, "0")).join("");
}
function luminance(hex: string) {
  const ch = rgb(hex).map((v) => {
    v /= 255;
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2];
}

// ---------------------------------------------------------------- poses

interface Pose {
  // eyes
  yaw: number; pitch: number; open: number; wide: number; wideX: number; happy: number; closed: number;
  lScale: number; rScale: number; lOpen: number; rOpen: number; lTilt: number; rTilt: number;
  lHappy: number; rHappy: number; lid: number; lidAngle: number;
  // body (lean = skew with the base planted, tilt = rock on the round bottom, degrees)
  lean: number; tilt: number; shift: number; sq: number; scale: number;
  breath: number; breathRate: number; swayLean: number; swayTilt: number; swayRate: number;
}
type PoseKey = keyof Pose;

const POSE0: Pose = {
  yaw: 0, pitch: 0, open: 1, wide: 1, wideX: 1, happy: 0, closed: 0,
  lScale: 1, rScale: 1, lOpen: 1, rOpen: 1, lTilt: 0, rTilt: 0, lHappy: 0, rHappy: 0, lid: 0, lidAngle: 0,
  lean: 0, tilt: 0, shift: 0, sq: 0, scale: 1,
  breath: 0.024, breathRate: 0.27, swayLean: 1.4, swayTilt: 0, swayRate: 0.13,
};

const STATE_POSE: Record<MaxState, Partial<Pose>> = {
  idle: {},
  listening: { wide: 1.1, pitch: 0.05, sq: 0.05, scale: 1.04, tilt: 4, breath: 0.016, swayLean: 0.4 },
  thinking: { yaw: 0.34, pitch: 0.4, open: 0.82, sq: 0.025, swayLean: 0, swayTilt: 5, swayRate: 0.2, breathRate: 0.22 },
  speaking: { sq: 0.01, swayLean: 1.8, swayRate: 0.32 },
  happy: { happy: 1, sq: 0.02, swayLean: 0, swayTilt: 3.5, swayRate: 0.85 },
  celebrate: { happy: 1, sq: 0.03, swayLean: 0, swayTilt: 4.5, swayRate: 1.0 },
  surprised: { wide: 1.32, wideX: 1.1, sq: 0.08, swayLean: 0, breath: 0.01 },
  sleepy: { closed: 1, pitch: -0.12, sq: -0.08, tilt: 5, breath: 0.055, breathRate: 0.17, swayLean: 0, swayTilt: 1.2, swayRate: 0.085 },
  confused: { lScale: 0.72, rScale: 1.1, lOpen: 0.75, pitch: 0.08, tilt: -7, shift: -4, swayLean: 0, swayTilt: 2.5, swayRate: 0.3 },
  sorry: { pitch: -0.3, open: 0.9, lid: 0.36, lidAngle: 22, sq: -0.07, scale: 0.92, tilt: 2, swayLean: 0.5, breathRate: 0.2 },
  wink: { rHappy: 1, lScale: 1.06, tilt: 8, yaw: 0.1, swayLean: 0.5 },
  squint: { open: 0.34, wideX: 1.2, lTilt: 7, rTilt: -7, sq: -0.04, swayLean: 0.6 },
  lookLeft: { yaw: -0.6, lean: -9, shift: -16, swayLean: 0.4 },
  lookRight: { yaw: 0.6, lean: 9, shift: 16, swayLean: 0.4 },
  lookUp: { pitch: 0.46, sq: 0.075, swayLean: 0.4 },
  lookDown: { pitch: -0.38, open: 0.86, sq: -0.055, swayLean: 0.4 },
};

// spring stiffness and damping ratio per pose key
const SPRING_OF: Record<PoseKey, [number, number]> = {
  yaw: [170, 0.62], pitch: [170, 0.62], open: [380, 0.75], wide: [260, 0.45], wideX: [200, 0.5],
  happy: [200, 0.7], closed: [120, 0.8], lScale: [180, 0.55], rScale: [180, 0.55], lOpen: [380, 0.75],
  rOpen: [380, 0.75], lTilt: [160, 0.6], rTilt: [160, 0.6], lHappy: [200, 0.7], rHappy: [200, 0.7],
  lid: [200, 0.7], lidAngle: [160, 0.7],
  lean: [95, 0.4], tilt: [80, 0.42], shift: [95, 0.45], sq: [150, 0.45], scale: [120, 0.55],
  breath: [12, 1], breathRate: [12, 1], swayLean: [10, 1], swayTilt: [10, 1], swayRate: [10, 1],
};

interface Spring { v: number; vel: number; k: number; c: number }
const spring = (v: number, k: number, zeta: number): Spring => ({ v, vel: 0, k, c: 2 * zeta * Math.sqrt(k) });
const stepSpring = (s: Spring, target: number, dt: number) => {
  s.vel += (s.k * (target - s.v) - s.c * s.vel) * dt;
  s.v += s.vel * dt;
};
const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
const easeOutBack = (p: number) => {
  p = clamp01(p);
  const c1 = 1.9, c3 = c1 + 1;
  return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2;
};
const easeOutCubic = (p: number) => 1 - (1 - clamp01(p)) ** 3;

/** Speech-like loudness: syllables inside phrases with small pauses. Deterministic in t. */
function voiceAmp(t: number) {
  const phrase = Math.sin(t * 0.9) + Math.sin(t * 1.7 + 1) > -0.6 ? 1 : 0;
  const syll = Math.max(0, Math.sin(t * 12.5)) ** 0.6;
  const vary = 0.55 + 0.45 * Math.sin(t * 3.1 + Math.sin(t * 1.3));
  return phrase * syll * vary;
}

function rng(seed: number) {
  let a = seed | 0;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ---------------------------------------------------------------- engine

const STEP = 1 / 120;
const GRAVITY = 2400;
const STAR = "M0 -15Q2.5 -2.5 15 0Q2.5 2.5 0 15Q-2.5 2.5 -15 0Q-2.5 -2.5 0 -15Z";
const QMARK = "M-13 -22C-13 -40 15 -40 15 -24C15 -12 1 -10 1 2";
const SPARK_COLORS = ["var(--max-sym)", "#FFB900", "var(--max-sym)", "#FFB900", "var(--max-sym)", "#FFB900", "var(--max-sym)", "#FFB900"];

interface EyeEls { g: SVGGElement; pill: SVGRectElement; arch: SVGPathElement; curve: SVGPathElement; lid: SVGRectElement }
interface Timed { el: SVGElement; born: number }
interface Spark extends Timed { ang: number; d0: number; d1: number; size: number; spin: number; x: number; y: number }

class Engine {
  private q = <T extends Element>(name: string) => this.svg.querySelector(`[data-p="${name}"]`) as T;
  private qa = <T extends Element>(name: string) => [...this.svg.querySelectorAll(`[data-p="${name}"]`)] as T[];
  private attrCache = new WeakMap<Element, Record<string, string>>();

  private body: SVGGElement; private path: SVGPathElement; private shadow: SVGEllipseElement | null;
  private eyes: EyeEls[]; private fx: SVGGElement | null; private rings: Timed[]; private zs: Timed[];
  private sparks: Spark[];
  private fxEls: Record<string, SVGElement | null>;
  private burst: SVGLineElement[]; private dots: SVGCircleElement[];

  private bumps: Circle[];
  private bx: number[]; private by: number[]; private bvx: number[]; private bvy: number[];
  private bk: number[]; private pathDirty = false; private radii: number[] = [];

  private P: Record<PoseKey, Spring>;
  private state: MaxState = "idle";
  private t = 0; private stateT = -10;
  private air = 0; private vy = 0; private airborne = false;
  private jig = spring(0, 330, 0.24); private jigTarget = 0; private hopScale: number;
  private actions: { at: number; fn: () => void }[] = [];
  private breathPhase = 0; private swayPhase = 0;
  private sacYaw = spring(0, 420, 0.85); private sacPitch = spring(0, 420, 0.85); private sac = { y: 0, p: 0 };
  private nextSaccade = 1.2; private nextBlink = 2.2; private blinkStart = -10; private doubleBlink = false;
  private nextBeat = 0; private amp = spring(0, 520, 0.9); private lvl = spring(0, 400, 0.9);
  private lastRing = -10; private ringIdx = 0; private zNext = 0; private zIdx = 0; private sparkIdx = 0;
  private prevTop = { x: 0, y: 0, vx: 0, vy: 0 };
  private rand = rng(7);

  // inputs
  level: number | undefined = undefined;
  follow = false;
  reduced = false;
  onDark = false;
  private mouse = { yaw: 0, pitch: 0 };
  private calm = false;                    // freeze/still: no random blinks or glances
  private entered = false;

  // loop
  private raf = 0; private last = 0; private acc = 0; private running = false; private destroyed = false;
  private visible = true; private onscreen = true; private io: IntersectionObserver | null = null;

  constructor(private svg: SVGSVGElement, private compact: boolean) {
    this.body = this.q("body"); this.path = this.q("path"); this.shadow = this.q("shadow");
    this.eyes = this.qa<SVGGElement>("eye").map((g) => ({
      g, pill: g.querySelector("[data-e=pill]")!, arch: g.querySelector("[data-e=arch]")!,
      curve: g.querySelector("[data-e=curve]")!, lid: g.querySelector("[data-e=lid]")!,
    }));
    this.fx = this.q("fx");
    this.rings = this.qa<SVGElement>("ring").map((el) => ({ el, born: -10 }));
    this.zs = this.qa<SVGElement>("z").map((el) => ({ el, born: -10 }));
    this.sparks = this.qa<SVGElement>("spark").map((el) => ({ el, born: -10, ang: 0, d0: 0, d1: 0, size: 1, spin: 0, x: 0, y: 0 }));
    this.fxEls = Object.fromEntries(["ex", "q1", "q2", "b1", "b2", "b3", "sweat"].map((k) => [k, this.q(k)]));
    this.burst = this.qa("burst"); this.dots = this.qa("dot");
    this.bumps = compact ? BUMPS_COMPACT : BUMPS_FULL;
    const n = this.bumps.length;
    this.bx = Array(n).fill(0); this.by = Array(n).fill(0); this.bvx = Array(n).fill(0); this.bvy = Array(n).fill(0);
    this.bk = [300, 260, 330, 280].slice(0, n);
    this.hopScale = compact ? 0.45 : 1;
    this.P = {} as Record<PoseKey, Spring>;
    for (const k of Object.keys(POSE0) as PoseKey[]) this.P[k] = spring(POSE0[k], SPRING_OF[k][0], SPRING_OF[k][1]);
    this.path.setAttribute("d", restPath(compact));
  }

  // ---------- public
  setState(name: MaxState) {
    if (name === this.state && this.entered) return;
    this.entered = true;
    this.enter(name);
  }
  setMouse(clientX: number, clientY: number) {
    const r = this.svg.getBoundingClientRect();
    const dx = (clientX - (r.left + r.width / 2)) / Math.max(40, r.width / 2);
    const dy = (clientY - (r.top + r.height / 2)) / Math.max(40, r.height / 2);
    this.mouse.yaw = Math.max(-0.65, Math.min(0.65, dx * 0.5));
    this.mouse.pitch = Math.max(-0.45, Math.min(0.45, -dy * 0.42));
  }
  renderStill() { this.calm = true; this.render(); }
  freeze(state: MaxState, at: number) {
    this.calm = true;
    for (let t = 0; t < 0.4; t += STEP) this.step(STEP);        // settle in idle first
    this.enter(state);
    const steps = Math.round(at / STEP);
    for (let i = 0; i < steps; i++) this.step(STEP);
    this.render();
  }
  start() {
    this.running = true;
    document.addEventListener("visibilitychange", this.onVisibility);
    if ("IntersectionObserver" in window) {
      this.io = new IntersectionObserver((es) => { this.onscreen = es.some((e) => e.isIntersecting); this.kick(); });
      this.io.observe(this.svg);
    }
    this.render();
    this.kick();
  }
  destroy() {
    this.destroyed = true;
    cancelAnimationFrame(this.raf);
    this.io?.disconnect();
    document.removeEventListener("visibilitychange", this.onVisibility);
  }

  // ---------- loop
  private onVisibility = () => { this.visible = !document.hidden; this.kick(); };
  private kick() {
    const go = this.running && !this.destroyed && this.visible && this.onscreen;
    if (go && !this.raf) { this.last = 0; this.raf = requestAnimationFrame(this.frame); }
    if (!go && this.raf) { cancelAnimationFrame(this.raf); this.raf = 0; }
  }
  private frame = (now: number) => {
    this.raf = 0;
    const dt = this.last ? Math.min(0.05, (now - this.last) / 1000) : 1 / 60;
    this.last = now;
    this.acc += dt;
    while (this.acc >= STEP) { this.step(STEP); this.acc -= STEP; }
    this.render();
    this.kick();
  };

  // ---------- behaviour
  private at(delay: number, fn: () => void) { this.actions.push({ at: this.t + delay, fn }); }

  /** Anticipation crouch, launch, flight under gravity; landing squash comes from the physics. Returns landing delay. */
  private hop(v0: number, crouch: number, delay = 0, onLaunch?: () => void) {
    if (this.reduced) return delay;
    const v = v0 * this.hopScale, h = v0 / 560;
    this.at(delay, () => { this.jigTarget = -0.14 * h; });
    this.at(delay + crouch, () => {
      this.jigTarget = 0;
      this.vy = v; this.airborne = true;
      this.jig.vel += 2.6 * h;
      onLaunch?.();
    });
    return delay + crouch + (2 * v) / GRAVITY;
  }

  private celebrateBurst() {
    if (this.compact) return;
    for (let i = 0; i < 6; i++) {
      const s = this.sparks[this.sparkIdx++ % this.sparks.length];
      s.born = this.t; s.x = 0; s.y = -150;
      s.ang = (-158 + i * 27 + (this.rand() - 0.5) * 12) * (Math.PI / 180);
      s.d0 = 110; s.d1 = 150 + this.rand() * 30; s.size = 0.7 + this.rand() * 0.5; s.spin = this.rand() < 0.5 ? -1 : 1;
    }
  }
  private winkSparkle() {
    if (this.compact) return;
    [[118, -168, 1], [146, -136, 0.6]].forEach(([x, y, size], i) => {
      const s = this.sparks[this.sparkIdx++ % this.sparks.length];
      s.born = this.t + i * 0.1; s.x = x; s.y = y; s.ang = 0; s.d0 = 0; s.d1 = 0; s.size = size; s.spin = 1;
    });
  }

  private enter(name: MaxState) {
    const prev = this.state;
    this.state = name;
    this.stateT = this.t;
    this.actions = [];
    this.jigTarget = 0;
    this.nextBeat = this.t + (name === "idle" ? 8 + this.rand() * 5 : 3.4);
    if (this.reduced) return;
    // anticipation: wind up against the coming lean/shift, the springs then overshoot a little (follow-through)
    const tgt = { ...POSE0, ...STATE_POSE[name] };
    this.P.lean.vel -= (tgt.lean - this.P.lean.v) * 5;
    this.P.shift.vel -= (tgt.shift - this.P.shift.v) * 5;
    this.P.tilt.vel -= (tgt.tilt - this.P.tilt.v) * 3;
    if (prev === name) return;
    switch (name) {
      case "happy": this.hop(470, 0.14); break;
      case "celebrate": {
        const land = this.hop(560, 0.13, 0, () => this.celebrateBurst());
        this.hop(470, 0.08, land, () => this.celebrateBurst());
        break;
      }
      case "surprised": this.hop(380, 0.05); break;
      case "wink": this.hop(250, 0.07, 0, () => this.winkSparkle()); break;
      case "listening": this.jig.vel += 1.4; break;
      case "sorry": this.jig.vel -= 1.6; break;
      case "confused": this.P.tilt.vel -= 30; break;
      case "lookUp": this.jig.vel += 1.2; break;
      case "lookDown": this.jig.vel -= 1.0; break;
      case "sleepy": this.zNext = this.t + 0.5; break;
      default: this.jig.vel += 0.6;
    }
  }

  private beat() {
    switch (this.state) {
      case "idle": {   // a small wiggle now and then
        const dir = this.rand() < 0.5 ? -1 : 1;
        this.at(0, () => { this.P.lean.vel += 70 * dir; this.jig.vel += 0.9; });
        this.at(0.14, () => { this.P.lean.vel -= 120 * dir; });
        this.at(0.3, () => { this.P.lean.vel += 70 * dir; });
        this.nextBeat = this.t + 10 + this.rand() * 4;
        return;
      }
      case "happy": this.hop(340, 0.1); this.nextBeat = this.t + 3.4; return;
      case "celebrate": {
        const land = this.hop(560, 0.13, 0, () => this.celebrateBurst());
        this.hop(470, 0.08, land, () => this.celebrateBurst());
        this.nextBeat = this.t + 3.8;
        return;
      }
      case "wink": this.winkSparkle(); this.nextBeat = this.t + 2.8; return;
      default: this.nextBeat = this.t + 1e9;
    }
  }

  private targets(): Pose {
    const p: Pose = { ...POSE0, ...STATE_POSE[this.state] };
    const st = this.t - this.stateT, t = this.t;
    if (this.state === "surprised") {
      const ph = st < 0.05 ? 0 : st < 0.24 ? 1 : 2;     // squeeze, pop, settle
      p.wide = [0.6, 1.7, 1.32][ph];
      p.wideX = [1.18, 1.22, 1.1][ph];
    }
    if (this.state === "confused") p.yaw = 0.22 * Math.sin(t * 1.2);
    if (this.state === "thinking") p.yaw += 0.06 * Math.sin(t * 0.8);
    if (this.state === "listening") p.wide += clamp01(this.lvl.v) * 0.3;
    if (this.follow) {
      p.yaw = this.mouse.yaw; p.pitch = this.mouse.pitch;
      p.lean += this.mouse.yaw * 9; p.shift += this.mouse.yaw * 8;
    } else {
      p.lean += this.sacYaw.v * 10; p.shift += this.sacYaw.v * 8;
    }
    if (this.reduced) {
      p.lean = 0; p.tilt = 0; p.shift = 0; p.swayLean = 0; p.swayTilt = 0;
      p.sq *= 0.5; p.scale = 1 + (p.scale - 1) * 0.5; p.breath *= 0.7;
    }
    return p;
  }

  private step(dt: number) {
    this.t += dt;
    const t = this.t;
    if (this.actions.length) {
      const due = this.actions.filter((a) => a.at <= t);
      if (due.length) { this.actions = this.actions.filter((a) => a.at > t); due.forEach((a) => a.fn()); }
    }
    if (t >= this.nextBeat && !(this.calm && this.state === "idle")) this.beat();

    // inputs
    stepSpring(this.lvl, this.state === "listening" || this.state === "speaking" ? clamp01(this.level ?? 0) : 0, dt);
    const speakSrc = this.state === "speaking" ? (this.level === undefined ? voiceAmp(t) : clamp01(this.level)) : 0;
    stepSpring(this.amp, speakSrc, dt);

    // glances
    const glancing = !this.calm && !this.follow && (this.state === "idle" || this.state === "speaking" || this.state === "listening");
    if (glancing && t > this.nextSaccade) {
      const back = this.rand() < 0.4;
      const range = this.state === "listening" ? 0.15 : 0.3;
      this.sac = back ? { y: 0, p: 0 } : { y: (this.rand() * 2 - 1) * range, p: (this.rand() * 2 - 1) * 0.12 };
      this.nextSaccade = t + 2 + this.rand() * 3;
    }
    if (!glancing) this.sac = { y: 0, p: 0 };
    stepSpring(this.sacYaw, this.sac.y, dt);
    stepSpring(this.sacPitch, this.sac.p, dt);

    // blinks every 3-6 s, sometimes double
    const canBlink = !this.calm && !["happy", "celebrate", "sleepy", "wink"].includes(this.state);
    if (canBlink && t > this.nextBlink) {
      this.blinkStart = t;
      this.doubleBlink = this.rand() < 0.18;
      this.nextBlink = t + 3 + this.rand() * 3;
    }
    if (this.doubleBlink && t - this.blinkStart > 0.26) { this.blinkStart = t; this.doubleBlink = false; }

    // pose springs
    const tgt = this.targets();
    for (const k in this.P) stepSpring(this.P[k as PoseKey], tgt[k as PoseKey], dt);
    this.breathPhase += Math.PI * 2 * this.P.breathRate.v * dt;
    this.swayPhase += Math.PI * 2 * this.P.swayRate.v * dt;

    // jumping
    if (this.airborne) {
      this.vy -= GRAVITY * dt;
      this.air += this.vy * dt;
      if (this.air <= 0) {
        this.jig.vel -= Math.min(3.4, Math.abs(this.vy) * 0.0062);   // landing squash
        this.air = 0; this.vy = 0; this.airborne = false;
      }
    }
    stepSpring(this.jig, this.jigTarget, dt);

    // secondary motion: bumps lag behind the top of the body, then jiggle back (too small to see in compact icons)
    if (!this.reduced && !this.compact) {
      const lean = (this.P.lean.v * Math.PI) / 180, tilt = (this.P.tilt.v * Math.PI) / 180;
      const topX = this.P.shift.v + 150 * (Math.tan(lean) + Math.sin(tilt));
      const topY = this.air + 150 * (this.jig.v + this.P.sq.v + this.amp.v * 0.09);
      const vx = (topX - this.prevTop.x) / dt, vyTop = (topY - this.prevTop.y) / dt;
      const ax = (vx - this.prevTop.vx) / dt, ay = (vyTop - this.prevTop.vy) / dt;
      this.prevTop = { x: topX, y: topY, vx, vy: vyTop };
      const C = 0.0016;
      for (let i = 0; i < this.bumps.length; i++) {
        const w = 0.8 + 0.4 * ((this.bumps[i].r - 40) / 26) + (i % 2) * 0.15;
        const k = this.bk[i], c = 2 * 0.2 * Math.sqrt(k);
        this.bvx[i] += (-k * this.bx[i] - c * this.bvx[i] - ax * C * w * 60) * dt;
        this.bvy[i] += (-k * this.by[i] - c * this.bvy[i] + ay * C * w * 60) * dt;
        this.bx[i] = Math.max(-12, Math.min(12, this.bx[i] + this.bvx[i] * dt));
        this.by[i] = Math.max(-12, Math.min(12, this.by[i] + this.bvy[i] * dt));
      }
      this.pathDirty = true;
    }

    // speaking rings, sleepy z's
    if (this.state === "speaking" && !this.reduced && this.amp.v > 0.35 && t - this.lastRing > 0.5) {
      const r = this.rings[this.ringIdx++ % Math.max(1, this.rings.length)];
      if (r) r.born = t;
      this.lastRing = t;
    }
    if (this.state === "sleepy" && t > this.zNext && this.zs.length) {
      this.zs[this.zIdx++ % this.zs.length].born = t;
      this.zNext = t + 1.0;
    }
  }

  // ---------- drawing
  private set(el: Element | null, name: string, v: string) {
    if (!el) return;
    let c = this.attrCache.get(el);
    if (!c) { c = {}; this.attrCache.set(el, c); }
    if (c[name] !== v) { c[name] = v; el.setAttribute(name, v); }
  }
  private op(el: Element | null, o: number) { this.set(el, "opacity", clamp01(o).toFixed(3)); }
  private tf(el: Element | null, x: number, y: number, s: number, r = 0) {
    this.set(el, "transform", `translate(${x.toFixed(2)} ${y.toFixed(2)}) rotate(${r.toFixed(2)}) scale(${Math.max(0.0001, s).toFixed(4)})`);
  }

  private render() {
    const P = this.P, t = this.t, st = t - this.stateT;
    const a = Math.max(0, this.amp.v), L = clamp01(this.lvl.v);

    // body shape
    if (this.pathDirty) {
      const moving = this.bx.some((v, i) => Math.abs(v) > 0.04 || Math.abs(this.by[i]) > 0.04);
      if (moving) this.set(this.path, "d", cloudPath(this.bumps, this.bx, this.by, this.radii));
      else this.set(this.path, "d", restPath(this.compact));
      this.pathDirty = false;
    }

    // squash & stretch (keeps area), lean, tilt
    const airStretch = Math.min(0.13, Math.abs(this.vy) / 4200);
    const listenPulse = this.state === "listening" ? L * 0.07 : 0;
    const breath = P.breath.v * Math.sin(this.breathPhase);
    const sq = Math.max(-0.3, Math.min(0.35, P.sq.v + this.jig.v + breath + a * 0.09 + airStretch + listenPulse));
    const yaw = P.yaw.v + (this.follow ? 0 : this.sacYaw.v);
    const sy = 1 + sq;
    const sx = (1 / sy) * (1 - Math.abs(yaw) * 0.03);
    const S = P.scale.v;
    const lean = P.lean.v + P.swayLean.v * Math.sin(this.swayPhase);
    const tilt = P.tilt.v + P.swayTilt.v * Math.sin(this.swayPhase) + (this.state === "speaking" ? a * 1.5 : 0);
    const shift = P.shift.v;
    this.set(this.body, "transform",
      `translate(${shift.toFixed(2)} ${(-this.air).toFixed(2)}) rotate(${tilt.toFixed(2)}) skewX(${(-lean).toFixed(2)}) scale(${(sx * S).toFixed(4)} ${(sy * S).toFixed(4)})`);

    // ground shadow: smaller and lighter when high up, wider when squashed
    if (this.shadow) {
      const lift = this.air;
      this.set(this.shadow, "transform", `translate(${(shift * 0.9).toFixed(2)} 0) scale(${(sx * S * (1 - lift / 330)).toFixed(4)} 1)`);
      this.op(this.shadow, (this.onDark ? 0.42 : 0.13) * (1 - lift / 240));
    }

    // eyes on an imaginary sphere
    const pitch = P.pitch.v + (this.follow ? 0 : this.sacPitch.v) + a * 0.04;
    const bp = (t - this.blinkStart) / 0.16;
    const blink = bp >= 0 && bp < 1 ? 1 - 0.92 * Math.sin(bp * Math.PI) : 1;
    const eyeK = this.compact ? 1.32 : 1;
    const baseYaw = this.compact ? 0.36 : 0.31;
    const EW = 32 * eyeK, EH = 61 * eyeK;
    [-1, 1].forEach((side, i) => {
      const e = this.eyes[i];
      if (!e) return;
      const isL = side < 0;
      const ey = yaw + side * baseYaw;
      const px = SPHERE_R * Math.sin(ey) * Math.cos(pitch);
      const py = FACE_Y - SPHERE_R * Math.sin(pitch) + (this.compact ? 4 : 0);
      const fxs = Math.max(0.25, Math.cos(ey)), fys = Math.max(0.25, Math.cos(pitch));
      const scale = isL ? P.lScale.v : P.rScale.v;
      const open = Math.max(0, P.open.v * (isL ? P.lOpen.v : P.rOpen.v) * blink);
      const tiltE = isL ? P.lTilt.v : P.rTilt.v;
      const happy = clamp01(P.happy.v + (isL ? P.lHappy.v : P.rHappy.v));
      const closed = clamp01(P.closed.v);
      const hide = Math.max(happy, closed);
      const w = EW * P.wideX.v * scale;
      const h = Math.max(3, EH * P.wide.v * open * scale * (1 + a * 0.1) * (1 - hide * 0.75));
      this.set(e.pill, "x", (-w / 2).toFixed(2));
      this.set(e.pill, "y", (-h / 2).toFixed(2));
      this.set(e.pill, "width", w.toFixed(2));
      this.set(e.pill, "height", h.toFixed(2));
      this.set(e.pill, "rx", (Math.min(w, h) / 2).toFixed(2));
      this.op(e.pill, 1 - hide);

      const aw = EW * 1.3 * scale, ah = 15 * scale * eyeK;
      this.set(e.arch, "d", `M${(-aw / 2).toFixed(1)} ${(ah * 0.55).toFixed(1)}Q0 ${(-ah * 1.35).toFixed(1)} ${(aw / 2).toFixed(1)} ${(ah * 0.55).toFixed(1)}`);
      this.set(e.arch, "stroke-width", (EW * 0.42 * scale).toFixed(2));
      this.op(e.arch, happy);
      const cw = EW * 1.4, ch = 12 * eyeK;
      this.set(e.curve, "d", `M${(-cw / 2).toFixed(1)} ${(-ch * 0.4).toFixed(1)}Q0 ${(ch * 1.1).toFixed(1)} ${(cw / 2).toFixed(1)} ${(-ch * 0.4).toFixed(1)}`);
      this.set(e.curve, "stroke-width", (EW * 0.38).toFixed(2));
      this.op(e.curve, closed * (1 - happy));

      // eyelid in body colour: droops for "sorry", flattens for "squint"
      const lid = clamp01(P.lid.v) * (1 - hide);
      this.set(e.lid, "x", (-w * 1.1).toFixed(2));
      this.set(e.lid, "width", (w * 2.2).toFixed(2));
      this.set(e.lid, "y", (-h / 2 - 16).toFixed(2));
      this.set(e.lid, "height", (16 + lid * h).toFixed(2));
      this.set(e.lid, "transform", `rotate(${(P.lidAngle.v * (isL ? -1 : 1)).toFixed(2)} 0 ${(-h / 2 + lid * h).toFixed(2)})`);
      this.op(e.lid, lid > 0.01 ? 1 : 0);

      this.set(e.g, "transform", `translate(${px.toFixed(2)} ${py.toFixed(2)}) scale(${fxs.toFixed(4)} ${fys.toFixed(4)}) rotate(${tiltE.toFixed(2)})`);
    });

    if (this.compact || !this.fx) return;

    // speaking rings
    this.rings.forEach((r) => {
      const age = t - r.born;
      if (age < 0 || age > 1.3) { this.op(r.el, 0); return; }
      const p = age / 1.3;
      this.set(r.el, "cx", shift.toFixed(1));
      this.set(r.el, "cy", (-108 - this.air).toFixed(1));
      this.set(r.el, "rx", (150 + p * 60).toFixed(1));
      this.set(r.el, "ry", (116 + p * 50).toFixed(1));
      this.op(r.el, 0.55 * (1 - p) * (1 - p * 0.3));
    });

    // symbols ride on the top of the body
    const leanR = (lean * Math.PI) / 180, tiltR = (tilt * Math.PI) / 180;
    const fxX = shift + 200 * (Math.tan(leanR) + Math.sin(tiltR)) * 0.8;
    const fxY = -this.air - BODY_H * (sy * S - 1);
    this.set(this.fx, "transform", `translate(${fxX.toFixed(2)} ${fxY.toFixed(2)})`);
    this.renderFx(t, st);
  }

  private renderFx(t: number, st: number) {
    const F = this.fxEls, s = this.state, still = this.reduced;
    // "!" pops with a wobble and burst lines
    const EX = [140, -236];
    if (s === "surprised") {
      const o = 1 - clamp01((st - 2.2) / 0.4);
      const sc = (still ? 1 : easeOutBack((st - 0.06) / 0.3)) * (0.6 + 0.4 * o);
      const wob = still ? 0 : 12 * Math.sin(st * 20) * Math.exp(-st * 3.5);
      this.tf(F.ex, EX[0], EX[1], sc, wob); this.op(F.ex, st > 0.06 ? o : 0);
    } else this.op(F.ex, 0);
    const angles = [-160, -126, -54, -20];
    this.burst.forEach((ln, i) => {
      if (s === "surprised" && !still && st > 0.06 && st < 0.7) {
        const p = (st - 0.06) / 0.6, an = (angles[i] * Math.PI) / 180;
        const r1 = 40 + p * 24, r2 = r1 + 16 * (1 - p) + 3;
        this.set(ln, "x1", (EX[0] + Math.cos(an) * r1).toFixed(1)); this.set(ln, "y1", (EX[1] - 22 + Math.sin(an) * r1).toFixed(1));
        this.set(ln, "x2", (EX[0] + Math.cos(an) * r2).toFixed(1)); this.set(ln, "y2", (EX[1] - 22 + Math.sin(an) * r2).toFixed(1));
        this.op(ln, 1 - p * p);
      } else this.op(ln, 0);
    });

    // "?" marks wobble
    if (s === "confused") {
      const m = still ? 0 : 1;
      const s1 = still ? 1 : easeOutBack((st - 0.05) / 0.35), s2 = still ? 1 : easeOutBack((st - 0.4) / 0.35);
      this.tf(F.q1, 136, -244 + 3 * Math.sin(t * 2.2) * m, s1, 12 * Math.sin(t * 2.4) * m);
      this.tf(F.q2, 96, -276 + 3 * Math.sin(t * 2 + 1) * m, 0.62 * s2, -14 * Math.sin(t * 2.1 + 1) * m);
      this.op(F.q1, st > 0.05 ? 1 : 0); this.op(F.q2, st > 0.4 ? 1 : 0);
    } else { this.op(F.q1, 0); this.op(F.q2, 0); }

    // thought bubble grows from the head, dots bounce
    if (s === "thinking") {
      const fl = still ? 0 : 2.5 * Math.sin(t * 1.6);
      const g1 = still ? 1 : easeOutBack(st / 0.25), g2 = still ? 1 : easeOutBack((st - 0.12) / 0.25), g3 = still ? 1 : easeOutBack((st - 0.24) / 0.35);
      this.tf(F.b1, 112, -214 + fl * 0.4, g1); this.op(F.b1, g1 > 0.01 ? 1 : 0);
      this.tf(F.b2, 132, -240 + fl * 0.7, g2); this.op(F.b2, g2 > 0.01 ? 1 : 0);
      this.tf(F.b3, 160, -276 + fl, g3); this.op(F.b3, g3 > 0.01 ? 1 : 0);
      this.dots.forEach((d, i) => {
        const bounce = still ? 0.5 : Math.max(0, Math.sin(t * 6.5 - i * 0.9));
        this.set(d, "cy", (2 - 5 * bounce).toFixed(2));
        this.op(d, 0.45 + 0.55 * bounce);
      });
    } else { this.op(F.b1, 0); this.op(F.b2, 0); this.op(F.b3, 0); }

    // z's float up and fade
    this.zs.forEach((z) => {
      const life = 2.8, age = t - z.born;
      if (s !== "sleepy" || age < 0 || age > life) { this.op(z.el, 0); return; }
      const p = age / life;
      this.tf(z.el, 104 + p * 62 + 7 * Math.sin(age * 3), -196 - p * 100, 0.6 + p * 1.0, -12 + 18 * p);
      this.op(z.el, Math.min(1, p / 0.15) * (1 - Math.max(0, (p - 0.6) / 0.4)));
    });

    // sweat drop for "sorry"
    if (s === "sorry") {
      const p = still ? 1 : easeOutCubic((st - 0.2) / 0.5);
      const slide = still ? 0 : 6 * Math.sin(t * 1.4);
      this.tf(F.sweat, -116, -190 + p * 10 + slide, 0.4 + 0.6 * p, -18);
      this.op(F.sweat, st > 0.2 ? p : 0);
    } else this.op(F.sweat, 0);

    // sparkles (celebrate burst, wink twinkle)
    this.sparks.forEach((sp) => {
      const age = t - sp.born, life = sp.d1 ? 0.95 : 1.1;
      if (age < 0 || age > life || (s !== "celebrate" && s !== "wink")) { this.op(sp.el, 0); return; }
      const p = age / life;
      const d = sp.d0 + (sp.d1 - sp.d0) * easeOutCubic(p);
      const x = sp.x + Math.cos(sp.ang) * d, y = sp.y + Math.sin(sp.ang) * d;
      const sc = easeOutBack(age / 0.25) * (1 - clamp01((p - 0.65) / 0.35)) * sp.size;
      this.tf(sp.el, x, y, sc, age * 160 * sp.spin);
      this.op(sp.el, 1);
    });
  }
}

// ---------------------------------------------------------------- React component

export function MaxCharacter({
  state = "idle", size = 160, level, followCursor = false, color = MAX_COLOR, still = false,
  freezeAt, reducedMotion, onDark = false, title = "Max", className, style,
}: MaxCharacterProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const engRef = useRef<Engine | null>(null);
  const uid = useId().replace(/[^a-zA-Z0-9]/g, "");
  const compact = size <= 40;
  const tight = compact || still;
  const frozen = freezeAt !== undefined;
  const sysReduced = useReducedMotionPref();
  const reduced = reducedMotion ?? sysReduced;

  // live values the engine reads every frame
  const live = useRef({ state, level, followCursor, reduced, onDark });
  live.current = { state, level, followCursor, reduced, onDark };

  useLayoutEffect(() => {
    const eng = new Engine(svgRef.current!, compact);
    engRef.current = eng;
    const l = live.current;
    eng.level = l.level; eng.follow = l.followCursor; eng.reduced = l.reduced; eng.onDark = l.onDark;
    if (still) { eng.renderStill(); }
    else if (frozen) { eng.freeze(l.state, freezeAt!); }
    else { eng.setState(l.state); eng.start(); }
    return () => { eng.destroy(); engRef.current = null; };
  }, [compact, still, frozen, freezeAt, frozen ? state : null, frozen ? level : null, frozen ? reduced : null]);

  useEffect(() => { if (!still && !frozen) engRef.current?.setState(state); }, [state, still, frozen]);
  useEffect(() => { if (engRef.current) engRef.current.level = level; }, [level]);
  useEffect(() => { if (engRef.current) engRef.current.reduced = reduced; }, [reduced]);
  useEffect(() => { if (engRef.current) engRef.current.onDark = onDark; }, [onDark]);
  useEffect(() => {
    if (engRef.current) engRef.current.follow = followCursor;
    if (!followCursor || still || frozen) return;
    const onMove = (e: PointerEvent) => engRef.current?.setMouse(e.clientX, e.clientY);
    window.addEventListener("pointermove", onMove);
    return () => window.removeEventListener("pointermove", onMove);
  }, [followCursor, still, frozen]);

  const light = luminance(color) > 0.55;
  const eyeCol = light ? "#1a1a1a" : "#ffffff";
  const sym = light ? mix(color, "#000000", 0.35) : color;
  const bubble = mix(color, "#ffffff", 0.8);
  const grad = `max-body-${uid}`;

  return (
    <svg
      ref={svgRef}
      viewBox={tight ? VIEW_TIGHT : VIEW_FULL}
      width={size}
      height={size}
      role="img"
      aria-label={title}
      className={className}
      style={{ display: "block", overflow: "visible", flexShrink: 0, ["--max-sym" as string]: sym, ...style }}
    >
      <defs>
        <linearGradient id={grad} gradientUnits="userSpaceOnUse" x1="0" y1={-BODY_H} x2="0" y2="-138">
          <stop offset="0" stopColor={mix(color, "#ffffff", 0.2)} />
          <stop offset="1" stopColor={color} />
        </linearGradient>
      </defs>
      {!tight && <ellipse data-p="shadow" cx="0" cy="3" rx="132" ry="11" fill="#000" opacity="0" />}
      {!compact && !still && (
        <g fill="none" stroke={color} strokeWidth="6">
          {[0, 1, 2, 3].map((i) => <ellipse key={i} data-p="ring" opacity="0" />)}
        </g>
      )}
      <g data-p="body">
        <path data-p="path" fill={`url(#${grad})`} />
        {[0, 1].map((i) => (
          <g key={i} data-p="eye">
            <rect data-e="pill" fill={eyeCol} />
            <path data-e="arch" fill="none" stroke={eyeCol} strokeLinecap="round" opacity="0" />
            <path data-e="curve" fill="none" stroke={eyeCol} strokeLinecap="round" opacity="0" />
            <rect data-e="lid" fill={color} opacity="0" />
          </g>
        ))}
      </g>
      {!compact && !still && (
        <g data-p="fx">
          {[0, 1, 2, 3].map((i) => <line key={i} data-p="burst" stroke="var(--max-sym)" strokeWidth="6" strokeLinecap="round" opacity="0" />)}
          <g data-p="ex" opacity="0" fill="var(--max-sym)">
            <rect x="-8.5" y="-44" width="17" height="36" rx="8.5" />
            <circle cx="0" cy="8.5" r="8.5" />
          </g>
          {["q1", "q2"].map((k) => (
            <g key={k} data-p={k} opacity="0">
              <path d={QMARK} fill="none" stroke="var(--max-sym)" strokeWidth="9" strokeLinecap="round" strokeLinejoin="round" />
              <circle cx="1" cy="17" r="5.5" fill="var(--max-sym)" />
            </g>
          ))}
          <circle data-p="b1" r="8" fill={bubble} opacity="0" />
          <circle data-p="b2" r="12" fill={bubble} opacity="0" />
          <g data-p="b3" opacity="0">
            <g fill={bubble}>
              <circle cx="-22" cy="2" r="22" /><circle cx="0" cy="-10" r="26" />
              <circle cx="22" cy="2" r="21" /><circle cx="0" cy="12" r="22" />
            </g>
            {[-15, 0, 15].map((x) => <circle key={x} data-p="dot" cx={x} cy="2" r="4.6" fill="var(--max-sym)" />)}
          </g>
          {[0, 1, 2, 3].map((i) => (
            <path key={i} data-p="z" d="M-7 -7H7L-7 7H7" fill="none" stroke="var(--max-sym)" strokeWidth="4.2"
              strokeLinecap="round" strokeLinejoin="round" opacity="0" />
          ))}
          <g data-p="sweat" opacity="0">
            <path d="M0 -16C6 -6 11 0 11 6A11 11 0 0 1 -11 6C-11 0 -6 -6 0 -16Z" fill="#7CC4F8" />
            <ellipse cx="-4" cy="5" rx="2.6" ry="4" fill="#ffffff" opacity="0.8" />
          </g>
          {SPARK_COLORS.map((c, i) => <path key={i} data-p="spark" d={STAR} fill={c} opacity="0" />)}
        </g>
      )}
    </svg>
  );
}

/** True when the system asks for less motion; follows live changes. */
function useReducedMotionPref() {
  const get = () => typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  const [reduced, setReduced] = useState(get);
  useEffect(() => {
    const q = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    if (!q) return;
    const on = () => setReduced(q.matches);
    q.addEventListener("change", on);
    return () => q.removeEventListener("change", on);
  }, []);
  return reduced;
}
