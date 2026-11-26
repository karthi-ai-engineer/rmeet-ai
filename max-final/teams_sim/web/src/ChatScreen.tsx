// UI design mock-up: the Chat screen (1:1 with Max, group chats, 1:1 chats). Static data, Max not connected.
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Avatar,
  AvatarGroup,
  AvatarGroupItem,
  Badge,
  Button,
  Input,
  Tab,
  TabList,
  Text,
  Textarea,
  Tooltip,
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  Checkbox,
  ToggleButton,
  Popover,
  PopoverSurface,
  PopoverTrigger,
  makeStyles,
  mergeClasses,
  tokens,
} from "@fluentui/react-components";
import {
  ArrowReply16Regular,
  Attach20Regular,
  Call20Regular,
  Compose20Regular,
  Dismiss12Regular,
  Emoji20Regular,
  Filter20Regular,
  Search16Regular,
  Send20Filled,
  TextEditStyle20Regular,
  ThumbDislike16Regular,
  ThumbLike16Regular,
  Video20Regular,
  Sparkle20Regular,
  ChevronDown12Regular,
  ChevronUp12Regular,
  ThumbLike16Filled,
  ThumbDislike16Filled,
} from "@fluentui/react-icons";
import { CHATS, maxChatFor, type Chat, type ChatMessage } from "./chatMock";
import { PEOPLE, type PersonId } from "./mock";
import { MAX_ORANGE, MaxAvatar, RichText, Sources, personName } from "./ui";
import { CardFrame } from "./CardsGallery";
import { CARDS } from "./cards";

