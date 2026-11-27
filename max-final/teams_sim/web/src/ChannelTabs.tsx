// A channel's Files tab and Plans tab. Files: real files from the simulator server (ChannelFiles) or the
// design mock-up on static data (FilesTab, showcase mode). Plans: still the mock-up.
import { useEffect, useState, type JSX } from "react";
import {
  Avatar,
  Badge,
  Button,
  Link,
  ProgressBar,
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
  makeStyles,
  mergeClasses,
  tokens,
} from "@fluentui/react-components";
import {
  ArrowUpload20Regular,
  Board20Regular,
  GanttChart20Regular,
  TextBulletListLtr20Regular,
  ChevronDown16Regular,
  ChevronRight16Regular,
  Dismiss20Regular,
  Document24Regular,
  DocumentPdf24Regular,
  DocumentText24Regular,
  Image24Regular,
  Open16Regular,
  SlideText24Regular,
  Table24Regular,
} from "@fluentui/react-icons";
import { PEOPLE, type PersonId } from "./mock";
import { MaxAvatar, personName } from "./ui";
import { api, fileSize, fileTime, type ApiFile } from "./api";

const useStyles = makeStyles({
  page: { flex: 1, display: "flex", minHeight: 0 },
  main: { flex: 1, overflowY: "auto", padding: "16px 20px" },
  bar: { display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" },
  card: { backgroundColor: tokens.colorNeutralBackground1, borderRadius: tokens.borderRadiusLarge, boxShadow: tokens.shadow2 },
  row: { cursor: "pointer" },
  rowActive: { backgroundColor: tokens.colorNeutralBackground1Selected },
  muted: { color: tokens.colorNeutralForeground3 },
  preview: {
    width: "420px", flexShrink: 0, display: "flex", flexDirection: "column", overflowY: "auto",
    backgroundColor: tokens.colorNeutralBackground1, borderLeft: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  previewHead: { display: "flex", alignItems: "center", gap: "10px", padding: "12px 12px 12px 16px", borderBottom: `1px solid ${tokens.colorNeutralStroke2}` },
  previewBody: { padding: "16px", display: "flex", flexDirection: "column", gap: "12px" },
  sheet: { borderCollapse: "collapse", fontSize: tokens.fontSizeBase200, width: "100%" },
  sheetCell: { border: `1px solid ${tokens.colorNeutralStroke2}`, padding: "4px 6px", textAlign: "right" },
  sheetHead: { backgroundColor: tokens.colorNeutralBackground3, fontWeight: tokens.fontWeightSemibold, textAlign: "left" },
  slide: {
    aspectRatio: "16 / 9", borderRadius: tokens.borderRadiusMedium, border: `1px solid ${tokens.colorNeutralStroke2}`,
    padding: "14px", display: "flex", flexDirection: "column", gap: "8px", backgroundColor: tokens.colorNeutralBackground2,
  },
  bars: { flex: 1, display: "flex", alignItems: "flex-end", gap: "10px", paddingTop: "6px" },
  // real files
  frame: {
    width: "100%", height: "520px", border: `1px solid ${tokens.colorNeutralStroke2}`, borderRadius: tokens.borderRadiusMedium,
    backgroundColor: tokens.colorNeutralBackground3,
  },
  image: { maxWidth: "100%", borderRadius: tokens.borderRadiusMedium, border: `1px solid ${tokens.colorNeutralStroke2}` },
  note: {
    display: "flex", flexDirection: "column", alignItems: "center", gap: "8px", padding: "32px 16px", textAlign: "center",
    borderRadius: tokens.borderRadiusMedium, backgroundColor: tokens.colorNeutralBackground2, color: tokens.colorNeutralForeground3,
  },
  versions: { display: "flex", flexDirection: "column", borderTop: `1px solid ${tokens.colorNeutralStroke2}` },
  version: {
    display: "flex", alignItems: "center", gap: "10px", padding: "8px 0", fontSize: tokens.fontSizeBase200,
    borderBottom: `1px solid ${tokens.colorNeutralStroke3}`,
  },
  empty: { padding: "40px", textAlign: "center", color: tokens.colorNeutralForeground3 },
  // plans
  plan: { marginBottom: "14px", overflow: "hidden" },
  planHead: { display: "flex", alignItems: "center", gap: "14px", padding: "14px 16px", cursor: "pointer" },
  planTitle: { fontWeight: tokens.fontWeightSemibold, fontSize: tokens.fontSizeBase400 },
  progress: { width: "160px" },
  late: { color: tokens.colorPaletteRedForeground1, fontWeight: tokens.fontWeightSemibold },
  blockedNote: { color: tokens.colorNeutralForeground3, fontSize: tokens.fontSizeBase200 },
});

// ------------------------------------------------------------------ Files
type Kind = "xlsx" | "pptx" | "docx" | "pdf" | "png" | "other"; // png = any image
interface FileRow { name: string; kind: Kind; by: PersonId | string; when: string; size: string; version?: number; note?: string }

const FILES: FileRow[] = [
  { name: "Parts prices.xlsx", kind: "xlsx", by: "praga", when: "Mon 24 Nov", size: "84 KB", version: 3 },
  { name: "Price change plan Q1.pptx", kind: "pptx", by: "prince", when: "Thu 20 Nov", size: "2.1 MB", note: "charts" },
  { name: "New model spec.docx", kind: "docx", by: "prince", when: "Tue 18 Nov", size: "220 KB", version: 2 },
  { name: "Supplier B quote (scanned).pdf", kind: "pdf", by: "praga", when: "Mon 17 Nov", size: "1.4 MB", note: "scanned" },
  { name: "Big accounts pricing.xlsx", kind: "xlsx", by: "rachitaa", when: "Wed 12 Nov", size: "56 KB" },
  { name: "Whiteboard pricing session.png", kind: "png", by: "prince", when: "Mon 10 Nov", size: "3.2 MB" },
];

const ICONS: Record<Kind, { icon: JSX.Element; color: string }> = {
  xlsx: { icon: <Table24Regular />, color: "#107C41" },
  pptx: { icon: <SlideText24Regular />, color: "#C43E1C" },
  docx: { icon: <DocumentText24Regular />, color: "#185ABD" },
  pdf: { icon: <DocumentPdf24Regular />, color: "#D13438" },
  png: { icon: <Image24Regular />, color: "#8764B8" },
  other: { icon: <Document24Regular />, color: tokens.colorNeutralForeground2 },
};

/** The file kind by its extension ("Parts prices.xlsx" -> xlsx, ".jpg" -> image). */
function kindOf(name: string): Kind {
  const ext = name.split(".").pop()?.toLowerCase() ?? "";
  if (["jpg", "jpeg", "png", "gif", "webp"].includes(ext)) return "png";
  return (["xlsx", "pptx", "docx", "pdf"] as const).find((k) => k === ext) ?? "other";
}
const APP: Partial<Record<Kind, string>> = { xlsx: "Excel", pptx: "PowerPoint", docx: "Word" };

function FileIcon({ kind }: { kind: Kind }) {
  return <span style={{ color: ICONS[kind].color, display: "inline-flex" }}>{ICONS[kind].icon}</span>;
}

function Preview({ f, onClose }: { f: FileRow; onClose: () => void }) {
  const s = useStyles();
  return (
    <aside className={s.preview}>
      <div className={s.previewHead}>
        <FileIcon kind={f.kind} />
        <Text weight="semibold" style={{ flex: 1 }}>{f.name}</Text>
        <Button appearance="subtle" icon={<Open16Regular />}>Open</Button>
        <Button appearance="subtle" icon={<Dismiss20Regular />} onClick={onClose} aria-label="Close preview" />
      </div>
      <div className={s.previewBody}>
        <Text size={200} className={s.muted}>
          Changed {f.when} by {personName(f.by)} · {f.size}{f.version ? ` · version ${f.version}` : ""}
        </Text>
        {f.kind === "xlsx" && (
          <>
            <TabList size="small" defaultSelectedValue="Memory">
              <Tab value="Memory">Memory</Tab><Tab value="GPU">GPU</Tab><Tab value="SSD">SSD</Tab><Tab value="Summary">Summary</Tab>
            </TabList>
            <table className={s.sheet}>
              <thead>
                <tr>{["Part", "Sep", "Oct", "Nov", "Change"].map((h) => <th key={h} className={mergeClasses(s.sheetCell, s.sheetHead)}>{h}</th>)}</tr>
              </thead>
              <tbody>
                {[["DDR5 16 GB", "7,400", "7,900", "9,100", "+15%"], ["DDR5 32 GB", "13,600", "14,200", "16,900", "+19%"], ["DDR5 64 GB", "26,800", "27,500", "31,600", "+15%"]].map((r) => (
                  <tr key={r[0]}>{r.map((c, i) => <td key={i} className={mergeClasses(s.sheetCell, i === 0 && s.sheetHead)}>{c}</td>)}</tr>
                ))}
              </tbody>
            </table>
            <Text size={200} className={s.muted}>Prices in ¥ per unit (invented test data).</Text>
          </>
        )}
        {f.kind === "pptx" && (
          <div className={s.slide}>
            <Text weight="semibold">Memory cost vs. desktop price</Text>
            <div className={s.bars}>
              {[38, 46, 61, 74].map((h, i) => (
                <div key={i} style={{ flex: 1, height: `${h}%`, borderRadius: 3, background: i === 3 ? "#C43E1C" : tokens.colorBrandBackground }} />
              ))}
            </div>
            <Text size={100} className={s.muted}>Slide 4 of 12 · chart image</Text>
          </div>
        )}
        {(f.kind === "docx" || f.kind === "pdf" || f.kind === "png") && (
          <div className={s.slide} style={{ aspectRatio: "3 / 4" }}>
            <Text weight="semibold">{f.name.replace(/\.\w+$/, "")}</Text>
            <Text size={200} className={s.muted}>
              {f.kind === "png" ? "Photo preview" : "Page 1 of 6"}{f.note === "scanned" ? " · scanned document" : ""}
            </Text>
          </div>
        )}
      </div>
    </aside>
  );
}

export function FilesTab() {
  const s = useStyles();
  const [open, setOpen] = useState<FileRow | null>(FILES[0]);
  return (
    <div className={s.page}>
      <div className={s.main}>
        <div className={s.bar}>
          <Button appearance="primary" icon={<ArrowUpload20Regular />}>Upload</Button>
          <Text className={s.muted} size={200}>{FILES.length} files</Text>
        </div>
        <div className={s.card}>
          <Table size="medium" aria-label="Files">
            <TableHeader>
              <TableRow>
                <TableHeaderCell>Name</TableHeaderCell>
                <TableHeaderCell style={{ width: 150 }}>Modified</TableHeaderCell>
                <TableHeaderCell style={{ width: 170 }}>Modified by</TableHeaderCell>
                <TableHeaderCell style={{ width: 90 }}>Size</TableHeaderCell>
              </TableRow>
            </TableHeader>
            <TableBody>
              {FILES.map((f) => {
                const p = PEOPLE.find((x) => x.id === f.by);
                return (
                  <TableRow key={f.name} className={mergeClasses(s.row, open?.name === f.name && s.rowActive)} onClick={() => setOpen(f)}>
                    <TableCell>
                      <TableCellLayout media={<FileIcon kind={f.kind} />}>
                        {f.name}{" "}
                        {f.version && <Badge appearance="outline" size="small" color="informative">v{f.version}</Badge>}
                      </TableCellLayout>
                    </TableCell>
                    <TableCell>{f.when}</TableCell>
                    <TableCell>
                      <TableCellLayout media={<Avatar size={20} name={personName(f.by)} color={p?.color} />}>{personName(f.by)}</TableCellLayout>
                    </TableCell>
                    <TableCell className={s.muted}>{f.size}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      </div>
      {open && <Preview f={open} onClose={() => setOpen(null)} />}
    </div>
  );
}

// ------------------------------------------------------------------ Files, real: from the simulator server
const colorOf = (id: string) => PEOPLE.find((p) => p.id === id)?.color ?? "neutral"; // background people: neutral

function FilePreview({ f, me, onClose }: { f: ApiFile; me: string; onClose: () => void }) {
  const s = useStyles();
  const kind = kindOf(f.name);
  const url = api.fileUrl(me, f.id);
  return (
    <aside className={s.preview} data-testid="file-preview" data-file-name={f.name}>
      <div className={s.previewHead}>
        <FileIcon kind={kind} />
        <Text weight="semibold" style={{ flex: 1, minWidth: 0, overflowWrap: "anywhere" }}>{f.name}</Text>
        <Button as="a" href={url} target="_blank" rel="noopener" appearance="subtle" icon={<Open16Regular />} data-testid="file-open">Open</Button>
        <Button appearance="subtle" icon={<Dismiss20Regular />} onClick={onClose} aria-label="Close preview" />
      </div>
      <div className={s.previewBody}>
        <Text size={200} className={s.muted}>
          Changed {fileTime(f.at)} by {personName(f.by)} · {fileSize(f.size)} · version {f.version}
        </Text>
        {kind === "png" && <img className={s.image} src={url} alt={f.name} />}
        {kind === "pdf" && <iframe className={s.frame} src={url} title={f.name} />}
        {kind !== "png" && kind !== "pdf" && (
          <div className={s.note}>
            <FileIcon kind={kind} />
            <Text size={200}>Preview opens in {APP[kind] ?? "its app"}.</Text>
            <Button as="a" href={url} target="_blank" rel="noopener" size="small" icon={<Open16Regular />}>Open</Button>
          </div>
        )}
        <div>
          <Text weight="semibold" block style={{ marginBottom: 6 }}>Versions</Text>
          <div className={s.versions}>
            {[...f.versions].reverse().map((v) => (
              <div key={v.v} className={s.version} data-testid="file-version" data-v={v.v}>
                <Badge appearance={v.v === f.version ? "filled" : "outline"} size="small" color="informative">v{v.v}</Badge>
                <span style={{ flex: 1 }}>
                  {fileTime(v.at)} · {personName(v.by)} · <span className={s.muted}>{fileSize(v.size)}</span>
                </span>
                <Link href={api.fileUrl(me, f.id, v.v)} target="_blank" rel="noopener">Open</Link>
              </div>
            ))}
          </div>
        </div>
      </div>
    </aside>
  );
}

/** The channel's real files: list (newest change first) + preview of the picked one. `reload` bumps = load again. */
export function ChannelFiles({ me, channel, reload, initialFile }: { me: string; channel: string; reload?: number; initialFile?: string | null }) {
  const s = useStyles();
  const [files, setFiles] = useState<ApiFile[] | null>(null);
  const [error, setError] = useState(false);
  const [openId, setOpenId] = useState<string | null | undefined>(initialFile ?? undefined); // undefined = first file
  useEffect(() => {
    let gone = false;
    setError(false);
    api.files(me, channel).then((fs) => { if (!gone) setFiles(fs); }, () => { if (!gone) { setFiles([]); setError(true); } });
    return () => { gone = true; };
  }, [me, channel, reload]);
  // the picked file; none picked yet (or the linked one isn't here) = the newest; closed = none
  const open = openId === null ? null : files?.find((f) => f.id === openId) ?? files?.[0] ?? null;
  return (
    <div className={s.page}>
      <div className={s.main}>
        <div className={s.bar}>
          <Tooltip content="Uploading comes later" relationship="description">
            <Button appearance="primary" icon={<ArrowUpload20Regular />} disabledFocusable>Upload</Button>
          </Tooltip>
          {files && <Text className={s.muted} size={200}>{files.length} {files.length === 1 ? "file" : "files"}</Text>}
        </div>
        <div className={s.card}>
          {files === null ? <div className={s.empty}>Loading files…</div>
            : error ? <div className={s.empty}>Couldn't load the files of this channel.</div>
            : files.length === 0 ? <div className={s.empty} data-testid="files-empty">No files in this channel yet.</div>
            : (
              <Table size="medium" aria-label="Files">
                <TableHeader>
                  <TableRow>
                    <TableHeaderCell>Name</TableHeaderCell>
                    <TableHeaderCell style={{ width: 150 }}>Modified</TableHeaderCell>
                    <TableHeaderCell style={{ width: 170 }}>Modified by</TableHeaderCell>
                    <TableHeaderCell style={{ width: 90 }}>Size</TableHeaderCell>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {files.map((f) => (
                    <TableRow key={f.id} className={mergeClasses(s.row, open?.id === f.id && s.rowActive)} onClick={() => setOpenId(f.id)}
                      data-testid="file-row" data-file-name={f.name}>
                      <TableCell>
                        <TableCellLayout media={<FileIcon kind={kindOf(f.name)} />}>
                          {f.name}{" "}
                          {f.version > 1 && <Badge appearance="outline" size="small" color="informative">v{f.version}</Badge>}
                        </TableCellLayout>
                      </TableCell>
                      <TableCell>{fileTime(f.at)}</TableCell>
                      <TableCell>
                        <TableCellLayout media={<Avatar size={20} name={personName(f.by)} color={colorOf(f.by)} />}>{personName(f.by)}</TableCellLayout>
                      </TableCell>
                      <TableCell className={s.muted}>{fileSize(f.size)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
        </div>
      </div>
      {open && <FilePreview key={open.id} f={open} me={me} onClose={() => setOpenId(null)} />}
    </div>
  );
}

// ------------------------------------------------------------------ Plans
type Status = "done" | "late" | "open" | "blocked";
interface Task { title: string; owner: PersonId | string; due: string; status: Status; note?: string }
interface Plan { name: string; owner: PersonId; end: string; tasks: Task[] }

const PLANS: Plan[] = [
  {
    name: "New model launch", owner: "prince", end: "Wed 15 Jan",
    tasks: [
      { title: "Price list", owner: "praga", due: "Mon 24 Nov", status: "late" },
      { title: "GPU supplier decision", owner: "prince", due: "Fri 28 Nov", status: "blocked", note: "Waiting for Supplier B's delivery date" },
      { title: "Supplier report", owner: "praga", due: "Mon 1 Dec", status: "open" },
      { title: "Northwind quote update", owner: "rachitaa", due: "Fri 28 Nov", status: "open" },
      { title: "Launch post", owner: "rachitaa", due: "Fri 12 Dec", status: "open" },
      { title: "Spec sheet v2", owner: "prince", due: "Tue 18 Nov", status: "done" },
      { title: "Stock plan", owner: "praga", due: "Mon 24 Nov", status: "done" },
      { title: "Memory price review", owner: "praga", due: "Thu 20 Nov", status: "done" },
      { title: "Supplier contract", owner: "prince", due: "Thu 20 Nov", status: "done" },
    ],
  },
  {
    name: "Q1 price change", owner: "prince", end: "Wed 31 Dec",
    tasks: [
      { title: "Tell big accounts", owner: "rachitaa", due: "Fri 5 Dec", status: "open" },
      { title: "Update web shop prices", owner: "prince", due: "Wed 31 Dec", status: "open" },
      { title: "Pricing decision", owner: "prince", due: "Thu 20 Nov", status: "done" },
    ],
  },
];

const STATUS: Record<Status, { label: string; color: "success" | "danger" | "informative" | "warning" }> = {
  done: { label: "Done", color: "success" },
  late: { label: "Late", color: "danger" },
  open: { label: "Open", color: "informative" },
  blocked: { label: "Blocked", color: "warning" },
};
const ORDER: Status[] = ["late", "blocked", "open", "done"];

function PlanCard({ plan, me, filter }: { plan: Plan; me: PersonId; filter: string }) {
  const s = useStyles();
  const [open, setOpen] = useState(true);
  const done = plan.tasks.filter((t) => t.status === "done").length;
  const late = plan.tasks.filter((t) => t.status === "late").length;
  const tasks = plan.tasks
    .filter((t) => filter === "all" || (filter === "late" ? t.status === "late" || t.status === "blocked" : t.owner === me))
    .sort((a, b) => ORDER.indexOf(a.status) - ORDER.indexOf(b.status));
  const owner = PEOPLE.find((p) => p.id === plan.owner);
  return (
    <div className={mergeClasses(s.card, s.plan)}>
      <div className={s.planHead} onClick={() => setOpen((o) => !o)}>
        {open ? <ChevronDown16Regular /> : <ChevronRight16Regular />}
        <div style={{ flex: 1 }}>
          <div className={s.planTitle}>{plan.name}</div>
          <Text size={200} className={s.muted}>Owner {personName(plan.owner)} · ends {plan.end}</Text>
        </div>
        <div className={s.progress}>
          <ProgressBar value={done / plan.tasks.length} thickness="large" color={late ? "warning" : "success"} />
          <Text size={200}>{done} of {plan.tasks.length} done{late ? <> · <span className={s.late}>{late} late</span></> : ""}</Text>
        </div>
        <Avatar name={personName(plan.owner)} color={owner?.color} size={28} />
      </div>
      {open && (
        <Table size="small" aria-label={`${plan.name} tasks`}>
          <TableHeader>
            <TableRow>
              <TableHeaderCell>Task</TableHeaderCell>
              <TableHeaderCell style={{ width: 160 }}>Owner</TableHeaderCell>
              <TableHeaderCell style={{ width: 130 }}>Due</TableHeaderCell>
              <TableHeaderCell style={{ width: 110 }}>Status</TableHeaderCell>
            </TableRow>
          </TableHeader>
          <TableBody>
            {tasks.map((t) => {
              const p = PEOPLE.find((x) => x.id === t.owner);
              return (
                <TableRow key={t.title}>
                  <TableCell>
                    <div style={t.status === "done" ? { color: tokens.colorNeutralForeground3 } : undefined}>{t.title}</div>
                    {t.note && <div className={s.blockedNote}>{t.note}</div>}
                  </TableCell>
                  <TableCell>
                    <TableCellLayout media={<Avatar size={20} name={personName(t.owner)} color={p?.color} />}>{personName(t.owner)}</TableCellLayout>
                  </TableCell>
                  <TableCell className={t.status === "late" ? s.late : undefined}>{t.due}</TableCell>
                  <TableCell><Badge appearance="tint" color={STATUS[t.status].color}>{STATUS[t.status].label}</Badge></TableCell>
                </TableRow>
              );
            })}
            {tasks.length === 0 && (
              <TableRow><TableCell colSpan={4} className={s.muted}>Nothing here.</TableCell></TableRow>
            )}
          </TableBody>
        </Table>
      )}
    </div>
  );
}

// ---- date helpers for the timeline (mock dates: Nov-Dec 2026, Jan 2027)
const MONTHS: Record<string, number> = { Nov: 10, Dec: 11, Jan: 0 };
function toDate(d: string): Date {
  const [, day, mon] = d.split(" ");
  return new Date(mon === "Jan" ? 2027 : 2026, MONTHS[mon], Number(day));
}
const TODAY = new Date(2026, 10, 26);
const START = new Date(2026, 10, 17);
const END = new Date(2027, 0, 18);
const pct = (d: Date) => ((d.getTime() - START.getTime()) / (END.getTime() - START.getTime())) * 100;
const DOT: Record<Status, string> = { done: "#107C10", late: "#D13438", open: "#5B5FC7", blocked: "#C19C00" };

const useViewStyles = makeStyles({
  board: { display: "grid", gridTemplateColumns: "repeat(4, minmax(220px, 1fr))", gap: "12px", alignItems: "start" },
  col: { backgroundColor: tokens.colorNeutralBackground2, borderRadius: tokens.borderRadiusLarge, padding: "10px", minHeight: "200px" },
  colHead: { display: "flex", alignItems: "center", gap: "8px", padding: "2px 4px 10px", fontWeight: tokens.fontWeightSemibold },
  taskCard: {
    backgroundColor: tokens.colorNeutralBackground1, borderRadius: tokens.borderRadiusMedium, boxShadow: tokens.shadow2,
    padding: "10px 12px", marginBottom: "8px", display: "flex", flexDirection: "column", gap: "6px",
  },
  taskFoot: { display: "flex", alignItems: "center", gap: "6px", fontSize: tokens.fontSizeBase200, color: tokens.colorNeutralForeground3 },
  tl: { padding: "8px 16px 16px" },
  tlAxis: { position: "relative", height: "24px", marginLeft: "220px", borderBottom: `1px solid ${tokens.colorNeutralStroke2}` },
  tlTick: { position: "absolute", top: "2px", fontSize: tokens.fontSizeBase100, color: tokens.colorNeutralForeground3, transform: "translateX(-50%)" },
  tlRow: { display: "flex", alignItems: "center", height: "30px" },
  tlName: { width: "220px", flexShrink: 0, fontSize: tokens.fontSizeBase200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", paddingRight: "8px" },
  tlTrack: { position: "relative", flex: 1, height: "100%", borderBottom: `1px dashed ${tokens.colorNeutralStroke3}` },
  tlDot: { position: "absolute", top: "50%", width: "12px", height: "12px", borderRadius: "50%", transform: "translate(-50%, -50%)", border: "2px solid white" },
  tlToday: { position: "absolute", top: 0, bottom: 0, width: "2px", backgroundColor: tokens.colorBrandStroke1, opacity: 0.7 },
  tlEnd: { position: "absolute", top: 0, bottom: 0, width: 0, borderLeft: `2px dashed ${tokens.colorPaletteRedBorder2}` },
  legend: { display: "flex", gap: "14px", padding: "0 16px 12px 236px", fontSize: tokens.fontSizeBase200, color: tokens.colorNeutralForeground3 },
});

function BoardView({ me, filter }: { me: PersonId; filter: string }) {
  const s = useStyles();
  const v = useViewStyles();
  const all = PLANS.flatMap((p) => p.tasks.map((t) => ({ ...t, plan: p.name })))
    .filter((t) => filter === "all" || (filter === "late" ? t.status === "late" || t.status === "blocked" : t.owner === me));
  return (
    <div className={v.board}>
      {ORDER.map((st) => {
        const items = all.filter((t) => t.status === st);
        return (
          <div key={st} className={v.col}>
            <div className={v.colHead}>
              <Badge appearance="tint" color={STATUS[st].color}>{STATUS[st].label}</Badge>
              <Text size={200} className={s.muted}>{items.length}</Text>
            </div>
            {items.map((t) => {
              const p = PEOPLE.find((x) => x.id === t.owner);
              return (
                <div key={t.plan + t.title} className={v.taskCard}>
                  <Text weight="semibold" style={st === "done" ? { color: tokens.colorNeutralForeground3 } : undefined}>{t.title}</Text>
                  {t.note && <Text size={200} className={s.muted}>{t.note}</Text>}
                  <div className={v.taskFoot}>
                    <Avatar size={20} name={personName(t.owner)} color={p?.color} />
                    <span style={{ flex: 1 }}>{personName(t.owner)}</span>
                    <span className={st === "late" ? s.late : undefined}>{t.due}</span>
                  </div>
                  <Text size={100} className={s.muted}>{t.plan}</Text>
                </div>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}

function TimelineView({ me, filter }: { me: PersonId; filter: string }) {
  const s = useStyles();
  const v = useViewStyles();
  const ticks = ["Mon 17 Nov", "Mon 1 Dec", "Mon 15 Dec", "Thu 1 Jan", "Thu 15 Jan"];
  return (
    <>
      {PLANS.map((plan) => {
        const tasks = plan.tasks
          .filter((t) => filter === "all" || (filter === "late" ? t.status === "late" || t.status === "blocked" : t.owner === me))
          .sort((a, b) => toDate(a.due).getTime() - toDate(b.due).getTime());
        return (
          <div key={plan.name} className={mergeClasses(s.card, s.plan)}>
            <div className={s.planHead} style={{ cursor: "default" }}>
              <div style={{ flex: 1 }}>
                <div className={s.planTitle}>{plan.name}</div>
                <Text size={200} className={s.muted}>Owner {personName(plan.owner)} · ends {plan.end}</Text>
              </div>
            </div>
            <div className={v.tl}>
              <div className={v.tlAxis}>
                {ticks.map((d) => <span key={d} className={v.tlTick} style={{ left: `${pct(toDate(d))}%` }}>{d.slice(4)}</span>)}
              </div>
              {tasks.map((t) => (
                <div key={t.title} className={v.tlRow}>
                  <div className={v.tlName}>{t.title} <span className={s.muted}>· {personName(t.owner)}</span></div>
                  <div className={v.tlTrack}>
                    <div className={v.tlToday} style={{ left: `${pct(TODAY)}%` }} />
                    <div className={v.tlEnd} style={{ left: `${pct(toDate(plan.end))}%` }} title={`Plan ends ${plan.end}`} />
                    <Tooltip content={`${t.title}: ${STATUS[t.status].label}, due ${t.due}`} relationship="label">
                      <div className={v.tlDot} style={{ left: `${pct(toDate(t.due))}%`, backgroundColor: DOT[t.status] }} />
                    </Tooltip>
                  </div>
                </div>
              ))}
            </div>
            <div className={v.legend}>
              {ORDER.map((st) => <span key={st}><span style={{ color: DOT[st] }}>●</span> {STATUS[st].label}</span>)}
              <span><span style={{ color: tokens.colorBrandForeground1 }}>│</span> Today</span>
              <span><span style={{ color: tokens.colorPaletteRedForeground1 }}>┆</span> Plan end ({plan.end})</span>
            </div>
          </div>
        );
      })}
    </>
  );
}

export function PlansTab({ me, initialView = "list" }: { me: PersonId; initialView?: string }) {
  const s = useStyles();
  const [filter, setFilter] = useState("all");
  const [view, setView] = useState(initialView);
  return (
    <div className={s.page}>
      <div className={s.main}>
        <div className={s.bar}>
          <MaxAvatar size={24} />
          <Text weight="semibold">Plans</Text>
          <Text size={200} className={s.muted}>kept up to date by Max</Text>
          <TabList size="small" selectedValue={view} onTabSelect={(_, d) => setView(String(d.value))} style={{ marginLeft: "16px" }}>
            <Tab value="list" icon={<TextBulletListLtr20Regular />}>List</Tab>
            <Tab value="board" icon={<Board20Regular />}>Board</Tab>
            <Tab value="timeline" icon={<GanttChart20Regular />}>Timeline</Tab>
          </TabList>
          <div style={{ flex: 1 }} />
          <TabList size="small" selectedValue={filter} onTabSelect={(_, d) => setFilter(String(d.value))}>
            <Tab value="all">All</Tab>
            <Tab value="late">Late or blocked</Tab>
            <Tab value="mine">Mine</Tab>
          </TabList>
        </div>
        {view === "list" && PLANS.map((p) => <PlanCard key={p.name} plan={p} me={me} filter={filter} />)}
        {view === "board" && <BoardView me={me} filter={filter} />}
        {view === "timeline" && <TimelineView me={me} filter={filter} />}
      </div>
    </div>
  );
}
