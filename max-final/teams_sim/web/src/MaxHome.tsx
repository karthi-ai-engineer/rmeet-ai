// Max app › Home (everyone): the home of the full living Max (personal tab in real Teams, our own page).
// "Open Max" buttons in cards link here. Max reacts to what is happening: happy when you arrive, thinking while
// he works on something in the background, listening when you point at "Ask Max"; hover and poke him.
import { useEffect, useState, type ReactNode } from "react";
import { AvatarGroup, AvatarGroupItem, Badge, Button, Spinner, Text, makeStyles, mergeClasses, tokens } from "@fluentui/react-components";
import {
  Clock20Regular, Board20Regular, CalendarLtr20Regular, Chat20Regular, ChatSparkle20Regular, CheckmarkCircle16Filled,
  Mail20Regular, Settings20Regular, TaskListLtr20Regular,
} from "@fluentui/react-icons";
import { MaxCharacter, useReducedMotionPref, type MaxState } from "./avatar/MaxCharacter";
import { PEOPLE, type PersonId } from "./mock";
import { MAX_ORANGE, personName } from "./ui";
import type { NavTarget } from "./ChatScreen";

const useStyles = makeStyles({
  grid: { display: "grid", gridTemplateColumns: "minmax(0, 1.1fr) minmax(0, 1fr)", gap: "20px", alignItems: "start" },
  col: { display: "flex", flexDirection: "column", gap: "20px" },
  card: { backgroundColor: tokens.colorNeutralBackground1, borderRadius: tokens.borderRadiusXLarge, boxShadow: tokens.shadow4, padding: "22px 24px" },
  // entrance: a short fade-up, one after another; none with reduced motion
  enter: {
    animationName: { from: { opacity: 0, transform: "translateY(10px)" }, to: { opacity: 1, transform: "none" } },
    animationDuration: "420ms", animationTimingFunction: "cubic-bezier(0.2, 0.8, 0.2, 1)", animationFillMode: "both",
    "@media (prefers-reduced-motion: reduce)": { animationName: "none" },
  },
  hero: { padding: "0 0 24px", overflow: "hidden" },
  stage: {
    position: "relative", height: "250px", display: "flex", alignItems: "flex-end", justifyContent: "center",
    background: `radial-gradient(70% 80% at 50% 100%, ${MAX_ORANGE}1f 0%, ${MAX_ORANGE}0a 55%, transparent 80%)`,
    borderBottom: `1px solid ${tokens.colorNeutralStroke3}`,
  },
  status: {
    position: "absolute", top: "14px", left: "50%", transform: "translateX(-50%)", display: "flex", alignItems: "center", gap: "8px",
    padding: "4px 12px 4px 10px", borderRadius: tokens.borderRadiusCircular, fontSize: tokens.fontSizeBase200, whiteSpace: "nowrap",
    backgroundColor: tokens.colorNeutralBackground1, boxShadow: tokens.shadow4, color: tokens.colorNeutralForeground2,
  },
  statusText: {
    animationName: { from: { opacity: 0, transform: "translateY(3px)" }, to: { opacity: 1, transform: "none" } },
    animationDuration: "260ms", animationTimingFunction: "ease-out",
    "@media (prefers-reduced-motion: reduce)": { animationName: "none" },
  },
  dot: { width: "8px", height: "8px", borderRadius: "50%", backgroundColor: tokens.colorPaletteGreenBackground3 },
  heroBody: { padding: "18px 24px 0" },
  hello: { fontSize: tokens.fontSizeBase600, fontWeight: tokens.fontWeightSemibold, lineHeight: tokens.lineHeightBase600, display: "block" },
  muted: { color: tokens.colorNeutralForeground3 },
  actions: { display: "flex", flexWrap: "wrap", gap: "8px", marginTop: "18px" },
  h2: { fontSize: tokens.fontSizeBase400, fontWeight: tokens.fontWeightSemibold, display: "block", marginBottom: "2px" },
  row: { display: "flex", gap: "12px", alignItems: "flex-start", padding: "10px 0", borderTop: `1px solid ${tokens.colorNeutralStroke3}`, ":first-of-type": { borderTop: "none" } },
  rowIcon: {
    width: "32px", height: "32px", borderRadius: tokens.borderRadiusMedium, flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center",
    backgroundColor: tokens.colorNeutralBackground3, color: tokens.colorNeutralForeground2,
  },
  num: { fontVariantNumeric: "tabular-nums" },
  meet: { display: "flex", gap: "14px", alignItems: "flex-start", marginTop: "12px" },
  date: {
    width: "52px", flexShrink: 0, borderRadius: tokens.borderRadiusLarge, overflow: "hidden", textAlign: "center",
    border: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  dateTop: { backgroundColor: tokens.colorBrandBackground, color: tokens.colorNeutralForegroundOnBrand, fontSize: tokens.fontSizeBase100, fontWeight: tokens.fontWeightSemibold, padding: "2px 0" },
  dateNum: { fontSize: tokens.fontSizeBase500, fontWeight: tokens.fontWeightSemibold, padding: "2px 0 4px" },
  brief: { margin: "12px 0 0", padding: "10px 12px", borderRadius: tokens.borderRadiusLarge, backgroundColor: tokens.colorNeutralBackground3, display: "flex", flexDirection: "column", gap: "4px" },
});

/** Background work Max does now and then (real jobs: briefs, catching up, the nightly check). */
const JOBS = [
  { doing: "Preparing your brief for New model check-in…", done: "Brief ready for New model check-in" },
  { doing: "Reading 4 new messages in #Pricing…", done: "#Pricing is up to date" },
];

const TODAY: { icon: ReactNode; text: ReactNode; sub: string }[] = [
  { icon: <Chat20Regular />, text: <>Answered <b>12</b> questions</>, sub: "9 in your chat with me, 3 in #Pricing · all with sources" },
  { icon: <Mail20Regular />, text: <>Sent <b>1</b> email after your approval</>, sub: "Q1 pricing summary · 10:41" },
  { icon: <Clock20Regular />, text: <>Set <b>2</b> reminders</>, sub: "Supplier report (Mon 1 Dec) · price list (tomorrow 10:00)" },
  { icon: <TaskListLtr20Regular />, text: <>Updated the <b>New model launch</b> plan</>, sub: "Stock plan marked done by Praga" },
];

function greeting(name: string) {
  const h = new Date().getHours();
  return `${h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening"}, ${name}`;
}

export function MaxHome({ me, onOpen, onSettings }: { me: PersonId; onOpen?: (to: NavTarget) => void; onSettings: () => void }) {
  const s = useStyles();
  const reduced = useReducedMotionPref();
  const first = personName(me).split(" ")[0];
  const [mood, setMood] = useState<MaxState>("happy");                  // happy when you arrive
  const [job, setJob] = useState<{ text: string; busy: boolean } | null>(null);
  const [askHover, setAskHover] = useState(false);

  useEffect(() => {
    const timers: number[] = [];
    const at = (ms: number, fn: () => void) => timers.push(window.setTimeout(fn, ms));
    at(1800, () => setMood("idle"));
    // every ~20 s Max picks up a small background job: thinking while busy, a short happy hop when done
    let t = 7000;
    for (let i = 0; i < 6; i++) {
      const j = JOBS[i % JOBS.length];
      at(t, () => { setJob({ text: j.doing, busy: true }); setMood("thinking"); });
      at(t + 4200, () => { setJob({ text: j.done, busy: false }); setMood("happy"); });
      at(t + 5600, () => setMood("idle"));
      at(t + 8200, () => setJob(null));
      t += 20000;
    }
    return () => timers.forEach(clearTimeout);
  }, []);

  const state: MaxState = askHover && mood === "idle" ? "listening" : mood;
  const meeting = PEOPLE.filter((p) => ["prince", "praga", "rachitaa", "karthi"].includes(p.id));
  const delay = (i: number) => ({ animationDelay: `${i * 70}ms` });

  return (
    <div className={s.grid}>
      <section className={mergeClasses(s.card, s.hero, s.enter)} style={delay(0)} aria-label="Max">
        <div className={s.stage}>
          <div className={s.status} role="status" aria-live="polite">
            {job?.busy ? <Spinner size="extra-tiny" aria-hidden /> : job ? <CheckmarkCircle16Filled primaryFill={tokens.colorPaletteGreenForeground1} /> : <span className={s.dot} />}
            <span key={job?.text ?? "idle"} className={s.statusText}>{job ? job.text : "All caught up · watching 6 chats"}</span>
          </div>
          <MaxCharacter state={state} size={210} interactive title="Max" style={{ marginBottom: -6 }} />
        </div>
        <div className={s.heroBody}>
          <span className={s.hello}>{greeting(first)}</span>
          <Text className={s.muted}>
            I'm keeping an eye on your team's chats, files and plans.{reduced ? "" : " Poke me if you like."}
          </Text>
          <div className={s.actions}>
            <Button appearance="primary" icon={<ChatSparkle20Regular />} onClick={() => onOpen?.({ view: "chat", chat: "max" })}
              onMouseEnter={() => setAskHover(true)} onMouseLeave={() => setAskHover(false)}
              onFocus={() => setAskHover(true)} onBlur={() => setAskHover(false)}>Ask Max</Button>
            <Button icon={<Board20Regular />} onClick={() => onOpen?.({ view: "teams", channel: "pp-models", tab: "plans" })}>Open plans</Button>
            <Button appearance="subtle" icon={<Settings20Regular />} onClick={onSettings}>My settings</Button>
          </div>
        </div>
      </section>

      <div className={s.col}>
        <section className={mergeClasses(s.card, s.enter)} style={delay(1)}>
          <span className={s.h2}>What I did today</span>
          <Text size={200} className={s.muted}>For you and your team, since 08:00</Text>
          <div style={{ marginTop: 8 }}>
            {TODAY.map((r, i) => (
              <div key={i} className={s.row}>
                <span className={s.rowIcon}>{r.icon}</span>
                <div style={{ minWidth: 0 }}>
                  <Text block className={s.num}>{r.text}</Text>
                  <Text size={200} className={s.muted}>{r.sub}</Text>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className={mergeClasses(s.card, s.enter)} style={delay(2)}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span className={s.h2} style={{ marginBottom: 0 }}>Coming up</span>
            <Badge appearance="tint" color="success" size="small" icon={<CheckmarkCircle16Filled />}>Brief ready</Badge>
          </div>
          <div className={s.meet}>
            <div className={s.date} aria-hidden>
              <div className={s.dateTop}>FRI</div>
              <div className={s.dateNum}>28</div>
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <Text weight="semibold" block>New model check-in</Text>
              <Text size={200} className={s.muted} block>Fri 28 Nov · 10:00 to 11:00 JST · organised by Prince</Text>
              <AvatarGroup layout="stack" size={20} style={{ marginTop: 6 }}>
                {meeting.map((p) => <AvatarGroupItem key={p.id} name={p.name} color={p.color} />)}
              </AvatarGroup>
            </div>
          </div>
          <div className={s.brief}>
            <Text size={200} weight="semibold">From my brief</Text>
            <Text size={200}>⚠️ Price list (Praga) is 2 days late</Text>
            <Text size={200}>⚠️ GPU supplier decision is waiting for Supplier B's date</Text>
            <Text size={200}>📌 Launch date is <b>Wed 15 Jan</b></Text>
          </div>
          <div className={s.actions} style={{ marginTop: 14 }}>
            <Button icon={<CalendarLtr20Regular />} onClick={() => onOpen?.({ view: "calendar", meeting: "m5" })}>Open brief</Button>
          </div>
        </section>
      </div>
    </div>
  );
}

