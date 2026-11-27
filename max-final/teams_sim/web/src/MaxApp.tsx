// UI design mock-up: Max's own app (left rail "Max"): Home (everyone), Setup, Health, Costs, My settings. Static data.
import { useState, type ReactNode } from "react";
import {
  Avatar,
  Badge,
  Button,
  Dropdown,
  Field,
  Input,
  Option,
  ProgressBar,
  SpinButton,
  Switch,
  Tab,
  TabList,
  Table,
  TableBody,
  TableCell,
  TableCellLayout,
  TableHeader,
  TableHeaderCell,
  TableRow,
  Text,
  Tooltip,
  makeStyles, shorthands,
  mergeClasses,
  tokens,
} from "@fluentui/react-components";
import {
  ArrowSync16Regular,
  Checkmark12Filled,
  CheckmarkCircle20Filled,
  Clock20Regular,
  DataBarVertical20Regular,
  ErrorCircle20Filled,
  HeartPulse20Regular,
  Home20Regular,
  Code20Regular,
  Search20Regular,
  LockClosed12Regular,
  Person20Regular,
  Settings20Regular,
  Warning20Filled,
} from "@fluentui/react-icons";
import { PEOPLE, type PersonId } from "./mock";
import { MAX_ORANGE, MaxAvatar, personName } from "./ui";
import { RunViewer, SearchTester } from "./DevTools";
import { MaxHome } from "./MaxHome";
import type { NavTarget } from "./ChatScreen";

const ADMINS: PersonId[] = ["prince", "karthi"]; // team lead + developer

