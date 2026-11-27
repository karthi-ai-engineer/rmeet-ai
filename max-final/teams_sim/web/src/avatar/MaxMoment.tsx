// Max's card moments: Max on his own small rounded tile, as it appears inside an Adaptive Card.
//
//   <MaxMomentTile moment="welcome" />
//
// In real Teams this tile is an image in the card: a GIF for "welcome" and "celebrate" (plays 2x or 1x, under 5 s,
// last frame = a still pose) and a PNG for "sorry". The tile background is baked into the image, so it looks the
// same on light and dark cards. The simulator draws the live character but limits it exactly like that GIF:
// it plays the same number of times, then stops on the same still pose. Reduced motion = the still pose only.
import { useEffect, useState } from "react";
import { MaxCharacter, useReducedMotionPref, type MaxState } from "./MaxCharacter";

export type MaxMoment = "welcome" | "celebrate" | "sorry";

interface Script {
  label: string;           // alt text (the card's Image altText says the same)
  plays: number;           // how often the GIF plays (0 = a still PNG)
  length: number;          // seconds per play
  steps: [number, MaxState][]; // state changes within one play (seconds)
  finish: number;          // seconds into the LAST play where it stops on the still pose
  still: [MaxState, number]; // the still pose: state + seconds after entering it (first/last GIF frame)
}

export const MOMENTS: Record<MaxMoment, Script> = {
  // a little wink, then a happy hop; twice (about 4.5 s), then rests smiling
  welcome: {
    label: "Max says hello with a wink and a happy hop",
    plays: 2, length: 2.3, steps: [[0, "wink"], [0.8, "happy"], [1.9, "idle"]], finish: 1.9, still: ["happy", 1.4],
  },
  // two jumps with sparkles, once (about 2 s), then rests smiling
  celebrate: {
    label: "Max celebrating",
    plays: 1, length: 2, steps: [[0, "celebrate"]], finish: 1.8, still: ["happy", 1.4],
  },
  // never animated
  sorry: { label: "Max looking sorry", plays: 0, length: 0, steps: [], finish: 0, still: ["sorry", 1.4] },
};

const FADE_MS = 280;

/** Total seconds a moment moves before it rests (for timing demos). */
export const momentDuration = (m: MaxMoment) =>
  MOMENTS[m].plays ? (MOMENTS[m].plays - 1) * MOMENTS[m].length + MOMENTS[m].finish + FADE_MS / 1000 : 0;

export function MaxMomentTile({ moment, size = 96, replayKey = 0 }: { moment: MaxMoment; size?: number; replayKey?: number }) {
  const sc = MOMENTS[moment];
  const reduced = useReducedMotionPref();
  const animated = sc.plays > 0 && !reduced;
  const [phase, setPhase] = useState<"live" | "fade" | "still">(animated ? "live" : "still");
  const [state, setState] = useState<MaxState>(sc.steps[0]?.[1] ?? sc.still[0]);

  useEffect(() => {
    if (!animated) { setPhase("still"); return; }
    setPhase("live");
    setState(sc.steps[0][1]);
    const timers: number[] = [];
    const at = (s: number, fn: () => void) => timers.push(window.setTimeout(fn, s * 1000));
    for (let p = 0; p < sc.plays; p++) {
      const last = p === sc.plays - 1;
      for (const [t, st] of sc.steps) {
        if (p === 0 && t === 0) continue;
        if (last && t >= sc.finish) continue;
        at(p * sc.length + t, () => setState(st));
      }
    }
    const end = (sc.plays - 1) * sc.length + sc.finish;
    at(end, () => setPhase("fade"));
    timers.push(window.setTimeout(() => setPhase("still"), end * 1000 + FADE_MS));
    return () => timers.forEach(clearTimeout);
  }, [moment, animated, replayKey]); // eslint-disable-line react-hooks/exhaustive-deps

  // the character fills ~90% of the tile, so effects (sparkles, the sweat drop) stay inside the image
  const inner = Math.round(size * 0.9);
  const layer = { position: "absolute", left: Math.round((size - inner) / 2), top: Math.round(size * 0.04) } as const;
  return (
    <div
      role="img"
      aria-label={sc.label}
      style={{
        position: "relative", width: size, height: size, flexShrink: 0, overflow: "hidden",
        borderRadius: Math.round(size * 0.2),
        background: "linear-gradient(180deg, #FFF5EE 0%, #FFE7D6 100%)",
        boxShadow: "inset 0 0 0 1px rgba(247, 99, 12, 0.10)",
      }}
    >
      <div aria-hidden="true">
        {phase !== "live" && (
          <div style={layer}>
            <MaxCharacter state={sc.still[0]} freezeAt={sc.still[1]} size={inner} interactive={false} />
          </div>
        )}
        {phase !== "still" && (
          <div style={{ ...layer, opacity: phase === "fade" ? 0 : 1, transition: `opacity ${FADE_MS}ms ease-out` }}>
            <MaxCharacter state={state} size={inner} interactive={false} />
          </div>
        )}
      </div>
    </div>
  );
}
