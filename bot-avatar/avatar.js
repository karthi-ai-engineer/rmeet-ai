/*
 * Cloud Avatar engine (reusable).
 *
 *   const avatar = CloudAvatar.create(containerEl, { background: 'light' });
 *   avatar.setState('thinking');      // see CloudAvatar.ORDER for all states
 *   avatar.setColour('#1E88FF');
 *   avatar.setLevel(0.6);             // mic level 0..1 (used by the "listening" state)
 *
 * Flat 2D cloud body; the eyes are projected onto an imaginary sphere so they
 * move with a 3D feel. Manga-style symbols (! ? z ✦ thought bubble) for emotions.
 */
(function () {
  'use strict';

  // ---------- Geometry ----------
  const CX = 200, CY = 214;         // face centre
  const R = 110;                    // radius of the imaginary sphere the eyes sit on
  const BASE_YAW = 0.28;            // eye spacing (radians around the sphere)
  const EYE_W = 26, EYE_H = 50;     // capsule eye size

  // ---------- Expressions ----------
  const DEFAULTS = {
    yaw: 0, pitch: 0, open: 1, wide: 1, wideX: 1, happy: 0, closed: 0, headTilt: 0,
    lScale: 1, rScale: 1, lOpen: 1, rOpen: 1, lTilt: 0, rTilt: 0, lHappy: 0, rHappy: 0,
  };
  const EXPR = {
    idle:      {},
    listening: { wide: 1.06, pitch: 0.04 },
    lookLeft:  { yaw: -0.58 },
    lookRight: { yaw: 0.58 },
    lookUp:    { pitch: 0.42 },
    lookDown:  { pitch: -0.36, open: 0.85 },
    surprised: { wide: 1.32, wideX: 1.1 },
    squint:    { open: 0.3, wideX: 1.2, lTilt: 6, rTilt: -6 },
    thinking:  { yaw: 0.34, pitch: 0.38, open: 0.8 },
    speaking:  {},
    happy:     { happy: 1 },
    sleepy:    { closed: 1, pitch: -0.1, headTilt: 3 },
    confused:  { lScale: 0.7, rScale: 1.1, lOpen: 0.7, headTilt: -7, pitch: 0.08 },
    wink:      { rHappy: 1, lScale: 1.06, headTilt: 8, yaw: 0.08 },
  };
  const ORDER = [
    ['idle', '😐', 'Idle'],
    ['listening', '👂', 'Listening'],
    ['lookLeft', '👈', 'Look left'],
    ['lookRight', '👉', 'Look right'],
    ['lookUp', '☝️', 'Look up'],
    ['lookDown', '👇', 'Look down'],
    ['surprised', '😲', 'Surprised'],
    ['squint', '😑', 'Squint'],
    ['thinking', '🤔', 'Thinking'],
    ['speaking', '🗣️', 'Speaking'],
    ['happy', '😊', 'Happy'],
    ['sleepy', '😴', 'Sleepy'],
    ['confused', '😕', 'Confused'],
    ['wink', '😉', 'Wink'],
  ];
  const COLOURS = [
    '#FF6B00', '#1E88FF', '#00C875', '#FF4FA3', '#8B5CF6', '#FF3B30',
    '#00B8C4', '#FFC400', '#7A7A7A', '#111111', '#8E5B33',
  ];

  const STAR = 'M 0 -15 Q 2.5 -2.5 15 0 Q 2.5 2.5 0 15 Q -2.5 2.5 -15 0 Q -2.5 -2.5 0 -15 Z';
  const QMARK = 'M -13 -22 C -13 -40 15 -40 15 -24 C 15 -12 1 -10 1 2';
  const EYE = `
    <g class="av-eye">
      <rect/>
      <path class="arch" fill="none" stroke-linecap="round"/>
      <path class="curve" fill="none" stroke-linecap="round"/>
    </g>`;
  const Q = `
      <path d="${QMARK}" fill="none" stroke-width="9" stroke-linecap="round"
            stroke-linejoin="round" style="stroke:var(--sym)"/>
      <circle cx="1" cy="17" r="5.5" style="fill:var(--sym)"/>`;

  const SVG_MARKUP = `
  <svg viewBox="0 0 400 400" role="img" aria-label="Animated cloud avatar" data-avatar
       style="width:100%;height:auto;display:block;overflow:visible;touch-action:none;stroke:none;stroke-width:0;--sym:#FF6B00;--bubOut:#ffffff">
    <ellipse class="av-shadow" cx="200" cy="356" rx="115" ry="12" fill="#000" opacity="0.07"/>
    <g class="av-rings"></g>
    <g class="av-body">
      <g class="av-cloud">
        <circle cx="200" cy="208" r="100"/>
        <circle cx="114" cy="232" r="62"/>
        <circle cx="288" cy="230" r="64"/>
        <circle cx="138" cy="148" r="58"/>
        <circle cx="238" cy="126" r="66"/>
        <circle cx="302" cy="168" r="50"/>
        <circle cx="172" cy="282" r="58"/>
        <circle cx="250" cy="284" r="55"/>
      </g>
      <g class="av-eyes">${EYE}${EYE}</g>
    </g>
    <g class="av-fx">
      <g class="av-burst" stroke-width="6" stroke-linecap="round" fill="none" style="stroke:var(--sym)">
        <line/><line/><line/><line/>
      </g>
      <g class="av-exclaim" opacity="0" style="fill:var(--sym)">
        <rect x="-8.5" y="-44" width="17" height="36" rx="8.5"/>
        <circle cx="0" cy="8.5" r="8.5"/>
      </g>
      <g class="av-q1" opacity="0">${Q}</g>
      <g class="av-q2" opacity="0">${Q}</g>
      <g class="av-b1" opacity="0">
        <circle r="9.5" style="fill:var(--bubOut)"/><circle r="7" fill="#fff"/>
      </g>
      <g class="av-b2" opacity="0">
        <circle r="12.5" style="fill:var(--bubOut)"/><circle r="10" fill="#fff"/>
      </g>
      <g class="av-b3" opacity="0">
        <g style="fill:var(--bubOut)">
          <circle cx="-23" cy="0" r="25"/><circle cx="-1" cy="-12" r="29"/>
          <circle cx="23" cy="0" r="23"/><circle cx="1" cy="12" r="25"/>
        </g>
        <g fill="#fff">
          <circle cx="-23" cy="0" r="22"/><circle cx="-1" cy="-12" r="26"/>
          <circle cx="23" cy="0" r="20"/><circle cx="1" cy="12" r="22"/>
        </g>
        <circle class="dot" cx="-17" cy="2" r="4.8" style="fill:var(--sym)"/>
        <circle class="dot" cx="0" cy="2" r="4.8" style="fill:var(--sym)"/>
        <circle class="dot" cx="17" cy="2" r="4.8" style="fill:var(--sym)"/>
      </g>
      <g class="av-z" fill="none" stroke-width="4.2" stroke-linecap="round"
         stroke-linejoin="round" style="stroke:var(--sym)"></g>
      <path class="av-s1" opacity="0" d="${STAR}" style="fill:var(--sym)"/>
      <path class="av-s2" opacity="0" d="${STAR}" style="fill:var(--sym)"/>
    </g>
  </svg>`;

  // ---------- Helpers ----------
  const NS = 'http://www.w3.org/2000/svg';
  const clamp01 = (x) => Math.max(0, Math.min(1, x));
  const easeOutBack = (p) => {
    p = clamp01(p);
    const c1 = 1.9, c3 = c1 + 1;
    return 1 + c3 * Math.pow(p - 1, 3) + c1 * Math.pow(p - 1, 2);
  };
  const tf = (el, x, y, s, r = 0) => el.setAttribute('transform',
    `translate(${x.toFixed(2)} ${y.toFixed(2)}) rotate(${r.toFixed(2)}) scale(${Math.max(0.0001, s).toFixed(4)})`);
  const op = (el, o) => el.setAttribute('opacity', clamp01(o).toFixed(3));
  const mk = (v, k, zeta) => ({ v, vel: 0, k, c: 2 * zeta * Math.sqrt(k) });
  const step = (s, target, dt) => {
    const a = s.k * (target - s.v) - s.c * s.vel;
    s.vel += a * dt;
    s.v += s.vel * dt;
  };
  function rgb(hex) {
    const n = parseInt(hex.slice(1), 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }
  function luminance(hex) {
    const ch = rgb(hex).map((v) => {
      v /= 255;
      return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2];
  }
  function darken(hex, f) {
    return '#' + rgb(hex).map((v) => Math.round(v * (1 - f)).toString(16).padStart(2, '0')).join('');
  }
  function voiceAmp(t) {
    const phrase = (Math.sin(t * 0.9) + Math.sin(t * 1.7 + 1)) > -0.6 ? 1 : 0;
    const syll = Math.pow(Math.max(0, Math.sin(t * 12.5)), 0.6);
    const vary = 0.55 + 0.45 * Math.sin(t * 3.1 + Math.sin(t * 1.3));
    return phrase * syll * vary;
  }

  // ---------- Factory ----------
  function create(container, opts = {}) {
    container.innerHTML = SVG_MARKUP;
    const svg = container.querySelector('svg');
    const q = (sel) => svg.querySelector(sel);
    const qa = (sel) => [...svg.querySelectorAll(sel)];

    const body = q('.av-body'), cloud = q('.av-cloud');
    const ringsG = q('.av-rings'), shadow = q('.av-shadow');
    const eyes = qa('.av-eye').map((g) => ({
      g, rect: g.querySelector('rect'), arch: g.querySelector('.arch'), curve: g.querySelector('.curve'),
    }));
    const rings = Array.from({ length: 4 }, () => {
      const c = document.createElementNS(NS, 'circle');
      c.setAttribute('fill', 'none');
      c.setAttribute('stroke-width', '5');
      c.setAttribute('opacity', '0');
      ringsG.appendChild(c);
      return { el: c, born: -10 };
    });
    const fx = {
      root: q('.av-fx'),
      burst: qa('.av-burst line'),
      ex: q('.av-exclaim'),
      q1: q('.av-q1'), q2: q('.av-q2'),
      b1: q('.av-b1'), b2: q('.av-b2'), b3: q('.av-b3'),
      dots: qa('.av-b3 .dot'),
      s1: q('.av-s1'), s2: q('.av-s2'),
    };
    const zs = Array.from({ length: 4 }, () => {
      const p = document.createElementNS(NS, 'path');
      p.setAttribute('d', 'M -7 -7 H 7 L -7 7 H 7');
      p.setAttribute('opacity', '0');
      q('.av-z').appendChild(p);
      return { el: p, born: -10 };
    });

    // Springs
    const S = {};
    for (const key in DEFAULTS) {
      const fast = key.includes('pen');                // open / lOpen / rOpen
      S[key] = mk(DEFAULTS[key], fast ? 380 : 160, fast ? 0.75 : 0.6);
    }
    S.wide = mk(1, 260, 0.45);
    const sacYaw = mk(0, 420, 0.85), sacPitch = mk(0, 420, 0.85);
    const bodyY = mk(0, 220, 0.35);
    const amp = mk(0, 520, 0.9);
    const lvl = mk(0, 400, 0.9);
    const P = { ex: mk(0, 300, 1), q: mk(0, 300, 1), b: mk(0, 300, 1), z: mk(0, 200, 1), sp: mk(0, 300, 1) };

    // State
    let state = 'idle', stateStart = 0, T = 0;
    let colour = opts.colour || COLOURS[0];
    let bg = opts.background || 'light';
    let autoIdle = opts.autoIdle !== false, follow = !!opts.follow;
    let level = 0;
    let onState = opts.onState || null;
    let mouseYaw = 0, mousePitch = 0;
    let nextBlink = 1.5, blinkStart = -10, doubleBlink = false;
    let nextSaccade = 1, sacTarget = { y: 0, p: 0 };
    let lastRing = 0, ringIdx = 0;
    let hops = [];
    let zNext = 0, zIdx = 0;
    let sparkNext = 0, sparkBorn = -10;
    const t0 = performance.now() / 1000;
    let last = 0, alive = true;

    function updateSymbolColour() {
      const L = luminance(colour);
      let sym = colour;
      if (bg === 'meeting' && L < 0.06) sym = '#ffffff';
      else if (bg !== 'meeting' && L > 0.5) sym = darken(colour, 0.35);
      svg.style.setProperty('--sym', sym);
      svg.style.setProperty('--bubOut', bg === 'light' ? '#e3e3e3' : '#ffffff');
    }
    function setColour(hex) {
      colour = hex;
      cloud.setAttribute('fill', hex);
      const eyeCol = luminance(hex) > 0.55 ? '#1a1a1a' : '#ffffff';
      eyes.forEach((e) => {
        e.rect.setAttribute('fill', eyeCol);
        e.arch.setAttribute('stroke', eyeCol);
        e.curve.setAttribute('stroke', eyeCol);
      });
      rings.forEach((r) => r.el.setAttribute('stroke', hex));
      updateSymbolColour();
    }
    function setBackground(name) { bg = name; updateSymbolColour(); }

    function setState(name) {
      if (!EXPR[name]) return;
      const prev = state;
      state = name;
      stateStart = T;
      if (onState) onState(name);
      if (name === prev) return;
      if (name === 'surprised') { bodyY.vel += 160; hops.push({ at: T + 0.08, v: -440 }); }
      if (name === 'happy') hops = [{ at: T, v: -260 }, { at: T + 0.38, v: -260 }];
      if (name === 'confused') bodyY.vel -= 120;
      if (name === 'wink') { hops.push({ at: T + 0.05, v: -220 }); sparkNext = T + 0.12; }
      if (name === 'sleepy') zNext = T + 0.5;
    }

    function updateFx(t, st, dt, lx, ly) {
      fx.root.setAttribute('transform', `translate(${lx.toFixed(2)} ${ly.toFixed(2)})`);

      // Surprise: "!" pops with wobble, burst lines flash
      if (state === 'surprised') {
        const o = 1 - clamp01((st - 1.8) / 0.4);
        const s = easeOutBack((st - 0.08) / 0.32) * (0.6 + 0.4 * o);
        const wob = 12 * Math.sin(st * 20) * Math.exp(-st * 3.5);
        tf(fx.ex, 326, 72, s, wob); op(fx.ex, st > 0.08 ? o : 0);
        P.ex.v = st > 0.08 ? o : 0; P.ex.vel = 0;
      } else {
        step(P.ex, 0, dt);
        tf(fx.ex, 326, 72, 0.6 + 0.4 * P.ex.v); op(fx.ex, P.ex.v);
      }
      const angles = [-162, -128, -52, -18];
      fx.burst.forEach((ln, i) => {
        if (state === 'surprised' && st > 0.08 && st < 0.7) {
          const p = (st - 0.08) / 0.55;
          const a = angles[i] * Math.PI / 180;
          const r1 = 38 + p * 22, r2 = r1 + 16 * (1 - p) + 3;
          ln.setAttribute('x1', (326 + Math.cos(a) * r1).toFixed(1));
          ln.setAttribute('y1', (50 + Math.sin(a) * r1).toFixed(1));
          ln.setAttribute('x2', (326 + Math.cos(a) * r2).toFixed(1));
          ln.setAttribute('y2', (50 + Math.sin(a) * r2).toFixed(1));
          op(ln, 1 - p * p);
        } else op(ln, 0);
      });

      // Confused: two wobbling "?"
      if (state === 'confused') {
        const s1 = easeOutBack((st - 0.05) / 0.35), s2 = easeOutBack((st - 0.4) / 0.35);
        tf(fx.q1, 332, 76 + 3 * Math.sin(t * 2.2), s1, 12 * Math.sin(t * 2.4));
        tf(fx.q2, 292, 44 + 3 * Math.sin(t * 2 + 1), 0.62 * s2, -14 * Math.sin(t * 2.1 + 1));
        op(fx.q1, st > 0.05 ? 1 : 0); op(fx.q2, st > 0.4 ? 1 : 0);
        P.q.v = 1; P.q.vel = 0;
      } else {
        step(P.q, 0, dt);
        tf(fx.q1, 332, 76, P.q.v); tf(fx.q2, 292, 44, 0.62 * P.q.v);
        op(fx.q1, P.q.v); op(fx.q2, P.q.v);
      }

      // Thinking: bubble grows from head, dots bounce inside
      const fl = 2.5 * Math.sin(t * 1.6);
      let sB1, sB2, sB3;
      if (state === 'thinking') {
        sB1 = easeOutBack(st / 0.25);
        sB2 = easeOutBack((st - 0.12) / 0.25);
        sB3 = easeOutBack((st - 0.24) / 0.35);
        P.b.v = 1; P.b.vel = 0;
      } else {
        step(P.b, 0, dt);
        sB1 = sB2 = sB3 = P.b.v;
      }
      tf(fx.b1, 322, 110 + fl * 0.4, sB1); op(fx.b1, sB1 > 0.01 ? 1 : 0);
      tf(fx.b2, 336, 86 + fl * 0.7, sB2); op(fx.b2, sB2 > 0.01 ? 1 : 0);
      tf(fx.b3, 353, 44 + fl, sB3);       op(fx.b3, sB3 > 0.01 ? 1 : 0);
      fx.dots.forEach((d, i) => {
        const bounce = Math.max(0, Math.sin(t * 6.5 - i * 0.9));
        d.setAttribute('cy', (2 - 5 * bounce).toFixed(2));
        op(d, 0.45 + 0.55 * bounce);
      });

      // Sleepy: z's float up, sway, grow and fade
      step(P.z, state === 'sleepy' ? 1 : 0, dt);
      if (state === 'sleepy' && t > zNext) {
        zs[zIdx].born = t;
        zIdx = (zIdx + 1) % zs.length;
        zNext = t + 1.0;
      }
      zs.forEach((z) => {
        const life = 2.8, age = t - z.born;
        if (age < 0 || age > life) { op(z.el, 0); return; }
        const p = age / life;
        tf(z.el, 312 + p * 60 + 7 * Math.sin(age * 3), 112 - p * 110, 0.55 + p * 0.95, -12 + 18 * p);
        op(z.el, Math.min(1, p / 0.15) * (1 - Math.max(0, (p - 0.6) / 0.4)) * P.z.v);
      });

      // Wink: twinkling sparkles
      step(P.sp, state === 'wink' ? 1 : 0, dt);
      if (state === 'wink' && t > sparkNext) { sparkBorn = t; sparkNext = t + 2.6; }
      [[fx.s1, 0, 1, 356, 104], [fx.s2, 0.1, 0.55, 380, 138]].forEach(([el, delay, size, x, y]) => {
        const age = t - sparkBorn - delay;
        if (age < 0 || age > 1.1) { op(el, 0); return; }
        const s = easeOutBack(age / 0.25) * (1 - clamp01((age - 0.75) / 0.35)) * size;
        tf(el, x, y, s, age * 120);
        op(el, P.sp.v > 0.02 ? 1 : 0);
      });
    }

    function frame(nowMs) {
      if (!alive) return;
      const t = nowMs / 1000 - t0;
      const dt = Math.min(0.033, Math.max(0.001, t - last));
      last = t;
      T = t;
      const st = t - stateStart;

      step(lvl, state === 'listening' ? level : 0, dt);
      const L = clamp01(lvl.v);

      const tgt = { ...DEFAULTS, ...EXPR[state] };
      if (state === 'surprised') {
        const ph = st < 0.08 ? 0 : st < 0.26 ? 1 : 2;   // squeeze → pop → settle
        tgt.wide = [0.6, 1.75, 1.32][ph];
        tgt.wideX = [1.18, 1.22, 1.1][ph];
      }
      if (state === 'confused') {
        tgt.headTilt += 4 * Math.sin(t * 1.8);
        tgt.yaw = 0.22 * Math.sin(t * 1.2);
      }
      if (state === 'listening') tgt.wide += L * 0.3;
      if (follow) { tgt.yaw = mouseYaw; tgt.pitch = mousePitch; }
      for (const key in S) step(S[key], tgt[key], dt);

      // Idle glances (saccades)
      const glancing = autoIdle && !follow && (state === 'idle' || state === 'speaking');
      if (glancing && t > nextSaccade) {
        const back = Math.random() < 0.4;
        sacTarget = back ? { y: 0, p: 0 } : {
          y: (Math.random() * 2 - 1) * 0.28,
          p: (Math.random() * 2 - 1) * 0.12,
        };
        nextSaccade = t + 1.1 + Math.random() * 2.6;
      }
      if (!glancing) sacTarget = { y: 0, p: 0 };
      step(sacYaw, sacTarget.y, dt);
      step(sacPitch, sacTarget.p, dt);

      // Blinking
      const canBlink = autoIdle && !['happy', 'sleepy', 'wink'].includes(state);
      if (canBlink && t > nextBlink) {
        blinkStart = t;
        doubleBlink = Math.random() < 0.2;
        nextBlink = t + 2.2 + Math.random() * 3.4;
      }
      if (doubleBlink && t - blinkStart > 0.26 && t - blinkStart < 0.3) { blinkStart = t; doubleBlink = false; }
      const bp = (t - blinkStart) / 0.16;
      const blink = bp >= 0 && bp < 1 ? 1 - 0.92 * Math.sin(bp * Math.PI) : 1;

      // Speaking amplitude
      step(amp, state === 'speaking' ? voiceAmp(t) : 0, dt);
      const a = Math.max(0, amp.v);

      // Body bounce
      hops = hops.filter((h) => {
        if (t >= h.at) { bodyY.vel += h.v; return false; }
        return true;
      });
      step(bodyY, -a * 7 - L * 6, dt);

      let wigY = 0, wigP = 0;
      if (state === 'thinking') { wigY = 0.05 * Math.sin(t * 1.6); wigP = 0.03 * Math.sin(t * 2.3); }

      const yaw = S.yaw.v + sacYaw.v + wigY;
      const pitch = S.pitch.v + sacPitch.v + wigP + a * 0.04;

      // Body: breathing + squash/stretch + lean
      const sleepy = state === 'sleepy';
      const breathe = Math.sin(t * (sleepy ? 1.05 : 2.1));
      const bAmp = sleepy ? 2.2 : 1;
      const stretch = Math.max(-0.08, Math.min(0.08, -bodyY.vel / 650));
      const sy = 1 + 0.012 * bAmp * breathe + stretch;
      const sx = 1 - 0.008 * bAmp * breathe - stretch * 0.6 - Math.abs(yaw) * 0.025;
      const leanX = yaw * 10, leanY = -pitch * 6 + bodyY.v;
      const pvx = 200, pvy = 340;
      body.setAttribute('transform',
        `translate(${leanX.toFixed(2)} ${leanY.toFixed(2)}) ` +
        `rotate(${S.headTilt.v.toFixed(2)} ${pvx} ${pvy}) ` +
        `translate(${pvx} ${pvy}) scale(${sx.toFixed(4)} ${sy.toFixed(4)}) translate(${-pvx} ${-pvy})`);

      const lift = Math.max(0, -bodyY.v);
      shadow.setAttribute('rx', (115 * (1 - lift / 260)).toFixed(1));
      shadow.setAttribute('opacity', ((bg === 'meeting' ? 0.35 : 0.07) * (1 - lift / 200)).toFixed(3));

      // Eyes projected onto an imaginary sphere
      [-1, 1].forEach((side, i) => {
        const e = eyes[i];
        const isL = side < 0;
        const ey = yaw + side * BASE_YAW;
        const ep = pitch;
        const px = CX + R * Math.sin(ey) * Math.cos(ep);
        const py = CY - R * Math.sin(ep);
        const fxs = Math.max(0.25, Math.cos(ey));       // far eye gets narrower
        const fys = Math.max(0.25, Math.cos(ep));

        const scale = isL ? S.lScale.v : S.rScale.v;
        const open = Math.max(0, S.open.v * (isL ? S.lOpen.v : S.rOpen.v) * blink);
        const tilt = isL ? S.lTilt.v : S.rTilt.v;
        const happy = clamp01(S.happy.v + (isL ? S.lHappy.v : S.rHappy.v));
        const closed = clamp01(S.closed.v);
        const hide = Math.max(happy, closed);

        const w = EYE_W * S.wideX.v * scale;
        const h = Math.max(3, EYE_H * S.wide.v * open * scale * (1 + a * 0.1) * (1 - hide * 0.75));
        e.rect.setAttribute('x', (-w / 2).toFixed(2));
        e.rect.setAttribute('y', (-h / 2).toFixed(2));
        e.rect.setAttribute('width', w.toFixed(2));
        e.rect.setAttribute('height', h.toFixed(2));
        e.rect.setAttribute('rx', (Math.min(w, h) / 2).toFixed(2));
        op(e.rect, 1 - hide);

        const aw = EYE_W * 1.25 * scale, ah = 14 * scale;
        e.arch.setAttribute('d', `M ${-aw / 2} ${ah * 0.5} Q 0 ${-ah * 1.3} ${aw / 2} ${ah * 0.5}`);
        e.arch.setAttribute('stroke-width', (EYE_W * 0.45 * scale).toFixed(2));
        op(e.arch, happy);

        const cw = EYE_W * 1.4, ch = 12;
        e.curve.setAttribute('d', `M ${-cw / 2} ${-ch * 0.4} Q 0 ${ch * 1.1} ${cw / 2} ${-ch * 0.4}`);
        e.curve.setAttribute('stroke-width', (EYE_W * 0.4).toFixed(2));
        op(e.curve, closed * (1 - happy));

        e.g.setAttribute('transform',
          `translate(${px.toFixed(2)} ${py.toFixed(2)}) scale(${fxs.toFixed(4)} ${fys.toFixed(4)}) rotate(${tilt.toFixed(2)})`);
      });

      // Voice rings while speaking
      if (state === 'speaking' && a > 0.35 && t - lastRing > 0.55) {
        rings[ringIdx].born = t;
        ringIdx = (ringIdx + 1) % rings.length;
        lastRing = t;
      }
      rings.forEach((r) => {
        const age = t - r.born;
        if (age < 0 || age > 1.3) { r.el.setAttribute('opacity', '0'); return; }
        const p = age / 1.3;
        r.el.setAttribute('cx', (200 + leanX).toFixed(1));
        r.el.setAttribute('cy', (214 + leanY).toFixed(1));
        r.el.setAttribute('r', (160 + p * 60).toFixed(1));
        r.el.setAttribute('opacity', (0.32 * (1 - p)).toFixed(3));
      });

      updateFx(t, st, dt, leanX, leanY);
      requestAnimationFrame(frame);
    }

    function onPointer(e) {
      const r = svg.getBoundingClientRect();
      const dx = (e.clientX - (r.left + r.width / 2)) / (r.width / 2);
      const dy = (e.clientY - (r.top + r.height / 2)) / (r.height / 2);
      mouseYaw = Math.max(-0.65, Math.min(0.65, dx * 0.55));
      mousePitch = Math.max(-0.45, Math.min(0.45, -dy * 0.45));
    }
    window.addEventListener('pointermove', onPointer);

    setColour(colour);
    requestAnimationFrame(frame);

    return {
      setState,
      getState: () => state,
      setColour,
      getColour: () => colour,
      setBackground,
      setAutoIdle: (v) => { autoIdle = !!v; },
      setFollow: (v) => { follow = !!v; },
      setLevel: (v) => { level = clamp01(v); },
      onStateChange: (fn) => { onState = fn; },
      destroy: () => { alive = false; window.removeEventListener('pointermove', onPointer); },
    };
  }

  window.CloudAvatar = { create, ORDER, COLOURS, STATES: Object.keys(EXPR) };
})();