const useStyles = makeStyles({
  wrap: { display: "flex", flex: 1, minWidth: 0, minHeight: 0 },
  // ---- left: chat list
  list: {
    width: "320px", flexShrink: 0, display: "flex", flexDirection: "column",
    backgroundColor: tokens.colorNeutralBackground2, borderRight: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  listTop: { display: "flex", alignItems: "center", padding: "14px 12px 8px 16px", gap: "4px" },
  listTitle: { flex: 1, fontSize: tokens.fontSizeBase500, fontWeight: tokens.fontWeightBold },
  listSearch: { margin: "0 12px 8px" },
  section: {
    padding: "10px 16px 4px", fontSize: tokens.fontSizeBase200, color: tokens.colorNeutralForeground3,
    fontWeight: tokens.fontWeightSemibold,
  },
  item: {
    display: "flex", alignItems: "center", gap: "10px", padding: "8px 12px", margin: "0 6px", cursor: "pointer",
    borderRadius: tokens.borderRadiusMedium, ":hover": { backgroundColor: tokens.colorNeutralBackground1Hover },
  },
  itemActive: { backgroundColor: tokens.colorNeutralBackground1Selected, ":hover": { backgroundColor: tokens.colorNeutralBackground1Selected } },
  itemBody: { flex: 1, minWidth: 0 },
  itemTop: { display: "flex", alignItems: "baseline", gap: "6px" },
  itemName: { flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  itemPreview: {
    display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
    color: tokens.colorNeutralForeground3, fontSize: tokens.fontSizeBase200,
  },
  unread: { fontWeight: tokens.fontWeightBold, color: tokens.colorNeutralForeground1 },
  // ---- right: conversation
  conv: { flex: 1, display: "flex", flexDirection: "column", minWidth: 0, backgroundColor: tokens.colorNeutralBackground3 },
  head: {
    display: "flex", alignItems: "center", gap: "12px", padding: "8px 16px 0 20px", flexShrink: 0,
    backgroundColor: tokens.colorNeutralBackground1, borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  headName: { fontSize: tokens.fontSizeBase400, fontWeight: tokens.fontWeightBold, whiteSpace: "nowrap" },
  headRight: { marginLeft: "auto", display: "flex", gap: "4px", paddingBottom: "8px" },
  scroll: { flex: 1, overflowY: "auto", padding: "8px 24px 16px" },
  inner: { maxWidth: "980px", margin: "0 auto", display: "flex", flexDirection: "column" },
  day: {
    display: "flex", alignItems: "center", gap: "12px", margin: "18px 0 8px",
    color: tokens.colorNeutralForeground3, fontSize: tokens.fontSizeBase200,
    "::before": { content: '""', flex: 1, height: "1px", backgroundColor: tokens.colorNeutralStroke2 },
    "::after": { content: '""', flex: 1, height: "1px", backgroundColor: tokens.colorNeutralStroke2 },
  },
  row: { display: "flex", gap: "10px", marginTop: "2px", position: "relative" },
  rowFirst: { marginTop: "14px" },
  rowMine: { justifyContent: "flex-end" },
  avatarSlot: { width: "32px", flexShrink: 0 },
  col: { display: "flex", flexDirection: "column", maxWidth: "min(680px, 75%)", minWidth: 0 },
  colMine: { alignItems: "flex-end" },
  meta: { display: "flex", alignItems: "baseline", gap: "8px", marginBottom: "2px", fontSize: tokens.fontSizeBase200 },
  maxName: { color: MAX_ORANGE, fontWeight: tokens.fontWeightSemibold },
  bubble: {
    position: "relative", padding: "8px 12px", borderRadius: tokens.borderRadiusLarge, boxShadow: tokens.shadow2,
    backgroundColor: tokens.colorNeutralBackground1, color: tokens.colorNeutralForeground1,
    ":hover > .msg-actions": { opacity: 1 },
  },
  bubbleMine: { backgroundColor: tokens.colorBrandBackground2, boxShadow: "none" },
  actions: {
    position: "absolute", top: "-16px", right: "8px", display: "flex", gap: "2px", padding: "2px",
    opacity: 0, transitionProperty: "opacity", transitionDuration: tokens.durationFaster,
    backgroundColor: tokens.colorNeutralBackground1, borderRadius: tokens.borderRadiusMedium, boxShadow: tokens.shadow8,
  },
  react: {
    minWidth: "28px", height: "28px", border: "none", background: "transparent", cursor: "pointer",
    borderRadius: tokens.borderRadiusMedium, fontSize: "15px", ":hover": { backgroundColor: tokens.colorNeutralBackground1Hover },
  },
  quote: {
    borderLeft: `3px solid ${tokens.colorBrandStroke1}`, padding: "4px 8px", marginBottom: "6px",
    backgroundColor: tokens.colorNeutralBackground3, borderRadius: tokens.borderRadiusSmall, fontSize: tokens.fontSizeBase200,
  },
  reactions: { display: "flex", gap: "4px", marginTop: "4px" },
  reactionChip: {
    display: "inline-flex", alignItems: "center", gap: "4px", padding: "1px 8px", fontSize: tokens.fontSizeBase200,
    borderRadius: tokens.borderRadiusCircular, backgroundColor: tokens.colorNeutralBackground1,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  feedback: { display: "flex", gap: "2px", marginTop: "4px" },
  time: { color: tokens.colorNeutralForeground3, fontSize: tokens.fontSizeBase100 },
  typing: { display: "inline-flex", gap: "4px", padding: "12px 14px" },
  dot: {
    width: "6px", height: "6px", borderRadius: "50%", backgroundColor: tokens.colorNeutralForeground3,
    animationName: { "0%, 60%, 100%": { opacity: 0.3, transform: "translateY(0)" }, "30%": { opacity: 1, transform: "translateY(-3px)" } },
    animationDuration: "1.2s", animationIterationCount: "infinite",
  },
  // ---- compose
  compose: { padding: "8px 24px 18px", flexShrink: 0 },
  composeBox: {
    maxWidth: "980px", margin: "0 auto", borderRadius: tokens.borderRadiusLarge, overflow: "hidden",
    backgroundColor: tokens.colorNeutralBackground1, border: `1px solid ${tokens.colorNeutralStroke1}`,
    borderBottom: `2px solid ${tokens.colorBrandStroke1}`,
  },
  replyingTo: {
    display: "flex", alignItems: "center", gap: "8px", margin: "8px 8px 0", padding: "4px 8px",
    borderLeft: `3px solid ${tokens.colorBrandStroke1}`, backgroundColor: tokens.colorNeutralBackground3,
    borderRadius: tokens.borderRadiusSmall, fontSize: tokens.fontSizeBase200,
  },
  composeText: { width: "100%", "& textarea": { maxHeight: "160px" } },
  composeBar: { display: "flex", alignItems: "center", gap: "2px", padding: "0 6px 6px" },
  hint: { color: tokens.colorNeutralForeground3, fontSize: tokens.fontSizeBase100, marginLeft: "6px" },
});

interface Canned { statuses: string[]; text: string; sources?: { n: number; title: string; where: string }[]; followUps?: string[]; card?: { before: object; after?: object; done?: boolean; afterText?: string } }
const EMAIL_CARD = CARDS.find((c) => c.id === "email")!;
function cannedAnswer(q: string): Canned {
  const s = q.toLowerCase();
  if (s.includes("email")) return {
    statuses: ["Searching team chats and files…", "Writing the email…", "Checking the facts…"],
    text: "Here's the email to Prince. **It's only sent after you approve it.**",
    card: { before: EMAIL_CARD.before, after: EMAIL_CARD.after, afterText: "✅ Done. The email went to Prince from Max's mailbox." },
  };
  if (s.includes("plate") || s.includes("tasks")) return {
    statuses: ["Checking your plans…", "Reading your calendar…"],
    text: "**3 open items this week:**\n⚠️ Price list (new model launch) was due **Mon 24 Nov** [1]\n⏰ Supplier report due **Mon 1 Dec** [1]\n📅 New model check-in **Fri 28 Nov, 10:00 JST** [2]",
    sources: [{ n: 1, title: "Launch plan", where: "Product Planning › Plans" }, { n: 2, title: "Calendar", where: "New model check-in" }],
    followUps: ["Remind me about the price list tomorrow", "What's late in the launch plan?"],
  };
  if (s.includes("decide") || s.includes("decision")) return {
    statuses: ["Searching team chats and files…", "Reading 3 threads…", "Checking the answer…"],
    text: "📌 **Decided on 20 Nov:** all desktop models go up **5% from 1 Jan**, because of the memory price rise [1].\nQuotes sent **before 1 Dec** keep the old price [1].",
    sources: [{ n: 1, title: "Pricing thread, 20 Nov", where: "Prince, 14:32 and 14:52" }],
    followUps: ["Who tells the big accounts?", "Show the memory price change"],
  };
  if (s.includes("cost") || s.includes("price") || s.includes("total")) return {
    statuses: ["Searching team chats and files…", "Reading Parts prices.xlsx › Memory…", "Calculating…", "Checking the numbers…"],
    text: "**Total memory cost in November: ¥57,600** per set of one of each module (16 GB ¥9,100 + 32 GB ¥16,900 + 64 GB ¥31,600) [1].\nThat's **+16%** on October (¥49,600).",
    sources: [{ n: 1, title: "Parts prices.xlsx › Memory", where: "rows 2-4, Oct and Nov (sum by code)" }],
    followUps: ["Compare with September", "Show the GPU prices too", "Who decided the 5% price rise?"],
  };
  return {
    statuses: ["Searching team chats and files…", "Reading 2 threads…"],
    text: "This is a design mock-up, so I'm not connected yet. In the real simulator I'd answer here, with sources.",
  };
}

export const PROMPT_STARTERS = [
  { title: "What did I miss?", prompt: "Catch me up on my departments since yesterday" },
  { title: "What's on my plate?", prompt: "What are my open tasks and meetings this week?" },
  { title: "Find a decision", prompt: "What did we decide about desktop prices?" },
  { title: "Numbers from a file", prompt: "What's the total memory cost in November in Parts prices?" },
  { title: "Make a plan", prompt: "Make a plan for the new model launch by 15 Jan" },
  { title: "Remind me", prompt: "Remind me tomorrow at 10:00 to check the supplier report" },
];

const useWelcome = makeStyles({
  wrap: { display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", padding: "48px 16px 24px", gap: "6px" },
  name: { fontSize: tokens.fontSizeBase600, fontWeight: tokens.fontWeightSemibold, marginTop: "10px" },
  desc: { maxWidth: "520px", color: tokens.colorNeutralForeground2, marginTop: "6px" },
  grid: { display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: "10px", marginTop: "26px", width: "100%", maxWidth: "820px", textAlign: "left" },
  tile: {
    padding: "12px 14px", borderRadius: tokens.borderRadiusLarge, cursor: "pointer", backgroundColor: tokens.colorNeutralBackground1,
    border: `1px solid ${tokens.colorNeutralStroke2}`, display: "flex", flexDirection: "column", gap: "4px",
    transitionProperty: "box-shadow, border-color", transitionDuration: tokens.durationFaster,
    ":hover": { boxShadow: tokens.shadow8, border: `1px solid ${tokens.colorBrandStroke1}` },
  },
  label: { color: tokens.colorNeutralForeground3, fontSize: tokens.fontSizeBase200, marginTop: "26px" },
  list: { display: "flex", flexDirection: "column", gap: "2px", width: "320px" },
  listItem: { padding: "8px 10px", borderRadius: tokens.borderRadiusMedium, cursor: "pointer", ":hover": { backgroundColor: tokens.colorNeutralBackground1Hover } },
});

/** What Teams shows in a new, empty chat with Max: app icon, name, description (from the manifest) + prompt starters. */
function MaxWelcome({ onPick }: { onPick: (text: string) => void }) {
  const w = useWelcome();
  return (
    <div className={w.wrap}>
      <MaxAvatar size={72} />
      <div className={w.name}>Max</div>
      <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>AI teammate · Thirdwave</Text>
      <Text className={w.desc}>
        Ask me about your team's chats, files and plans. I answer with sources, and I always ask before I send or change anything.
      </Text>
      <span className={w.label}>Try one of these</span>
      <div className={w.grid} style={{ marginTop: 10 }}>
        {PROMPT_STARTERS.map((p) => (
          <div key={p.title} className={w.tile} onClick={() => onPick(p.prompt)} role="button" tabIndex={0}>
            <Text weight="semibold">{p.title}</Text>
            <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>{p.prompt}</Text>
          </div>
        ))}
      </div>
    </div>
  );
}

function PromptList({ onPick }: { onPick: (text: string) => void }) {
  const w = useWelcome();
  return (
    <div className={w.list}>
      <Text weight="semibold" style={{ padding: "4px 10px 6px" }}>Prompts</Text>
      {PROMPT_STARTERS.map((p) => (
        <div key={p.title} className={w.listItem} onClick={() => onPick(p.prompt)}>
          <Text weight="semibold" block size={300}>{p.title}</Text>
          <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>{p.prompt}</Text>
        </div>
      ))}
    </div>
  );
}

const plain = (t: string) => t.replace(/\*\*/g, "").replace(/\s*\[\d+\]/g, "").split("\n")[0];

function chatTitle(c: Chat, me: PersonId) {
  if (c.kind === "max") return "Max";
  if (c.kind === "group") return c.title ?? "Group chat";
  return personName(c.members.find((m) => m !== me) ?? me);
}

function ChatAvatar({ c, me, size = 36 }: { c: Chat; me: PersonId; size?: 28 | 32 | 36 }) {
  if (c.kind === "max") return <MaxAvatar size={size} />;
  if (c.kind === "group") {
    return (
      <AvatarGroup layout="pie" size={size}>
        {c.members.filter((m) => m !== me).map((m) => <AvatarGroupItem key={m} name={personName(m)} />)}
      </AvatarGroup>
    );
  }
  const other = c.members.find((m) => m !== me)!;
  const p = PEOPLE.find((x) => x.id === other);
  return <Avatar name={personName(other)} color={p?.color} size={size} badge={{ status: "available" }} />;
}

function TypingBubble() {
  const s = useStyles();
  return (
    <div className={mergeClasses(s.row, s.rowFirst)}>
      <MaxAvatar size={32} />
      <div className={s.col}>
        <div className={s.meta}><span className={s.maxName}>Max</span><span className={s.time}>is typing…</span></div>
        <div className={mergeClasses(s.bubble, s.typing)}>
          {[0, 1, 2].map((i) => <span key={i} className={s.dot} style={{ animationDelay: `${i * 0.15}s` }} />)}
        </div>
      </div>
    </div>
  );
}

function MessageRow({ m, me, first, onReply, latest, onPick, fb, onThumb, onCard, dark }: { m: ChatMessage; me: PersonId; first: boolean; onReply: (m: ChatMessage) => void; latest?: boolean; onPick?: (t: string) => void; fb?: string; onThumb?: (m: ChatMessage, k: "up" | "down") => void; onCard?: (m: ChatMessage, verb: string) => void; dark?: boolean }) {
  const [refsOpen, setRefsOpen] = useState(false);
  const s = useStyles();
  const mine = m.author === me;
  const isMax = m.author === "max";
  const p = PEOPLE.find((x) => x.id === m.author);
  return (
    <div className={mergeClasses(s.row, first && s.rowFirst, mine && s.rowMine)}>
      {!mine && (
        <div className={s.avatarSlot}>
          {first && (isMax ? <MaxAvatar size={32} /> : <Avatar name={personName(m.author)} color={p?.color} size={32} />)}
        </div>
      )}
      <div className={mergeClasses(s.col, mine && s.colMine)}>
        {first && (
          <div className={s.meta}>
            {!mine && <span className={isMax ? s.maxName : undefined} style={isMax ? undefined : { fontWeight: 600 }}>{personName(m.author)}</span>}
            <span className={s.time}>{m.time}</span>
            {isMax && <Badge appearance="tint" color="informative" size="small">AI generated</Badge>}
          </div>
        )}
        <div className={mergeClasses(s.bubble, mine && s.bubbleMine)}>
          <div className={mergeClasses(s.actions, "msg-actions")}>
            {["👍", "❤️", "😆", "😮"].map((e) => <button key={e} className={s.react} aria-label={`React ${e}`}>{e}</button>)}
            <Tooltip content="Reply" relationship="label">
              <Button size="small" appearance="subtle" icon={<ArrowReply16Regular />} onClick={() => onReply(m)} />
            </Tooltip>
          </div>
          {m.quote && (
            <div className={s.quote}>
              <Text weight="semibold" size={200}>{m.quote.author}</Text>
              <div style={{ color: tokens.colorNeutralForeground2 }}>{m.quote.text}</div>
            </div>
          )}
          <RichText text={m.card?.done && m.card.afterText ? m.card.afterText : m.text} sources={m.sources} />
          {m.card && (
            <div style={{ marginTop: 10 }}>
              <CardFrame json={m.card.done && m.card.after ? m.card.after : m.card.before} dark={!!dark} onAction={(v) => onCard?.(m, v)} />
            </div>
          )}
          {m.sources && (
            <div style={{ marginTop: 8 }}>
              <Button size="small" appearance="transparent" style={{ padding: 0, minWidth: 0 }}
                icon={refsOpen ? <ChevronUp12Regular /> : <ChevronDown12Regular />} iconPosition="after"
                onClick={() => setRefsOpen((o) => !o)}>
                {m.sources.length} {m.sources.length === 1 ? "reference" : "references"}
              </Button>
              {refsOpen && <Sources sources={m.sources} />}
            </div>
          )}
          {isMax && (
            <div className={s.feedback}>
              <Button size="small" appearance="subtle" aria-label="Helpful" onClick={() => onThumb?.(m, "up")}
                icon={fb === "up" ? <ThumbLike16Filled primaryFill={tokens.colorBrandForeground1} /> : <ThumbLike16Regular />} />
              <Button size="small" appearance="subtle" aria-label="Not helpful" onClick={() => onThumb?.(m, "down")}
                icon={fb?.startsWith("down") ? <ThumbDislike16Filled primaryFill={tokens.colorBrandForeground1} /> : <ThumbDislike16Regular />} />
              {fb?.startsWith("down:") && <Text size={200} style={{ color: tokens.colorNeutralForeground3, alignSelf: "center", marginLeft: 4 }}>{fb.slice(5)}</Text>}
              {fb === "up" && <Text size={200} style={{ color: tokens.colorNeutralForeground3, alignSelf: "center", marginLeft: 4 }}>Thanks!</Text>}
            </div>
          )}
        </div>
        {latest && m.followUps && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 }}>
            {m.followUps.map((f) => (
              <Button key={f} size="small" shape="circular" appearance="outline" onClick={() => onPick?.(f)}
                style={{ fontWeight: 400, borderColor: tokens.colorBrandStroke2, color: tokens.colorBrandForeground1 }}>{f}</Button>
            ))}
          </div>
        )}
        {m.reactions && (
          <div className={s.reactions}>
            {m.reactions.map((r) => <span key={r.emoji} className={s.reactionChip}>{r.emoji} {r.count}</span>)}
          </div>
        )}
      </div>
    </div>
  );
}

const useStream = makeStyles({
  status: { display: "flex", alignItems: "center", gap: "8px", color: tokens.colorNeutralForeground2, fontSize: tokens.fontSizeBase200 },
  bar: {
    height: "2px", width: "100%", borderRadius: "1px", marginTop: "8px", overflow: "hidden", backgroundColor: tokens.colorNeutralBackground4, position: "relative",
    "::after": {
      content: '""', position: "absolute", top: 0, bottom: 0, width: "40%", backgroundColor: tokens.colorBrandBackground,
      animationName: { from: { left: "-40%" }, to: { left: "100%" } }, animationDuration: "1.1s", animationIterationCount: "infinite",
    },
  },
  cursor: {
    display: "inline-block", width: "7px", height: "15px", marginLeft: "2px", verticalAlign: "-2px", backgroundColor: tokens.colorNeutralForeground2,
    animationName: { "0%, 100%": { opacity: 1 }, "50%": { opacity: 0 } }, animationDuration: "0.9s", animationIterationCount: "infinite",
  },
  stopBtn: {
    width: "24px", height: "24px", borderRadius: "50%", border: "none", cursor: "pointer", padding: 0,
    display: "flex", alignItems: "center", justifyContent: "center", backgroundColor: tokens.colorBrandBackground,
    boxShadow: tokens.shadow4, transitionProperty: "transform, background-color", transitionDuration: tokens.durationFaster,
    ":hover": { backgroundColor: tokens.colorBrandBackgroundHover, transform: "scale(1.06)" },
    ":active": { transform: "scale(0.94)" },
  },
  stopSquare: { width: "8px", height: "8px", borderRadius: "2px", backgroundColor: tokens.colorNeutralForegroundOnBrand },
});

/** Teams streaming: short status updates ("informative updates") first, then the text appears as it is written. */
function StreamingBubble({ status, text, onStop }: { status: string | null; text: string; onStop: () => void }) {
  const s = useStyles();
  const st = useStream();
  return (
    <div className={mergeClasses(s.row, s.rowFirst)}>
      <MaxAvatar size={32} />
      <div className={s.col} style={{ minWidth: 320 }}>
        <div className={s.meta}><span className={s.maxName}>Max</span><span className={s.time}>now</span></div>
        <div className={s.bubble} style={{ paddingRight: 44 }}>
          <Tooltip content="Stop" relationship="label">
            <button className={st.stopBtn} style={{ position: "absolute", right: 8, bottom: 8 }} onClick={onStop} aria-label="Stop"><span className={st.stopSquare} /></button>
          </Tooltip>
          {status && !text && (
            <>
              <div className={st.status}>{status}</div>
              <div className={st.bar} />
            </>
          )}
          {text && <RichText text={text} after={<span className={st.cursor} />} />}
        </div>
      </div>
    </div>
  );
}

const REASONS = ["Wrong facts", "Wrong numbers", "Missed something", "Old information", "Wrong source", "Not what I asked", "Too long"];

/** Max's own feedback form, opened by Teams when someone presses 👎 (Teams feedback loop, custom form). */
function FeedbackDialog({ open, me, onClose, onSend }: { open: boolean; me: PersonId; onClose: () => void; onSend: (r: string[], text: string, lesson: boolean) => void }) {
  const [reasons, setReasons] = useState<string[]>(["Old information"]);
  const [text, setText] = useState("");
  const [lesson, setLesson] = useState(true);
  const lead = me === "prince";
  return (
    <Dialog open={open} onOpenChange={(_, d) => { if (!d.open) onClose(); }}>
      <DialogSurface style={{ maxWidth: 520 }}>
        <DialogBody>
          <DialogTitle>What went wrong?</DialogTitle>
          <DialogContent style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>Pick what fits. It helps Max learn the right way for your team.</Text>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {REASONS.map((r) => (
                <ToggleButton key={r} size="small" shape="circular" checked={reasons.includes(r)}
                  onClick={() => setReasons((rs) => (rs.includes(r) ? rs.filter((x) => x !== r) : [...rs, r]))}>{r}</ToggleButton>
              ))}
            </div>
            <div>
              <Text weight="semibold" size={300} block style={{ marginBottom: 4 }}>What's right? (optional)</Text>
              <Textarea style={{ width: "100%" }} resize="vertical" value={text} onChange={(_, d) => setText(d.value)}
                placeholder="e.g. Use the Parts prices sheet, not the slides. The slides are from October." />
            </div>
            <Checkbox checked={lesson} onChange={(_, d) => setLesson(!!d.checked)}
              label={lead ? "Save as a lesson for the team (you're the team lead, so it's active at once)" : "Suggest this as a lesson for the team (Prince, the team lead, accepts it first)"} />
          </DialogContent>
          <DialogActions>
            <Button appearance="secondary" onClick={onClose}>Cancel</Button>
            <Button appearance="primary" disabled={reasons.length === 0 && !text.trim()} onClick={() => onSend(reasons, text, lesson)}>Send feedback</Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </Dialog>
  );
}

export function ChatScreen({ me, initialChat, fresh, demo, dark }: { me: PersonId; initialChat: string; fresh?: boolean; demo?: string; dark?: boolean }) {
  const s = useStyles();
  const [chats, setChats] = useState<Chat[]>(() => [
    demo === "card" || demo === "carddone" ? { ...maxChatFor(me), messages: [
      { id: "cq", author: me, day: "Today", time: "10:40", text: "Email Prince the Q1 pricing summary" },
      { id: "ca", author: "max", day: "Today", time: "10:41", text: cannedAnswer("email").text,
        card: { ...cannedAnswer("email").card!, done: demo === "carddone" } },
    ] }
    : ["done", "cite", "feedback", "fbdone"].includes(demo ?? "") ? { ...maxChatFor(me), messages: [
      { id: "dq", author: me, day: "Today", time: "11:20", text: "What's the total memory cost in November in Parts prices?" },
      { id: "da", author: "max", day: "Today", time: "11:20", ...(({ statuses: _s, ...rest }) => rest)(cannedAnswer("total memory cost")) },
    ] }
    : demo ? { ...maxChatFor(me), messages: [{ id: "dq", author: me, day: "Today", time: "11:20", text: "What's the total memory cost in November in Parts prices?" }] }
      : fresh ? { ...maxChatFor(me), messages: [] } : maxChatFor(me),
    ...CHATS.filter((c) => c.members.includes(me))]);
  const [promptsOpen, setPromptsOpen] = useState(false);
  const [feedback, setFeedback] = useState<Record<string, string>>(() => (demo === "fbdone" ? { da: `down:${me === "prince" ? "Thanks. Saved as a lesson for the team." : "Thanks. Sent to Prince (team lead) as a lesson to accept."}` } : {}));
  const [fbFor, setFbFor] = useState<string | null>(demo === "feedback" ? "da" : null);
  const [activeId, setActiveId] = useState(chats.some((c) => c.id === initialChat) ? initialChat : "max");
  const [draft, setDraft] = useState("");
  const [replyTo, setReplyTo] = useState<ChatMessage | null>(null);
  const [typing, setTyping] = useState(false);
  // streaming state (1:1 chat with Max). `demo` freezes a moment for design pictures.
  const demoQ = "What's the total memory cost in November in Parts prices?";
  const [stream, setStream] = useState<{ status: string | null; text: string } | null>(() =>
    ["done", "cite", "feedback", "fbdone", "card", "carddone"].includes(demo ?? "") ? null
      : demo === "status" ? { status: "Reading Parts prices.xlsx › Memory…", text: "" }
      : demo === "text" ? { status: null, text: cannedAnswer(demoQ).text.slice(0, 120) } : null);
  const timers = useRef<number[]>([]);
  const current = useRef<{ chatId: string; canned: Canned; shown: string } | null>(null);
  const [filter, setFilter] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const active = chats.find((c) => c.id === activeId)!;
  const busy = !!stream && active.kind === "max";

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [activeId, active.messages.length, typing, stream?.text, stream?.status]);

  const visible = useMemo(
    () => chats.filter((c) => chatTitle(c, me).toLowerCase().includes(filter.toLowerCase())),
    [chats, filter, me],
  );

  const pushMax = (chatId: string, m: { text: string; sources?: Canned["sources"]; followUps?: string[]; card?: Canned["card"] }) =>
    setChats((cs) => cs.map((c) => (c.id === chatId ? {
      ...c, messages: [...c.messages, { id: crypto.randomUUID(), author: "max" as const, day: "Today", time: new Date().toTimeString().slice(0, 5), ...m }],
    } : c)));

  const startStream = (chatId: string, canned: Canned) => {
    current.current = { chatId, canned, shown: "" };
    const at = (ms: number, fn: () => void) => timers.current.push(window.setTimeout(fn, ms));
    canned.statuses.forEach((st, i) => at(i * 800, () => setStream({ status: st, text: "" })));
    const words = canned.text.split(/(\s+)/);
    const start = canned.statuses.length * 800;
    words.forEach((_, i) => at(start + i * 30, () => {
      const shown = words.slice(0, i + 1).join("");
      if (current.current) current.current.shown = shown;
      setStream({ status: null, text: shown });
    }));
    at(start + words.length * 30 + 150, () => {
      setStream(null);
      current.current = null;
      pushMax(chatId, { text: canned.text, sources: canned.sources, followUps: canned.followUps, card: canned.card });
    });
  };

  const stopStream = () => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
    const cur = current.current;
    setStream(null);
    current.current = null;
    if (cur) pushMax(cur.chatId, { text: (cur.shown ? cur.shown + "\n\n" : "") + "(Stopped. Nothing was sent or changed.)" });
  };

  const send = () => sendText(draft);
  const sendText = (raw: string) => {
    setPromptsOpen(false);
    const text = raw.trim();
    if (!text) return;
    const time = new Date().toTimeString().slice(0, 5);
    const msg: ChatMessage = {
      id: crypto.randomUUID(), author: me, day: "Today", time, text,
      quote: replyTo ? { author: personName(replyTo.author), text: plain(replyTo.text) } : undefined,
    };
    const last = active.messages[active.messages.length - 1];
    // Max answers: always in its 1:1 chat; in other chats on @Max or a follow-up right after Max answered this person
    const askedMax = active.kind === "max" || /@max\b/i.test(text) || replyTo?.author === "max" ||
      (last?.author === "max" && active.messages[active.messages.length - 2]?.author === me);
    setChats((cs) => cs.map((c) => (c.id === active.id ? { ...c, messages: [...c.messages, msg] } : c)));
    setDraft("");
    setReplyTo(null);
    if (askedMax && active.kind === "max") {
      startStream(active.id, cannedAnswer(text));
    } else if (askedMax) {
      setTyping(true);
      setTimeout(() => {
        setTyping(false);
        pushMax(active.id, { text: "This is a design mock-up, so I'm not connected yet. In the real simulator I'd answer here, with sources." });
      }, 1400);
    }
  };

  const pinned = visible.filter((c) => c.kind === "max");
  const recent = visible.filter((c) => c.kind !== "max");

  const listItem = (c: Chat) => {
    const last = c.messages[c.messages.length - 1] ?? { author: "max", day: "Today", time: "", text: "New chat", id: "none" };
    const unread = c.id !== activeId && last.author !== me && c.kind !== "oneToOne";
    return (
      <div key={c.id} className={mergeClasses(s.item, c.id === activeId && s.itemActive)} onClick={() => setActiveId(c.id)}>
        <ChatAvatar c={c} me={me} />
        <div className={s.itemBody}>
          <div className={s.itemTop}>
            <Text className={mergeClasses(s.itemName, unread && s.unread)}>{chatTitle(c, me)}</Text>
            <Text size={100} style={{ color: tokens.colorNeutralForeground3 }}>{last.day === "Today" ? last.time : last.day}</Text>
          </div>
          <span className={mergeClasses(s.itemPreview, unread && s.unread)}>
            {last.author === me ? "You: " : c.kind === "group" ? `${personName(last.author)}: ` : ""}{plain(last.text)}
          </span>
        </div>
      </div>
    );
  };

  let prevDay = "";
  let prevAuthor = "";

  return (
    <div className={s.wrap}>
      <aside className={s.list}>
        <div className={s.listTop}>
          <span className={s.listTitle}>Chat</span>
          <Tooltip content="Filter" relationship="label"><Button appearance="subtle" icon={<Filter20Regular />} /></Tooltip>
          <Tooltip content="New chat" relationship="label"><Button appearance="subtle" icon={<Compose20Regular />} /></Tooltip>
        </div>
        <Input className={s.listSearch} size="small" contentBefore={<Search16Regular />} placeholder="Search chats"
          value={filter} onChange={(_, d) => setFilter(d.value)} />
        {pinned.length > 0 && <div className={s.section}>Pinned</div>}
        {pinned.map(listItem)}
        <div className={s.section}>Recent</div>
        {recent.map(listItem)}
      </aside>

      <section className={s.conv}>
        <div className={s.head}>
          <div style={{ paddingBottom: "8px" }}><ChatAvatar c={active} me={me} size={32} /></div>
          <div style={{ paddingBottom: "8px" }}>
            <div className={s.headName} style={active.kind === "max" ? { color: MAX_ORANGE } : undefined}>{chatTitle(active, me)}</div>
            {active.kind === "max" && <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>Your AI teammate · only you can see this chat</Text>}
            {active.kind === "group" && <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>{active.members.map(personName).join(", ")} · Max</Text>}
          </div>
          <TabList defaultSelectedValue="chat" size="small" style={{ marginLeft: "8px", alignSelf: "flex-end" }}>
            <Tab value="chat">Chat</Tab>
            <Tab value="files">Files</Tab>
          </TabList>
          {active.kind !== "max" && (
            <div className={s.headRight}>
              <Tooltip content="Video call" relationship="label"><Button appearance="subtle" icon={<Video20Regular />} /></Tooltip>
              <Tooltip content="Audio call" relationship="label"><Button appearance="subtle" icon={<Call20Regular />} /></Tooltip>
            </div>
          )}
        </div>

        <div className={s.scroll} ref={scrollRef}>
          <div className={s.inner}>
            {active.kind === "max" && active.messages.length === 0 && !typing && <MaxWelcome onPick={sendText} />}
            {active.messages.map((m) => {
              const newDay = m.day !== prevDay;
              const first = newDay || m.author !== prevAuthor || !!m.quote;
              prevDay = m.day;
              prevAuthor = m.author;
              return (
                <div key={m.id}>
                  {newDay && <div className={s.day}>{m.day}</div>}
                  <MessageRow m={m} me={me} first={first} onReply={setReplyTo} onPick={busy ? undefined : sendText}
                    dark={dark}
                    onCard={(mm, verb) => {
                      if (verb === "approve" || verb === "approveEdited" || verb === "book" || verb === "accept") {
                        setChats((cs) => cs.map((c) => ({ ...c, messages: c.messages.map((x) => (x.id === mm.id && x.card ? { ...x, card: { ...x.card, done: true } } : x)) })));
                      }
                    }}
                    fb={feedback[m.id]} onThumb={(mm, k) => (k === "up" ? setFeedback((f) => ({ ...f, [mm.id]: "up" })) : setFbFor(mm.id))}
                    latest={m.id === active.messages[active.messages.length - 1]?.id && !stream} />
                </div>
              );
            })}
            {typing && <TypingBubble />}
            <FeedbackDialog open={!!fbFor} me={me} onClose={() => setFbFor(null)}
              onSend={(_r, _t, lesson) => {
                const msg = lesson ? (me === "prince" ? "Thanks. Saved as a lesson for the team." : "Thanks. Sent to Prince (team lead) as a lesson to accept.") : "Thanks for the feedback.";
                setFeedback((f) => ({ ...f, [fbFor!]: `down:${msg}` }));
                setFbFor(null);
              }} />
            {stream && active.kind === "max" && <StreamingBubble status={stream.status} text={stream.text} onStop={stopStream} />}
          </div>
        </div>

        <div className={s.compose}>
          <div className={s.composeBox}>
            {replyTo && (
              <div className={s.replyingTo}>
                <ArrowReply16Regular />
                <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  <b>{personName(replyTo.author)}</b>: {plain(replyTo.text)}
                </span>
                <Button size="small" appearance="subtle" icon={<Dismiss12Regular />} onClick={() => setReplyTo(null)} />
              </div>
            )}
            <Textarea className={s.composeText} appearance="filled-lighter" resize="none" value={draft}
              disabled={busy}
              placeholder={busy ? "Max is answering… (stop it to ask something else)" : active.kind === "max" ? "Message Max (no @ needed here)" : "Type a message (use @Max to ask Max)"}
              onChange={(_, d) => setDraft(d.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); if (!busy) send(); } }} />
            <div className={s.composeBar}>
              {active.kind === "max" && (
                <Popover open={promptsOpen} onOpenChange={(_, d) => setPromptsOpen(d.open)} positioning="above-start">
                  <PopoverTrigger disableButtonEnhancement>
                    <Button size="small" appearance="subtle" icon={<Sparkle20Regular />}>View prompts</Button>
                  </PopoverTrigger>
                  <PopoverSurface><PromptList onPick={sendText} /></PopoverSurface>
                </Popover>
              )}
              <Tooltip content="Format" relationship="label"><Button size="small" appearance="subtle" icon={<TextEditStyle20Regular />} /></Tooltip>
              <Tooltip content="Emoji" relationship="label"><Button size="small" appearance="subtle" icon={<Emoji20Regular />} /></Tooltip>
              <Tooltip content="Attach file" relationship="label"><Button size="small" appearance="subtle" icon={<Attach20Regular />} /></Tooltip>
              <span className={s.hint}>Enter to send · Shift+Enter for a new line</span>
              <div style={{ flex: 1 }} />
              <Tooltip content="Send" relationship="label">
                <Button appearance="transparent" icon={<Send20Filled primaryFill={busy ? tokens.colorNeutralForegroundDisabled : tokens.colorBrandForeground1} />} onClick={send} disabled={!draft.trim() || busy} />
              </Tooltip>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