const useStyles = makeStyles({
  page: { flex: 1, display: "flex", flexDirection: "column", minWidth: 0, backgroundColor: tokens.colorNeutralBackground3 },
  hero: {
    display: "flex", alignItems: "center", gap: "16px", padding: "18px 28px 0", flexShrink: 0,
    backgroundColor: tokens.colorNeutralBackground1, borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    backgroundImage: `linear-gradient(90deg, ${MAX_ORANGE}14 0%, transparent 45%)`,
  },
  heroText: { paddingBottom: "14px" },
  heroName: { fontSize: tokens.fontSizeBase600, fontWeight: tokens.fontWeightBold, color: MAX_ORANGE, lineHeight: 1.1 },
  tabs: { marginLeft: "auto", alignSelf: "flex-end" },
  body: { flex: 1, overflowY: "auto", padding: "24px 28px 40px" },
  inner: { maxWidth: "1180px", margin: "0 auto" },
  card: { backgroundColor: tokens.colorNeutralBackground1, borderRadius: tokens.borderRadiusXLarge, boxShadow: tokens.shadow4, padding: "22px 24px" },
  h2: { fontSize: tokens.fontSizeBase500, fontWeight: tokens.fontWeightSemibold, marginBottom: "4px" },
  sub: { color: tokens.colorNeutralForeground3, fontSize: tokens.fontSizeBase300, marginBottom: "18px", display: "block" },
  muted: { color: tokens.colorNeutralForeground3 },
  // wizard
  wizard: { display: "grid", gridTemplateColumns: "260px 1fr", gap: "20px", alignItems: "start" },
  steps: { padding: "14px 10px" },
  step: { display: "flex", alignItems: "center", gap: "12px", padding: "10px 12px", borderRadius: tokens.borderRadiusLarge, cursor: "pointer", ":hover": { backgroundColor: tokens.colorNeutralBackground1Hover } },
  stepActive: { backgroundColor: tokens.colorNeutralBackground1Selected },
  bubble: {
    width: "26px", height: "26px", borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
    fontSize: tokens.fontSizeBase200, fontWeight: tokens.fontWeightSemibold, border: `2px solid ${tokens.colorNeutralStroke1}`, color: tokens.colorNeutralForeground3,
  },
  bubbleDone: { backgroundColor: tokens.colorBrandBackground, ...shorthands.borderColor(tokens.colorBrandBackground), color: tokens.colorNeutralForegroundOnBrand },
  bubbleNow: { ...shorthands.borderColor(tokens.colorBrandStroke1), color: tokens.colorBrandForeground1 },
  stepLine: { width: "2px", height: "14px", backgroundColor: tokens.colorNeutralStroke2, marginLeft: "24px" },
  footer: { display: "flex", alignItems: "center", gap: "8px", marginTop: "24px", paddingTop: "16px", borderTop: `1px solid ${tokens.colorNeutralStroke2}` },
  formGrid: { display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: "18px 28px" },
  limit: { padding: "14px 16px", borderRadius: tokens.borderRadiusLarge, border: `1px solid ${tokens.colorNeutralStroke2}`, display: "flex", flexDirection: "column", gap: "6px" },
  limitTop: { display: "flex", alignItems: "center", gap: "8px" },
  note: { display: "flex", gap: "10px", alignItems: "flex-start", padding: "12px 14px", borderRadius: tokens.borderRadiusLarge, backgroundColor: tokens.colorNeutralBackground3, marginTop: "18px" },
  // health + costs
  tiles: { display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: "16px", marginBottom: "20px" },
  tile: { backgroundColor: tokens.colorNeutralBackground1, borderRadius: tokens.borderRadiusXLarge, boxShadow: tokens.shadow4, padding: "18px 20px", display: "flex", flexDirection: "column", gap: "6px" },
  tileLabel: { color: tokens.colorNeutralForeground3, fontSize: tokens.fontSizeBase200, fontWeight: tokens.fontWeightSemibold, display: "flex", alignItems: "center", gap: "6px" },
  tileValue: { fontSize: "32px", fontWeight: tokens.fontWeightSemibold, lineHeight: 1.1, fontVariantNumeric: "tabular-nums" },
  two: { display: "grid", gridTemplateColumns: "minmax(0, 1.6fr) minmax(0, 1fr)", gap: "20px", marginTop: "20px" },
  chart: { display: "flex", alignItems: "flex-end", gap: "6px", height: "180px", padding: "8px 0 0", marginLeft: "46px", borderBottom: `1px solid ${tokens.colorNeutralStroke2}`, position: "relative" },
  barWrap: { flex: 1, height: "100%", display: "flex", position: "relative", zIndex: 1, maxWidth: "34px", margin: "0 auto", flexDirection: "column", justifyContent: "flex-end", alignItems: "stretch", cursor: "default" },
  bar: { borderRadius: "4px 4px 0 0", backgroundColor: tokens.colorBrandBackground, minHeight: "2px", transitionProperty: "opacity", transitionDuration: tokens.durationFaster, ":hover": { opacity: 0.8 } },
  barToday: { backgroundColor: tokens.colorBrandBackground, opacity: 0.55 },
  capLine: { position: "absolute", left: 0, right: 0, borderTop: `2px dashed ${tokens.colorNeutralStroke1}` },
  yLabel: { position: "absolute", left: "-46px", width: "40px", textAlign: "right", transform: "translateY(-50%)", fontSize: tokens.fontSizeBase100, color: tokens.colorNeutralForeground3 },
  gridLine: { position: "absolute", left: 0, right: 0, borderTop: `1px solid ${tokens.colorNeutralStroke3}`, pointerEvents: "none" },
  capLabel: { position: "absolute", right: 0, transform: "translateY(-120%)", fontSize: tokens.fontSizeBase100, color: tokens.colorNeutralForeground3 },
  xLabels: { display: "flex", gap: "6px", marginTop: "6px", marginLeft: "46px" },
  xLabel: { flex: 1, textAlign: "center", fontSize: tokens.fontSizeBase100, color: tokens.colorNeutralForeground3 },
  hbarRow: { display: "grid", gridTemplateColumns: "120px 1fr 64px", alignItems: "center", gap: "10px", padding: "7px 0" },
  hbarTrack: { height: "10px", borderRadius: "5px", backgroundColor: tokens.colorNeutralBackground4, overflow: "hidden" },
  hbarFill: { height: "100%", borderRadius: "5px", backgroundColor: tokens.colorBrandBackground },
  num: { textAlign: "right", fontVariantNumeric: "tabular-nums" },
});

// ------------------------------------------------------------------ setup wizard
const STEPS = ["Departments and chats", "Approvals", "Working hours", "Limits", "Style", "Review"];

