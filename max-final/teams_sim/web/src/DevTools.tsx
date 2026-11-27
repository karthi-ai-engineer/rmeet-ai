// UI design mock-ups: developer tools (Karthi only): Search tester and Run viewer. Static data.
import { useState } from "react";
import {
  Badge,
  Button,
  Dropdown,
  Input,
  Option,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  Text,
  makeStyles, shorthands,
  mergeClasses,
  tokens,
} from "@fluentui/react-components";
import {
  ArrowRight16Regular,
  ChevronDown16Regular,
  ChevronRight16Regular,
  CheckmarkCircle16Filled,
  Play20Filled,
  Search20Regular,
} from "@fluentui/react-icons";
import { personName } from "./ui";

const useStyles = makeStyles({
  card: { backgroundColor: tokens.colorNeutralBackground1, borderRadius: tokens.borderRadiusXLarge, boxShadow: tokens.shadow4, padding: "20px 22px", marginBottom: "18px" },
  h2: { fontSize: tokens.fontSizeBase500, fontWeight: tokens.fontWeightSemibold },
  muted: { color: tokens.colorNeutralForeground3 },
  mono: { fontFamily: tokens.fontFamilyMonospace, fontSize: tokens.fontSizeBase200 },
  queryRow: { display: "flex", gap: "10px", alignItems: "center", marginTop: "12px" },
  pipe: { display: "flex", alignItems: "stretch", gap: "6px", marginTop: "16px", flexWrap: "wrap" },
  stage: {
    flex: "1 1 140px", padding: "10px 12px", borderRadius: tokens.borderRadiusLarge, border: `1px solid ${tokens.colorNeutralStroke2}`,
    display: "flex", flexDirection: "column", gap: "2px", backgroundColor: tokens.colorNeutralBackground2,
  },
  stageAi: { ...shorthands.borderColor("#F7630C55"), backgroundColor: "#F7630C0D" },
  stageNum: { fontSize: tokens.fontSizeBase500, fontWeight: tokens.fontWeightSemibold, fontVariantNumeric: "tabular-nums" },
  arrow: { display: "flex", alignItems: "center", color: tokens.colorNeutralForeground3 },
  pass: { display: "flex", alignItems: "center", gap: "8px", marginTop: "14px", padding: "10px 12px", borderRadius: tokens.borderRadiusLarge, backgroundColor: tokens.colorPaletteGreenBackground1 },
  rank: { fontVariantNumeric: "tabular-nums", textAlign: "right" },
  scoreTrack: { height: "6px", width: "80px", borderRadius: "3px", backgroundColor: tokens.colorNeutralBackground4, display: "inline-block", verticalAlign: "middle", marginRight: "6px" },
  scoreFill: { height: "100%", borderRadius: "3px", backgroundColor: tokens.colorBrandBackground },
  // runs
  runs: { display: "grid", gridTemplateColumns: "380px 1fr", gap: "18px", alignItems: "start" },
  runItem: { display: "grid", gridTemplateColumns: "1fr auto", gap: "2px 8px", padding: "10px 12px", borderRadius: tokens.borderRadiusLarge, cursor: "pointer", ":hover": { backgroundColor: tokens.colorNeutralBackground1Hover } },
  runActive: { backgroundColor: tokens.colorNeutralBackground1Selected },
  totals: { display: "grid", gridTemplateColumns: "repeat(5, minmax(0, 1fr))", gap: "10px", margin: "14px 0 18px" },
  total: { padding: "10px 12px", borderRadius: tokens.borderRadiusLarge, backgroundColor: tokens.colorNeutralBackground2 },
  stepRow: { display: "grid", gridTemplateColumns: "20px 120px 1fr 70px 70px", alignItems: "center", gap: "10px", padding: "8px 6px", borderTop: `1px solid ${tokens.colorNeutralStroke3}`, cursor: "pointer" },
  dot: { width: "10px", height: "10px", borderRadius: "50%" },
  detail: { margin: "0 6px 10px 36px", padding: "10px 12px", borderRadius: tokens.borderRadiusMedium, backgroundColor: tokens.colorNeutralBackground3, whiteSpace: "pre-wrap" },
});

