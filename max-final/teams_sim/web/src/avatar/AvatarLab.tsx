// Avatar lab: playground for Max's animated character (?view=avatar).
// URL options: &state=happy  &freeze=1 (nice frozen pose)  &at=0.4 (freeze at a custom time)
//              &bg=white|tinted|meeting  &sheet=1 (contact sheet of every state, frozen)  &states=happy,sleepy
import { memo, useEffect, useRef, useState } from "react";
import {
  Badge, Divider, Slider, Switch, Tab, TabList, Text, ToggleButton, makeStyles, mergeClasses, tokens,
} from "@fluentui/react-components";
import { MAX_COLOR, MAX_FREEZE_POSE, MAX_STATES, MAX_STATE_INFO, MaxCharacter, type MaxState } from "./MaxCharacter";

type Bg = "white" | "tinted" | "meeting";
const BG: Record<Bg, string> = {
  white: "#ffffff",
  tinted: "linear-gradient(180deg, #F3F1FB 0%, #ECEAF8 100%)",
  meeting: "radial-gradient(120% 90% at 50% 35%, #3a3a3a 0%, #262626 60%, #1f1f1f 100%)",
};

const useStyles = makeStyles({
  page: { flex: 1, overflowY: "auto", backgroundColor: tokens.colorNeutralBackground3, padding: "24px 28px 40px" },
  inner: { maxWidth: "1240px", margin: "0 auto", display: "flex", flexDirection: "column", gap: "16px" },
  head: { display: "flex", alignItems: "baseline", gap: "10px", flexWrap: "wrap" },
  sub: { color: tokens.colorNeutralForeground3 },
  top: { display: "grid", gridTemplateColumns: "minmax(0, 1fr) 340px", gap: "16px" },
  card: {
    backgroundColor: tokens.colorNeutralBackground1, borderRadius: tokens.borderRadiusXLarge,
    boxShadow: tokens.shadow4, overflow: "hidden",
  },
  stageBar: {
    display: "flex", alignItems: "center", justifyContent: "space-between", gap: "8px",
    padding: "8px 12px 8px 16px", borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  stage: {
    position: "relative", height: "500px", display: "flex", alignItems: "center", justifyContent: "center",
    transition: "background 300ms ease",
  },
  stageMeeting: { margin: "16px", height: "468px", borderRadius: tokens.borderRadiusXLarge },
  tileName: {
    position: "absolute", left: "14px", bottom: "12px", padding: "3px 10px", borderRadius: tokens.borderRadiusMedium,
    backgroundColor: "rgba(0,0,0,0.45)", color: "#fff", fontSize: tokens.fontSizeBase200, display: "flex", gap: "6px", alignItems: "center",
  },
  chip: {
    position: "absolute", left: "50%", bottom: "16px", transform: "translateX(-50%)", padding: "4px 12px",
    borderRadius: tokens.borderRadiusCircular, fontSize: tokens.fontSizeBase200,
    backgroundColor: "rgba(0,0,0,0.05)", color: tokens.colorNeutralForeground2,
  },
  chipDark: { backgroundColor: "rgba(255,255,255,0.1)", color: "#e8e8e8" },
  frozen: { position: "absolute", right: "14px", top: "12px" },
  panel: { padding: "16px", display: "flex", flexDirection: "column", gap: "14px" },
  label: {
    fontSize: tokens.fontSizeBase100, fontWeight: tokens.fontWeightSemibold, letterSpacing: "0.06em",
    textTransform: "uppercase", color: tokens.colorNeutralForeground3,
  },
  states: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px" },
  stateBtn: { justifyContent: "flex-start", fontWeight: tokens.fontWeightRegular, minWidth: 0, gap: "6px" },
  emoji: { fontSize: "14px", lineHeight: "16px", width: "18px", textAlign: "center" },
  row: { display: "flex", alignItems: "center", justifyContent: "space-between", gap: "8px" },
  meter: { height: "6px", borderRadius: "3px", backgroundColor: tokens.colorNeutralBackground5, overflow: "hidden" },
  meterFill: { height: "100%", backgroundColor: MAX_COLOR, borderRadius: "3px" },
  icons: { display: "grid", gridTemplateColumns: "1fr 1fr" },
  iconSide: { display: "flex", alignItems: "flex-end", justifyContent: "space-around", gap: "16px", padding: "24px 20px 16px" },
  iconCell: { display: "flex", flexDirection: "column", alignItems: "center", gap: "10px" },
  iconCap: { fontSize: tokens.fontSizeBase100, color: tokens.colorNeutralForeground3 },
  listRow: { display: "flex", alignItems: "center", gap: "10px" },
  sheet: { display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "12px" },
  sheetCell: {
    backgroundColor: tokens.colorNeutralBackground1, borderRadius: tokens.borderRadiusXLarge, boxShadow: tokens.shadow4,
    display: "flex", flexDirection: "column", alignItems: "center", padding: "28px 0 14px",
  },
});

export function AvatarLab() {
  const q = new URLSearchParams(window.location.search);
  const initial = (MAX_STATES as readonly string[]).includes(q.get("state") ?? "") ? (q.get("state") as MaxState) : "idle";
  if (q.get("sheet") === "1") {
    const only = q.get("states")?.split(",").filter((k): k is MaxState => (MAX_STATES as readonly string[]).includes(k));
    return <ContactSheet dark={q.get("bg") === "meeting"} states={only?.length ? only : [...MAX_STATES]} />;
  }
  const at = q.get("at");
  return <Lab initialState={initial} freeze={q.get("freeze") === "1" || at !== null} at={at ? Number(at) : undefined}
    initialBg={(q.get("bg") as Bg) ?? "white"} />;
}

function Lab({ initialState, freeze, at, initialBg }: { initialState: MaxState; freeze: boolean; at?: number; initialBg: Bg }) {
  const s = useStyles();
  const [state, setState] = useState<MaxState>(initialState);
  const [bg, setBg] = useState<Bg>(initialBg);
  const [level, setLevel] = useState(0);
  const [simulate, setSimulate] = useState(false);
  const [follow, setFollow] = useState(false);
  const [reduced, setReduced] = useState<boolean | undefined>(undefined);
  const dark = bg === "meeting";

  return (
    <div className={s.page}>
      <div className={s.inner}>
        <div className={s.head}>
          <Text size={600} weight="bold">Max character</Text>
          <Badge appearance="tint" color="brand">Lab</Badge>
          <Text className={s.sub}>Cloud body with squash &amp; stretch, eyes on a 3D sphere. Click a mood to see the move.</Text>
        </div>

        <div className={s.top}>
          {/* Stage */}
          <div className={s.card}>
            <div className={s.stageBar}>
              <TabList size="small" selectedValue={bg} onTabSelect={(_, d) => setBg(d.value as Bg)}>
                <Tab value="white">White</Tab>
                <Tab value="tinted">Tinted</Tab>
                <Tab value="meeting">Meeting tile</Tab>
              </TabList>
              <Text size={200} className={s.sub}>{follow ? "Following your cursor" : "Click a mood to play its move"}</Text>
            </div>
            <div style={{ background: dark ? tokens.colorNeutralBackground1 : undefined }}>
              <div className={mergeClasses(s.stage, dark && s.stageMeeting)} style={{ background: BG[bg] }}>
                <StageCharacter state={state} level={level} simulate={simulate} follow={follow} reduced={reduced}
                  dark={dark} freezeAt={freeze ? (at ?? MAX_FREEZE_POSE[state]) : undefined} />
                {dark ? (
                  <div className={s.tileName}>Max <span style={{ opacity: 0.7 }}>· {MAX_STATE_INFO[state].label}</span></div>
                ) : (
                  <div className={s.chip}>{MAX_STATE_INFO[state].emoji} {MAX_STATE_INFO[state].label}</div>
                )}
                {freeze && <Badge className={s.frozen} appearance="outline" color={dark ? "subtle" : "informative"}>Frozen pose</Badge>}
              </div>
            </div>
          </div>

          {/* Controls */}
          <div className={mergeClasses(s.card, s.panel)}>
            <span className={s.label}>Mood</span>
            <div className={s.states}>
              {MAX_STATES.map((k) => (
                <ToggleButton key={k} size="small" className={s.stateBtn} checked={state === k}
                  appearance={state === k ? "primary" : "secondary"} onClick={() => setState(k)}
                  icon={<span className={s.emoji}>{MAX_STATE_INFO[k].emoji}</span>}>
                  {MAX_STATE_INFO[k].label}
                </ToggleButton>
              ))}
            </div>
            <Divider />
            <span className={s.label}>Voice</span>
            <div>
              <div className={s.row}>
                <Text size={200}>Level</Text>
                <Text size={200} className={s.sub}>{simulate ? "simulated" : level.toFixed(2)}</Text>
              </div>
              <Slider min={0} max={1} step={0.01} value={level} disabled={simulate} style={{ width: "100%" }}
                onChange={(_, d) => setLevel(d.value)} />
            </div>
            <Switch label="Simulate voice" checked={simulate} onChange={(_, d) => setSimulate(d.checked)} />
            <Text size={200} className={s.sub}>Level drives Listening and Speaking. At 0, Speaking uses its own talk rhythm.</Text>
            <Divider />
            <span className={s.label}>Behaviour</span>
            <Switch label="Follow cursor" checked={follow} onChange={(_, d) => setFollow(d.checked)} />
            <Switch label="Reduced motion" checked={reduced ?? false} onChange={(_, d) => setReduced(d.checked)} />
          </div>
        </div>

        {/* Icon sizes */}
        <div className={s.card}>
          <div className={s.stageBar}>
            <Text weight="semibold">Still icon</Text>
            <Text size={200} className={s.sub}>At 40 px and below Max uses a simpler 3-bump shape and bigger eyes.</Text>
          </div>
          <div className={s.icons}>
            <IconRow dark={false} />
            <IconRow dark />
          </div>
        </div>
      </div>
    </div>
  );
}

/** Keeps the fast-changing simulated level inside this small component, so the rest of the page doesn't re-render. */
function StageCharacter({ state, level, simulate, follow, reduced, dark, freezeAt }: {
  state: MaxState; level: number; simulate: boolean; follow: boolean; reduced?: boolean; dark: boolean; freezeAt?: number;
}) {
  const [sim, setSim] = useState(0);
  const raf = useRef(0);
  useEffect(() => {
    if (!simulate) return;
    const t0 = performance.now();
    let last = 0;
    const tick = (now: number) => {
      if (now - last > 33) {
        last = now;
        const t = (now - t0) / 1000;
        const phrase = Math.sin(t * 0.9) + Math.sin(t * 1.7 + 1) > -0.6 ? 1 : 0;
        const syll = Math.max(0, Math.sin(t * 11)) ** 0.6;
        setSim(phrase * syll * (0.55 + 0.45 * Math.sin(t * 2.9 + Math.sin(t * 1.3))));
      }
      raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [simulate]);
  const lv = simulate ? sim : level;
  return (
    <MaxCharacter state={state} size={340} followCursor={follow} reducedMotion={reduced} onDark={dark}
      level={simulate || level > 0 ? lv : undefined} freezeAt={freezeAt} />
  );
}

const IconRow = memo(function IconRow({ dark }: { dark: boolean }) {
  const s = useStyles();
  const fg = dark ? "#d6d6d6" : tokens.colorNeutralForeground3;
  return (
    <div className={s.iconSide} style={{ background: dark ? "#1f1f1f" : "#ffffff" }}>
      {[192, 48, 32, 20].map((px) => (
        <div key={px} className={s.iconCell}>
          <MaxCharacter still size={px} />
          <span className={s.iconCap} style={{ color: fg }}>{px} px</span>
        </div>
      ))}
      <div className={s.iconCell}>
        <div className={s.listRow}>
          <MaxCharacter size={32} />
          <div>
            <div style={{ fontWeight: 600, fontSize: 13, color: dark ? "#fff" : "#242424" }}>Max</div>
            <div style={{ fontSize: 12, color: fg }}>live, 32 px</div>
          </div>
        </div>
        <span className={s.iconCap} style={{ color: fg }}>in a list</span>
      </div>
    </div>
  );
});

function ContactSheet({ dark, states }: { dark: boolean; states: MaxState[] }) {
  const s = useStyles();
  return (
    <div className={s.page}>
      <div className={s.inner}>
        <div className={s.head}>
          <Text size={600} weight="bold">Max character: every mood</Text>
          <Text className={s.sub}>Frozen at a key pose of each move</Text>
        </div>
        <div className={s.sheet}>
          {states.map((k) => (
            <div key={k} className={s.sheetCell} style={dark ? { background: "#262626" } : undefined}>
              <MaxCharacter state={k} size={230} freezeAt={MAX_FREEZE_POSE[k]} onDark={dark} />
              <Text weight="semibold" style={dark ? { color: "#eee" } : undefined}>{MAX_STATE_INFO[k].emoji} {MAX_STATE_INFO[k].label}</Text>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