const PLACES = [
  { name: "Product Planning › General", kind: "Channel", on: true, window: "30 days" },
  { name: "Product Planning › New models", kind: "Channel", on: true, window: "30 days" },
  { name: "Product Planning › Pricing", kind: "Channel", on: true, window: "60 days" },
  { name: "Product Planning › Budget", kind: "Private channel", on: true, window: "30 days", locked: true },
  { name: "New model sync", kind: "Group chat", on: true, window: "30 days" },
  { name: "Friday lunch", kind: "Group chat", on: false, window: "—", personal: true },
];

const APPROVALS = [
  { action: "Send an email", who: "The person who asked" },
  { action: "Book, move or cancel a meeting", who: "The person who asked" },
  { action: "Create tasks from a plan", who: "The plan owner" },
  { action: "Change someone else's task", who: "The task owner" },
  { action: "Post in a different channel", who: "The person who asked" },
  { action: "Accept a lesson", who: "Team lead (Prince)" },
];

const LIMITS = [
  { name: "Daily AI budget", value: 1, unit: "$ / day", step: 0.5, why: "Max pauses new AI work for the day when reached" },
  { name: "Test budget", value: 5, unit: "$ / week", step: 1, why: "Separate from the daily budget" },
  { name: "Private messages per person", value: 3, unit: "per day", step: 1, why: "Chases, briefs and notices Max starts itself" },
  { name: "Chases per task", value: 1, unit: "per day", step: 1, why: "Never more than one reminder a day" },
  { name: "Timers and jobs per person", value: 40, unit: "active", step: 5, why: "Reminders and repeating jobs" },
  { name: "Approval cards expire after", value: 24, unit: "hours", step: 1, why: "Then: \"Expired, nothing was done\"" },
  { name: "Follow-up window", value: 10, unit: "minutes", step: 1, why: "Max answers follow-ups without @Max" },
  { name: "Searches per question", value: 3, unit: "max", step: 1, why: "Max digs deeper at most this often" },
];

function StepBubble({ i, now }: { i: number; now: number }) {
  const s = useStyles();
  if (i < now) return <span className={mergeClasses(s.bubble, s.bubbleDone)}><Checkmark12Filled /></span>;
  return <span className={mergeClasses(s.bubble, i === now && s.bubbleNow)}>{i + 1}</span>;
}