// ------------------------------------------------------------------ search tester
const RESULTS = [
  { rank: 1, title: "Parts prices.xlsx › Memory › rows 1-12", kw: 1, mean: 3, score: 0.94, snippet: "DDR5 32 GB | Sep 13,600 | Oct 14,200 | Nov 16,900 …", expected: true },
  { rank: 2, title: "Pricing thread, 20 Nov (post + 2 replies)", kw: 4, mean: 1, score: 0.88, snippet: "Decision from today's pricing review: all desktop models go up 5% …", expected: true },
  { rank: 3, title: "Price change plan Q1.pptx › slide 4", kw: 9, mean: 2, score: 0.71, snippet: "Memory cost vs. desktop price (chart) …" },
  { rank: 4, title: "Pricing thread, 24 Nov (Praga)", kw: 2, mean: 7, score: 0.66, snippet: "New memory quotes are in the sheet … 32 GB DDR5 is up again …" },
  { rank: 5, title: "Supplier B quote (scanned).pdf › page 1", kw: 12, mean: 5, score: 0.41, snippet: "Quotation … DDR5 modules … valid until 30 Nov …" },
];

export function SearchTester() {
  const s = useStyles();
  return (
    <>
      <div className={s.card}>
        <div className={s.h2}>Search tester</div>
        <Text size={200} className={s.muted}>See exactly what Max finds for a question, step by step. Asking "as" a person applies their privacy filter.</Text>
        <div className={s.queryRow}>
          <Input style={{ flex: 1 }} size="large" contentBefore={<Search20Regular />}
            defaultValue="How much did the 32 GB memory price change since October, and what did we decide?" />
          <Dropdown defaultValue="as Rachitaa" style={{ minWidth: 150 }}>
            {["as Prince", "as Praga", "as Rachitaa", "as Karthi"].map((o) => <Option key={o}>{o}</Option>)}
          </Dropdown>
          <Button appearance="primary" icon={<Play20Filled />} size="large">Run</Button>
        </div>
        <div className={s.pipe}>
          {[
            ["1 Understand", "3 phrasings", "dates: since 1 Oct", "AI · 420 ms · $0.0003", true],
            ["2 Privacy filter", "1,240", "of 1,310 pieces allowed", "code · 3 ms", false],
            ["3a Keyword", "50", "top 50", "code · 18 ms", false],
            ["3b Meaning", "50", "top 50", "code · 41 ms", false],
            ["4 Merge", "40", "weighted merge", "code · 1 ms", false],
            ["5 Re-rank", "8", "best 8 of 40", "AI · 1.3 s · $0.0014", true],
          ].map(([name, num, what, cost, ai], i) => (
            <div key={String(name)} style={{ display: "contents" }}>
              {i > 0 && <span className={s.arrow}><ArrowRight16Regular /></span>}
              <div className={mergeClasses(s.stage, ai && s.stageAi)}>
                <Text size={200} weight="semibold">{name}</Text>
                <span className={s.stageNum}>{num}</span>
                <Text size={200} className={s.muted}>{what}</Text>
                <Text size={100} className={s.muted}>{cost}</Text>
              </div>
            </div>
          ))}
        </div>
        <div className={s.pass}>
          <CheckmarkCircle16Filled primaryFill={tokens.colorPaletteGreenForeground1} />
          <Text size={200}><b>Test question Q-047:</b> both expected sources found (rank 1 and 2) · total 1.8 s · $0.0017</Text>
        </div>
      </div>
      <div className={s.card}>
        <div className={s.h2}>Best 8 after re-rank <Text size={200} className={s.muted}>(top 5 shown)</Text></div>
        <Table size="small" aria-label="Search results">
          <TableHeader><TableRow>
            <TableHeaderCell style={{ width: 50 }}>#</TableHeaderCell><TableHeaderCell>Piece</TableHeaderCell>
            <TableHeaderCell style={{ width: 90 }}>Keyword</TableHeaderCell><TableHeaderCell style={{ width: 90 }}>Meaning</TableHeaderCell>
            <TableHeaderCell style={{ width: 150 }}>Re-rank score</TableHeaderCell>
          </TableRow></TableHeader>
          <TableBody>
            {RESULTS.map((r) => (
              <TableRow key={r.rank}>
                <TableCell className={s.rank}>{r.rank}</TableCell>
                <TableCell>
                  <Text weight="semibold">{r.title}</Text> {r.expected && <Badge size="small" appearance="tint" color="success">expected</Badge>}
                  <div className={s.mono} style={{ color: tokens.colorNeutralForeground3 }}>{r.snippet}</div>
                </TableCell>
                <TableCell className={s.rank}>#{r.kw}</TableCell>
                <TableCell className={s.rank}>#{r.mean}</TableCell>
                <TableCell>
                  <span className={s.scoreTrack}><span className={s.scoreFill} style={{ width: `${r.score * 100}%`, display: "block" }} /></span>
                  <span className={s.mono}>{r.score.toFixed(2)}</span>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </>
  );
}

// ------------------------------------------------------------------ run viewer
interface Step { kind: "code" | "ai" | "tool" | "gate" | "reply"; name: string; what: string; ms: number; cost: number; detail: string }
interface Run { id: string; time: string; who: string; task: string; status: "done" | "waiting" | "stopped" | "failed"; ms: number; cost: number; ask: string; steps: Step[] }

const RUNS: Run[] = [
  {
    id: "r1", time: "09:12", who: "rachitaa", task: "answer", status: "done", ms: 6400, cost: 0.0071,
    ask: "@Max how much did the 32 GB memory price change since October, and what did we decide about prices?",
    steps: [
      { kind: "code", name: "INTAKE", what: "answer · audience: Product Planning › Pricing (3 people)", ms: 12, cost: 0, detail: "task type: answer (skill answer.md)\naudience: prince, rachitaa, karthi\nbudget: 8 steps · 60 s · $0.02" },
      { kind: "code", name: "PREPARE", what: "instructions + skill + last 20 messages + 1 lesson", ms: 30, cost: 0, detail: "lesson used: \"For memory prices, use the Parts prices sheet, not the slides.\" (accepted by Prince)" },
      { kind: "ai", name: "THINK", what: "→ search_knowledge (+2 phrasings, since 1 Oct)", ms: 900, cost: 0.0009, detail: "model: main (flash-lite) · 2,140 in / 96 out tokens" },
      { kind: "tool", name: "search_knowledge", what: "8 pieces (re-ranked)", ms: 1800, cost: 0.0017, detail: "top: Parts prices.xlsx › Memory (0.94), Pricing thread 20 Nov (0.88)" },
      { kind: "ai", name: "THINK", what: "→ query_sheet (Memory, DDR5 32 GB, Oct + Nov)", ms: 700, cost: 0.0008, detail: "" },
      { kind: "tool", name: "query_sheet", what: "Oct 14,200 · Nov 16,900", ms: 40, cost: 0, detail: "rows used: 5 (Oct), 5 (Nov)" },
      { kind: "tool", name: "calc", what: "(16900 - 14200) / 14200 = +19.0%", ms: 2, cost: 0, detail: "" },
      { kind: "ai", name: "THINK", what: "writes the answer (status: answered)", ms: 1600, cost: 0.0024, detail: "" },
      { kind: "gate", name: "CHECKS", what: "sources real ✓ · numbers match tools ✓ · fact-check ✓", ms: 1200, cost: 0.0013, detail: "fact-check: 2 claims, both supported" },
      { kind: "reply", name: "REPLY", what: "posted in thread with 2 sources", ms: 110, cost: 0, detail: "" },
    ],
  },
  {
    id: "r2", time: "10:41", who: "rachitaa", task: "email", status: "waiting", ms: 4100, cost: 0.0052, ask: "@Max email Prince the Q1 pricing summary",
    steps: [
      { kind: "code", name: "INTAKE", what: "email · 1:1 chat", ms: 10, cost: 0, detail: "" },
      { kind: "ai", name: "THINK", what: "→ search_knowledge", ms: 800, cost: 0.0008, detail: "" },
      { kind: "tool", name: "search_knowledge", what: "8 pieces", ms: 1700, cost: 0.0016, detail: "" },
      { kind: "ai", name: "THINK", what: "→ send_email (draft)", ms: 1500, cost: 0.0028, detail: "" },
      { kind: "gate", name: "GATES", what: "send_email is L3 → approval card to Rachitaa", ms: 90, cost: 0, detail: "waiting since 10:41 · expires in 24 h" },
    ],
  },
  { id: "r3", time: "08:41", who: "prince", task: "answer", status: "done", ms: 3900, cost: 0.0044, ask: "What's on my plate this week?", steps: [] },
  { id: "r4", time: "08:02", who: "praga", task: "summary", status: "stopped", ms: 12000, cost: 0.006, ask: "@Max summarise all supplier threads this month", steps: [] },
];

const KIND_COLOR: Record<Step["kind"], string> = { code: "#0F6CBD", ai: "#F7630C", tool: "#107C10", gate: "#C19C00", reply: "#5B5FC7" };
const STATUS: Record<Run["status"], { label: string; color: "success" | "warning" | "informative" | "danger" }> = {
  done: { label: "Done", color: "success" }, waiting: { label: "Waiting approval", color: "warning" },
  stopped: { label: "Stopped", color: "informative" }, failed: { label: "Failed", color: "danger" },
};

export function RunViewer() {
  const s = useStyles();
  const [openId, setOpenId] = useState("r1");
  const [expanded, setExpanded] = useState<number | null>(3);
  const run = RUNS.find((r) => r.id === openId)!;
  return (
    <div className={s.runs}>
      <div className={s.card} style={{ padding: "14px 10px" }}>
        <Text weight="semibold" style={{ padding: "0 12px 8px", display: "block" }}>Runs today</Text>
        {RUNS.map((r) => (
          <div key={r.id} className={mergeClasses(s.runItem, r.id === openId && s.runActive)} onClick={() => { setOpenId(r.id); setExpanded(null); }}>
            <Text weight="semibold">{r.time} · {personName(r.who)} · {r.task}</Text>
            <Badge size="small" appearance="tint" color={STATUS[r.status].color}>{STATUS[r.status].label}</Badge>
            <Text size={200} className={s.muted} style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.ask}</Text>
            <Text size={200} className={s.muted}>{(r.ms / 1000).toFixed(1)} s · ${r.cost.toFixed(4)}</Text>
          </div>
        ))}
      </div>
      <div className={s.card}>
        <div className={s.h2}>{run.time} · {personName(run.who)} · {run.task}</div>
        <Text size={200} className={s.muted}>"{run.ask}"</Text>
        <div className={s.totals}>
          {[["Status", STATUS[run.status].label], ["Time", `${(run.ms / 1000).toFixed(1)} s`], ["Cost", `$${run.cost.toFixed(4)}`], ["Tool steps", `${run.steps.filter((x) => x.kind === "tool").length} of 8 allowed`], ["Model", "main (flash-lite)"]].map(([k, v]) => (
            <div key={k} className={s.total}><Text size={100} className={s.muted} block>{k}</Text><Text weight="semibold">{v}</Text></div>
          ))}
        </div>
        {run.steps.length === 0 && <Text className={s.muted}>Steps are shown for the first two runs in this mock-up.</Text>}
        {run.steps.map((st, i) => (
          <div key={i}>
            <div className={s.stepRow} onClick={() => setExpanded(expanded === i ? null : i)}>
              {st.detail ? (expanded === i ? <ChevronDown16Regular /> : <ChevronRight16Regular />) : <span />}
              <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span className={s.dot} style={{ backgroundColor: KIND_COLOR[st.kind] }} />
                <Text weight="semibold" size={200}>{st.name}</Text>
              </span>
              <Text size={200}>{st.what}</Text>
              <Text size={200} className={s.muted} style={{ textAlign: "right" }}>{st.ms >= 1000 ? `${(st.ms / 1000).toFixed(1)} s` : `${st.ms} ms`}</Text>
              <Text size={200} className={s.muted} style={{ textAlign: "right" }}>{st.cost ? `$${st.cost.toFixed(4)}` : "—"}</Text>
            </div>
            {expanded === i && st.detail && <div className={mergeClasses(s.detail, s.mono)}>{st.detail}</div>}
          </div>
        ))}
        <div style={{ display: "flex", gap: 14, marginTop: 14 }}>
          {Object.entries({ code: "Code", ai: "AI", tool: "Tool", gate: "Checks / gates", reply: "Reply" }).map(([k, v]) => (
            <Text key={k} size={200} className={s.muted}><span style={{ color: KIND_COLOR[k as Step["kind"]] }}>●</span> {v}</Text>
          ))}
        </div>
      </div>
    </div>
  );
}