function SetupTab({ initialStep }: { initialStep: number }) {
  const s = useStyles();
  const [step, setStep] = useState(initialStep);
  let content: ReactNode = null;
  if (step === 0) {
    content = (
      <>
        <div className={s.h2}>Which departments and chats should Max read?</div>
        <span className={s.sub}>Max only reads the places you switch on. Older messages than the window are not read; you can read further back any time.</span>
        <Table size="small" aria-label="Places Max reads">
          <TableHeader><TableRow>
            <TableHeaderCell>Place</TableHeaderCell><TableHeaderCell style={{ width: 140 }}>Kind</TableHeaderCell>
            <TableHeaderCell style={{ width: 170 }}>History to read</TableHeaderCell><TableHeaderCell style={{ width: 110 }}>Max reads it</TableHeaderCell>
          </TableRow></TableHeader>
          <TableBody>
            {PLACES.map((p) => (
              <TableRow key={p.name}>
                <TableCell><TableCellLayout>{p.name} {p.locked && <LockClosed12Regular />}</TableCellLayout>
                  {p.personal && <Text size={200} className={s.muted} block>Mostly personal talk: not indexed</Text>}</TableCell>
                <TableCell className={s.muted}>{p.kind}</TableCell>
                <TableCell>
                  <Dropdown size="small" defaultValue={p.window} disabled={!p.on} style={{ minWidth: 120 }}>
                    {["15 days", "30 days", "60 days", "90 days"].map((w) => <Option key={w}>{w}</Option>)}
                  </Dropdown>
                </TableCell>
                <TableCell><Switch defaultChecked={p.on} /></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </>
    );
  } else if (step === 1) {
    content = (
      <>
        <div className={s.h2}>Who approves what?</div>
        <span className={s.sub}>Actions that change something or reach other people always wait for this person's OK on a card.</span>
        <Table size="small" aria-label="Approvals">
          <TableHeader><TableRow><TableHeaderCell>Action</TableHeaderCell><TableHeaderCell style={{ width: 300 }}>Approved by</TableHeaderCell></TableRow></TableHeader>
          <TableBody>
            {APPROVALS.map((a) => (
              <TableRow key={a.action}>
                <TableCell>{a.action}</TableCell>
                <TableCell>
                  <Dropdown size="small" defaultValue={a.who} style={{ minWidth: 260 }}>
                    {["The person who asked", "The plan owner", "The task owner", "Team lead (Prince)"].map((w) => <Option key={w}>{w}</Option>)}
                  </Dropdown>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <div className={s.note}><LockClosed12Regular style={{ marginTop: 4 }} />
          <Text size={200}>Emails only go to people inside the company. Deleting Teams messages or files is never allowed.</Text></div>
      </>
    );
  } else if (step === 2) {
    content = (
      <>
        <div className={s.h2}>When does Max work?</div>
        <span className={s.sub}>Max only starts conversations (chases, briefs) inside working hours. Times people set themselves are always kept.</span>
        <div className={s.formGrid}>
          <Field label="Time zone"><Dropdown defaultValue="JST (UTC+9)"><Option>JST (UTC+9)</Option><Option>UTC</Option></Dropdown></Field>
          <Field label="Working days"><Dropdown defaultValue="Monday to Friday"><Option>Monday to Friday</Option><Option>Monday to Saturday</Option></Dropdown></Field>
          <Field label="Starts"><Input defaultValue="09:00" contentBefore={<Clock20Regular />} /></Field>
          <Field label="Ends"><Input defaultValue="18:00" contentBefore={<Clock20Regular />} /></Field>
          <Field label="Nightly check (compares Max's copy with Teams)" hint="If the computer is off, it runs at the next start">
            <Input defaultValue="02:00" contentBefore={<Clock20Regular />} /></Field>
          <Field label="Weekly digest"><Dropdown defaultValue="Monday 09:00"><Option>Monday 09:00</Option><Option>Friday 17:00</Option><Option>Off</Option></Dropdown></Field>
        </div>
      </>
    );
  } else if (step === 3) {
    content = (
      <>
        <div className={s.h2}>Limits</div>
        <span className={s.sub}>Starting values. Every limit can be changed here at any time; changes apply at once, no restart.</span>
        <div className={s.formGrid}>
          {LIMITS.map((l) => (
            <div key={l.name} className={s.limit}>
              <div className={s.limitTop}>
                <Text weight="semibold" style={{ flex: 1 }}>{l.name}</Text>
                <SpinButton defaultValue={l.value} step={l.step} min={0} style={{ width: 96 }} />
                <Text size={200} className={s.muted} style={{ width: 70 }}>{l.unit}</Text>
              </div>
              <Text size={200} className={s.muted}>{l.why}</Text>
            </div>
          ))}
        </div>
      </>
    );
  } else if (step === 4) {
    content = (
      <>
        <div className={s.h2}>Style</div>
        <span className={s.sub}>How Max writes in this team.</span>
        <div className={s.formGrid}>
          <div className={s.limit}><Switch defaultChecked label="Emoji signposts (✅ ⚠️ 📌 📅 ⏰ 🔍 📎 👋)" /><Text size={200} className={s.muted}>A few emoji at the start of lines, never as decoration</Text></div>
          <div className={s.limit}><Switch defaultChecked label="Answer follow-ups without @Max" /><Text size={200} className={s.muted}>Only right after Max answered the same person</Text></div>
          <div className={s.limit}><Field label="Language"><Dropdown defaultValue="English"><Option>English</Option></Dropdown></Field></div>
          <div className={s.limit}><Switch defaultChecked={false} label="Digest needs a review before posting" /><Text size={200} className={s.muted}>The team lead checks the Monday digest first</Text></div>
        </div>
      </>
    );
  } else {
    content = (
      <>
        <div className={s.h2}>Review</div>
        <span className={s.sub}>Everything is saved. Max starts reading the chosen places now; the health view shows its progress.</span>
        {[["Places", "5 on · 1 off (personal) · windows 30-60 days"], ["Approvals", "6 rules · emails inside the company only"], ["Working hours", "Mon-Fri, 09:00-18:00 JST · nightly check 02:00"], ["Limits", "$1.00 / day · tests $5 / week · 3 private messages / person / day"], ["Style", "Emoji on · follow-ups on · English"]].map(([k, v]) => (
          <div key={k} style={{ display: "flex", gap: 16, padding: "10px 0", borderBottom: `1px solid ${tokens.colorNeutralStroke3}` }}>
            <CheckmarkCircle20Filled primaryFill={tokens.colorPaletteGreenForeground1} />
            <Text weight="semibold" style={{ width: 140 }}>{k}</Text><Text>{v}</Text>
          </div>
        ))}
      </>
    );
  }
  return (
    <div className={s.wizard}>
      <div className={mergeClasses(s.card, s.steps)}>
        <Text weight="semibold" size={300} style={{ padding: "4px 12px 10px", display: "block" }}>Set up Max</Text>
        {STEPS.map((name, i) => (
          <div key={name}>
            {i > 0 && <div className={s.stepLine} />}
            <div className={mergeClasses(s.step, i === step && s.stepActive)} onClick={() => setStep(i)}>
              <StepBubble i={i} now={step} />
              <Text weight={i === step ? "semibold" : "regular"}>{name}</Text>
            </div>
          </div>
        ))}
      </div>
      <div className={s.card}>
        {content}
        <div className={s.footer}>
          <Text size={200} className={s.muted}>Step {step + 1} of {STEPS.length}</Text>
          <div style={{ flex: 1 }} />
          {step > 0 && <Button onClick={() => setStep(step - 1)}>Back</Button>}
          <Button appearance="primary" onClick={() => setStep(Math.min(step + 1, STEPS.length - 1))}>{step === STEPS.length - 1 ? "Done" : "Save and continue"}</Button>
        </div>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ health
const CHATS_HEALTH = [
  { name: "Product Planning › General", updated: "11:14", behind: "—", horizon: "27 Oct", status: "ok" },
  { name: "Product Planning › New models", updated: "11:12", behind: "—", horizon: "27 Oct", status: "ok" },
  { name: "Product Planning › Pricing", updated: "08:10", behind: "3 h", horizon: "27 Sep", status: "behind" },
  { name: "Product Planning › Budget", updated: "10:58", behind: "—", horizon: "27 Oct", status: "ok" },
  { name: "New model sync", updated: "11:15", behind: "—", horizon: "27 Oct", status: "ok" },
  { name: "Procurement › Suppliers", updated: "11:09", behind: "—", horizon: "27 Oct", status: "ok" },
  { name: "Sales › Big accounts", updated: "—", behind: "—", horizon: "—", status: "error" },
];

function Tile({ label, icon, value, foot, tone }: { label: string; icon: ReactNode; value: ReactNode; foot: ReactNode; tone?: string }) {
  const s = useStyles();
  return (
    <div className={s.tile}>
      <span className={s.tileLabel}>{icon}{label}</span>
      <span className={s.tileValue} style={tone ? { color: tone } : undefined}>{value}</span>
      <Text size={200} className={s.muted}>{foot}</Text>
    </div>
  );
}

function HealthTab() {
  const s = useStyles();
  const status = (st: string) =>
    st === "ok" ? <Badge appearance="tint" color="success" icon={<CheckmarkCircle20Filled />}>Up to date</Badge>
      : st === "behind" ? <Badge appearance="tint" color="warning" icon={<Warning20Filled />}>Catching up</Badge>
        : <Badge appearance="tint" color="danger" icon={<ErrorCircle20Filled />}>No access</Badge>;
  return (
    <>
      <div className={s.tiles}>
        <Tile label="Places up to date" icon={<CheckmarkCircle20Filled primaryFill={tokens.colorPaletteGreenForeground1} />} value="5 of 7" foot="Updated within 30 s of a change" />
        <Tile label="Catching up" icon={<Warning20Filled primaryFill={tokens.colorPaletteMarigoldForeground1} />} value="1" foot="#Pricing: 3 h behind, ~2 min left" />
        <Tile label="Needs attention" icon={<ErrorCircle20Filled primaryFill={tokens.colorPaletteRedForeground1} />} value="1" foot="Sales › Big accounts: Max was removed" />
        <Tile label="Last nightly check" icon={<Clock20Regular />} value="02:00" foot="0 differences fixed · target 0" />
      </div>
      <div className={s.card}>
        <div className={s.h2}>Every place Max reads</div>
        <span className={s.sub}>"Read back to" is Max's knowledge horizon: older messages are not read.</span>
        <Table aria-label="Health per place">
          <TableHeader><TableRow>
            <TableHeaderCell>Place</TableHeaderCell><TableHeaderCell style={{ width: 130 }}>Last update</TableHeaderCell>
            <TableHeaderCell style={{ width: 110 }}>Behind by</TableHeaderCell><TableHeaderCell style={{ width: 130 }}>Read back to</TableHeaderCell>
            <TableHeaderCell style={{ width: 150 }}>Status</TableHeaderCell><TableHeaderCell style={{ width: 150 }} />
          </TableRow></TableHeader>
          <TableBody>
            {CHATS_HEALTH.map((c) => (
              <TableRow key={c.name}>
                <TableCell>{c.name}</TableCell>
                <TableCell>{c.updated}</TableCell>
                <TableCell style={c.status === "behind" ? { color: tokens.colorPaletteMarigoldForeground1, fontWeight: 600 } : undefined}>{c.behind}</TableCell>
                <TableCell>{c.horizon}</TableCell>
                <TableCell>{status(c.status)}</TableCell>
                <TableCell>
                  {c.status === "behind" && <Button size="small" icon={<ArrowSync16Regular />}>Catch up now</Button>}
                  {c.status === "error" && <Button size="small">How to fix</Button>}
                  {c.status === "ok" && <Button size="small" appearance="subtle">Read further back</Button>}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </>
  );
}

// ------------------------------------------------------------------ costs
const DAYS = [
  ["13", 0.21], ["14", 0.34], ["15", 0.05], ["16", 0.04], ["17", 0.41], ["18", 0.52], ["19", 0.38],
  ["20", 0.61], ["21", 0.47], ["22", 0.06], ["23", 0.03], ["24", 0.44], ["25", 0.58], ["26", 0.37],
] as const;
const BY_TASK = [["Answers", 0.19], ["Summaries", 0.07], ["Plans", 0.05], ["Briefs + digest", 0.03], ["Search (re-rank)", 0.02], ["Memory", 0.01]] as const;

function CostsTab() {
  const s = useStyles();
  const max = 1.0; // daily cap
  const scale = (v: number) => `${(v / max) * 100}%`;
  return (
    <>
      <div className={s.tiles}>
        <div className={s.tile}>
          <span className={s.tileLabel}>Today</span>
          <span className={s.tileValue}>$0.37</span>
          <ProgressBar value={0.37} thickness="large" />
          <Text size={200} className={s.muted}>37% of the $1.00 daily budget</Text>
        </div>
        <Tile label="This week" icon={null} value="$2.29" foot="Mon-Wed · last week $2.71" />
        <Tile label="Per answer (average)" icon={null} value="$0.006" foot="Target ≤ $0.01 · 61 answers today" />
        <div className={s.tile}>
          <span className={s.tileLabel}>Test budget (this week)</span>
          <span className={s.tileValue}>$1.80</span>
          <ProgressBar value={0.36} thickness="large" color="success" />
          <Text size={200} className={s.muted}>of $5.00 · nightly answer tests</Text>
        </div>
      </div>
      <div className={s.two}>
        <div className={s.card}>
          <div className={s.h2}>Spend per day</div>
          <span className={s.sub}>Last 14 days · dashed line = daily budget ($1.00)</span>
          <div className={s.chart}>
            {[0.25, 0.5, 0.75].map((g) => (
              <div key={g} className={s.gridLine} style={{ bottom: `${g * 100}%` }}><span className={s.yLabel}>${g.toFixed(2)}</span></div>
            ))}
            <div className={s.capLine} style={{ bottom: "100%" }}><span className={s.capLabel}>$1.00 budget</span></div>
            {DAYS.map(([d, v], i) => (
              <Tooltip key={d} content={`${d} Nov: $${v.toFixed(2)}`} relationship="label">
                <div className={s.barWrap}>
                  <div className={mergeClasses(s.bar, i === DAYS.length - 1 && s.barToday)} style={{ height: scale(v) }} />
                </div>
              </Tooltip>
            ))}
          </div>
          <div className={s.xLabels}>{DAYS.map(([d], i) => <span key={d} className={s.xLabel}>{i === DAYS.length - 1 ? "Today" : d}</span>)}</div>
        </div>
        <div className={s.card}>
          <div className={s.h2}>Today by kind of work</div>
          <span className={s.sub}>Where today's $0.37 went</span>
          {BY_TASK.map(([k, v]) => (
            <div key={k} className={s.hbarRow}>
              <Text size={200}>{k}</Text>
              <div className={s.hbarTrack}><div className={s.hbarFill} style={{ width: `${(v / 0.19) * 100}%` }} /></div>
              <Text size={200} className={s.num}>${v.toFixed(2)}</Text>
            </div>
          ))}
          <div className={s.note}>
            <DataBarVertical20Regular />
            <Text size={200}>Main model handled 98% of calls; the backup model 2% (2 time-outs). Speech and the local voice are free.</Text>
          </div>
        </div>
      </div>
    </>
  );
}

// ------------------------------------------------------------------ my settings (everyone)
function MySettingsTab({ me }: { me: PersonId }) {
  const s = useStyles();
  return (
    <div className={s.card} style={{ maxWidth: 760 }}>
      <div className={s.h2}>My settings</div>
      <span className={s.sub}>Only for you, {personName(me)}.</span>
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <Switch defaultChecked label="Reminders and chases about my tasks" />
        <Switch defaultChecked label="Meeting briefs before my meetings" />
        <Switch defaultChecked label="Morning summary of my day" />
        <Switch defaultChecked={false} label="Weekly digest also as a private message" />
      </div>
      <div className={s.note}><Person20Regular />
        <Text size={200}>To see or correct what Max remembers about you, ask Max in your chat: "What do you know about me?"</Text></div>
    </div>
  );
}

export function MaxApp({ me, initialTab, initialStep, onOpen }: { me: PersonId; initialTab?: string; initialStep?: number; onOpen?: (to: NavTarget) => void }) {
  const s = useStyles();
  const admin = ADMINS.includes(me);
  const [tab, setTab] = useState(initialTab && (admin || initialTab === "mine" || initialTab === "home") && (me === "karthi" || !["search", "runs"].includes(initialTab)) ? initialTab : "home");
  const person = PEOPLE.find((p) => p.id === me)!;
  return (
    <div className={s.page}>
      <div className={s.hero}>
        <div style={{ paddingBottom: 14 }}><MaxAvatar size={52} /></div>
        <div className={s.heroText}>
          <div className={s.heroName}>Max</div>
          <Text className={s.muted}>Your AI teammate · Thirdwave · Product Planning</Text>
        </div>
        <div style={{ paddingBottom: 14, marginLeft: 12 }}>
          <Badge appearance="outline" icon={<Avatar size={16} name={person.name} color={person.color} />}>
            {admin ? (me === "karthi" ? "Developer and admin" : "Team lead") : "Member"}
          </Badge>
        </div>
        <TabList className={s.tabs} selectedValue={tab} onTabSelect={(_, d) => setTab(String(d.value))}>
          <Tab value="home" icon={<Home20Regular />}>Home</Tab>
          {admin && <Tab value="setup" icon={<Settings20Regular />}>Setup</Tab>}
          {admin && <Tab value="health" icon={<HeartPulse20Regular />}>Health</Tab>}
          {admin && <Tab value="costs" icon={<DataBarVertical20Regular />}>Costs</Tab>}
          {me === "karthi" && <Tab value="search" icon={<Search20Regular />}>Search tester</Tab>}
          {me === "karthi" && <Tab value="runs" icon={<Code20Regular />}>Runs</Tab>}
          <Tab value="mine" icon={<Person20Regular />}>My settings</Tab>
        </TabList>
      </div>
      <div className={s.body}>
        <div className={s.inner}>
          {tab === "home" && <MaxHome me={me} onOpen={onOpen} onSettings={() => setTab("mine")} />}
          {tab === "setup" && <SetupTab initialStep={initialStep ?? 0} />}
          {tab === "health" && <HealthTab />}
          {tab === "costs" && <CostsTab />}
          {tab === "mine" && <MySettingsTab me={me} />}
          {tab === "search" && <SearchTester />}
          {tab === "runs" && <RunViewer />}
        </div>
      </div>
    </div>
  );
}
