// UI design mock-ups: simple Mail (to check emails Max sent after approval) and Activity. Static data.
import { useState } from "react";
import {
  Avatar,
  Badge,
  Button,
  Divider,
  Tab,
  TabList,
  Text,
  makeStyles,
  mergeClasses,
  tokens,
} from "@fluentui/react-components";
import {
  ArrowReply20Regular,
  Mention12Regular,
  Mail20Regular,
  Send20Regular,
  ChatMultiple20Regular,
} from "@fluentui/react-icons";
import { PEOPLE, type PersonId } from "./mock";
import { MAX_ORANGE, MaxAvatar, RichText, personName } from "./ui";

const useStyles = makeStyles({
  wrap: { flex: 1, display: "flex", minWidth: 0, minHeight: 0, backgroundColor: tokens.colorNeutralBackground1 },
  folders: { width: "200px", flexShrink: 0, padding: "12px 8px", backgroundColor: tokens.colorNeutralBackground2, borderRight: `1px solid ${tokens.colorNeutralStroke2}` },
  folder: {
    display: "flex", alignItems: "center", gap: "8px", padding: "8px 10px", borderRadius: tokens.borderRadiusMedium, cursor: "pointer",
    ":hover": { backgroundColor: tokens.colorNeutralBackground1Hover },
  },
  folderActive: { backgroundColor: tokens.colorNeutralBackground1Selected, fontWeight: tokens.fontWeightSemibold },
  title: { fontSize: tokens.fontSizeBase500, fontWeight: tokens.fontWeightBold, padding: "4px 10px 12px" },
  list: { width: "360px", flexShrink: 0, overflowY: "auto", borderRight: `1px solid ${tokens.colorNeutralStroke2}` },
  item: {
    display: "flex", gap: "10px", padding: "12px 14px", cursor: "pointer", borderBottom: `1px solid ${tokens.colorNeutralStroke3}`,
    borderLeft: "3px solid transparent", ":hover": { backgroundColor: tokens.colorNeutralBackground1Hover },
  },
  itemActive: { backgroundColor: tokens.colorNeutralBackground1Selected, borderLeftColor: tokens.colorBrandStroke1 },
  itemUnread: { borderLeftColor: tokens.colorBrandStroke1 },
  one: { display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  muted: { color: tokens.colorNeutralForeground3 },
  read: { flex: 1, overflowY: "auto", padding: "20px 28px", minWidth: 0 },
  subject: { fontSize: tokens.fontSizeBase600, fontWeight: tokens.fontWeightSemibold, marginBottom: "14px" },
  fromRow: { display: "flex", gap: "12px", alignItems: "center" },
  body: { marginTop: "18px", maxWidth: "720px", lineHeight: tokens.lineHeightBase400 },
  approved: { marginTop: "16px", display: "flex", gap: "8px", alignItems: "center" },
  emptyBox: { flex: 1, display: "flex", alignItems: "center", justifyContent: "center", color: tokens.colorNeutralForeground3 },
  // activity
  actList: { width: "420px", flexShrink: 0, overflowY: "auto", borderRight: `1px solid ${tokens.colorNeutralStroke2}`, backgroundColor: tokens.colorNeutralBackground2 },
  actTop: { padding: "14px 16px 6px" },
  actItem: {
    display: "flex", gap: "10px", padding: "10px 16px", cursor: "pointer", position: "relative",
    ":hover": { backgroundColor: tokens.colorNeutralBackground1Hover },
  },
  dotUnread: { position: "absolute", left: "5px", top: "22px", width: "6px", height: "6px", borderRadius: "50%", backgroundColor: tokens.colorBrandForeground1 },
  kind: {
    position: "absolute", left: "38px", top: "30px", width: "18px", height: "18px", borderRadius: "50%",
    display: "flex", alignItems: "center", justifyContent: "center", fontSize: "10px",
    backgroundColor: tokens.colorNeutralBackground1, boxShadow: tokens.shadow4,
  },
  ctx: { flex: 1, padding: "24px 28px", overflowY: "auto" },
  ctxCard: { maxWidth: "720px", padding: "16px", borderRadius: tokens.borderRadiusLarge, backgroundColor: tokens.colorNeutralBackground2, marginTop: "12px" },
});

// ------------------------------------------------------------------ Mail
interface Mail { id: string; to: PersonId[]; onBehalfOf: PersonId; subject: string; time: string; body: string; approvedAt: string }

const MAILS: Mail[] = [
  {
    id: "e1", to: ["prince"], onBehalfOf: "rachitaa", subject: "Q1 pricing summary for big accounts", time: "Wed 26 Nov 10:42", approvedAt: "10:42",
    body: "Hi Prince,\n\nHere is the summary you asked for:\n• Desktop prices go up **5% from 1 Jan** (decided 20 Nov) [1]\n• Quotes sent **before 1 Dec** keep the old price [1]\n• 32 GB DDR5 rose **19%** from October to November [2]\n\nBest regards,\nMax, for Rachitaa\n\nSources: [1] Pricing thread, 20 Nov · [2] Parts prices.xlsx › Memory",
  },
  {
    id: "e2", to: ["prince", "praga", "rachitaa", "karthi"], onBehalfOf: "prince", subject: "Follow-up: Pricing weekly (Mon 24 Nov)", time: "Mon 24 Nov 11:20", approvedAt: "11:18",
    body: "Hi all,\n\nFollow-up from today's pricing weekly:\n📌 Decided: prices go up 5% from 1 Jan\n⏰ Rachitaa: tell big accounts by **Fri 5 Dec**\n⏰ Praga: price list by **Mon 24 Nov**\n\nBest regards,\nMax, for Prince",
  },
  {
    id: "e3", to: ["praga"], onBehalfOf: "prince", subject: "Supplier report: what we need by Mon 1 Dec", time: "Tue 25 Nov 09:05", approvedAt: "09:05",
    body: "Hi Praga,\n\nFor the supplier report due **Mon 1 Dec**, Prince would like: GPU prices from both suppliers, Supplier B's delivery date, and the volume discount.\n\nBest regards,\nMax, for Prince",
  },
];

export function MailScreen({ me }: { me: PersonId }) {
  const s = useStyles();
  const [folder, setFolder] = useState<"inbox" | "sent">("inbox");
  const items = MAILS.filter((m) => (folder === "inbox" ? m.to.includes(me) : m.onBehalfOf === me));
  const [openId, setOpenId] = useState<string | null>(items[0]?.id ?? null);
  const open = items.find((m) => m.id === openId) ?? items[0];
  return (
    <div className={s.wrap}>
      <nav className={s.folders}>
        <div className={s.title}>Mail</div>
        <div className={mergeClasses(s.folder, folder === "inbox" && s.folderActive)} onClick={() => setFolder("inbox")}>
          <Mail20Regular /> <span style={{ flex: 1 }}>Inbox</span>
          <Text size={200}>{MAILS.filter((m) => m.to.includes(me)).length}</Text>
        </div>
        <div className={mergeClasses(s.folder, folder === "sent" && s.folderActive)} onClick={() => setFolder("sent")}>
          <Send20Regular /> <span style={{ flex: 1 }}>Sent by Max for me</span>
        </div>
        <Text size={100} className={s.muted} block style={{ padding: "16px 10px" }}>
          Simulated mailbox. Max sends from its own mailbox, only after the person approves, and only inside the company.
        </Text>
      </nav>
      <div className={s.list}>
        {items.length === 0 && <div style={{ padding: 20 }} className={s.muted}>Nothing here.</div>}
        {items.map((m) => (
          <div key={m.id} className={mergeClasses(s.item, m.id === open?.id && s.itemActive)} onClick={() => setOpenId(m.id)}>
            <MaxAvatar size={32} />
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ display: "flex", gap: 6 }}>
                <Text weight="semibold" className={s.one} style={{ flex: 1 }}>Max for {personName(m.onBehalfOf)}</Text>
                <Text size={100} className={s.muted}>{m.time.split(" ").slice(0, 3).join(" ")}</Text>
              </div>
              <Text className={s.one}>{m.subject}</Text>
              <Text size={200} className={mergeClasses(s.one, s.muted)}>{m.body.replace(/\*\*/g, "").split("\n").filter(Boolean)[1]}</Text>
            </div>
          </div>
        ))}
      </div>
      {open ? (
        <div className={s.read}>
          <div className={s.subject}>{open.subject}</div>
          <div className={s.fromRow}>
            <MaxAvatar size={40} />
            <div style={{ flex: 1 }}>
              <Text weight="semibold" style={{ color: MAX_ORANGE }}>Max</Text>{" "}
              <Text className={s.muted}>&lt;max@thirdwave.test&gt; on behalf of {personName(open.onBehalfOf)}</Text>
              <div><Text size={200} className={s.muted}>To: {open.to.map(personName).join(", ")} · {open.time}</Text></div>
            </div>
            <Button appearance="subtle" icon={<ArrowReply20Regular />}>Reply</Button>
          </div>
          <div className={s.body}><RichText text={open.body} /></div>
          <Divider style={{ marginTop: 18 }} />
          <div className={s.approved}>
            <Badge appearance="tint" color="success">Approved</Badge>
            <Text size={200} className={s.muted}>by {personName(open.onBehalfOf)} at {open.approvedAt}, from the approval card in Teams</Text>
          </div>
        </div>
      ) : <div className={s.emptyBox}>No email selected</div>}
    </div>
  );
}

// ------------------------------------------------------------------ Activity
type Kind = "mention" | "reply" | "reaction" | "max";
interface Act { id: string; who: PersonId | "max"; kind: Kind; text: string; where: string; time: string; unread?: boolean; detail?: string; forOnly?: PersonId[] }

const ACTS: Act[] = [
  { id: "a1", who: "max", kind: "max", text: "Approval needed: send the Q1 pricing summary to Prince?", where: "Chat with Max", time: "10:41", unread: true, forOnly: ["rachitaa"], detail: "⚠️ **Send this email?** Open the chat with Max to approve, edit or deny." },
  { id: "a2", who: "max", kind: "max", text: "New lesson from Praga to accept", where: "Chat with Max", time: "10:05", unread: true, forOnly: ["prince"], detail: "📌 \"For memory prices, use the Parts prices sheet, not the slides.\" From a 👎 on Tue 25 Nov. **Accept / Edit / Reject** in the chat with Max." },
  { id: "a3", who: "prince", kind: "mention", text: "mentioned you: \"Rachitaa, please let the big accounts know before 5 Dec.\"", where: "Product Planning › Pricing", time: "Thu 20 Nov", unread: true, forOnly: ["rachitaa"] },
  { id: "a4", who: "max", kind: "max", text: "⏰ The price list you own was due Mon 24 Nov", where: "Chat with Max", time: "09:00", unread: true, forOnly: ["praga"], detail: "⏰ Hi Praga, the **price list** you own was due **Mon 24 Nov** (new model launch). **Done / New date / Blocked** · Stop these" },
  { id: "a5", who: "max", kind: "max", text: "⚠️ #Pricing is 3 hours behind (catching up)", where: "Chat with Max", time: "08:15", forOnly: ["karthi", "prince"], detail: "⚠️ **#Pricing is 3 hours behind.** Teams stopped sending updates at 05:10. I'm catching up now. **Open health view**" },
  { id: "a6", who: "rachitaa", kind: "reply", text: "replied: \"Noted. Does that include the order we're quoting for Northwind?\"", where: "Product Planning › Pricing", time: "Thu 20 Nov", forOnly: ["prince"] },
  { id: "a7", who: "praga", kind: "reaction", text: "reacted 👍 to your message", where: "New model sync", time: "Yesterday", forOnly: ["prince"] },
  { id: "a8", who: "max", kind: "max", text: "📅 Brief ready: New model check-in (Fri 10:00)", where: "Calendar", time: "Yesterday", forOnly: ["prince", "praga", "rachitaa", "karthi"], detail: "📅 **New model check-in** · Fri 28 Nov, 10:00 JST. Open items: price list (late), GPU decision (blocked). Open the meeting in Calendar." },
];

const KIND_ICON: Record<Kind, JSX.Element | string> = { mention: <Mention12Regular />, reply: <ChatMultiple20Regular fontSize={12} />, reaction: "👍", max: "☁" };

export function ActivityScreen({ me }: { me: PersonId }) {
  const s = useStyles();
  const [filter, setFilter] = useState("all");
  const mine = ACTS.filter((a) => !a.forOnly || a.forOnly.includes(me))
    .filter((a) => filter === "all" || (filter === "unread" ? a.unread : filter === "mentions" ? a.kind === "mention" : a.kind === "max"));
  const [openId, setOpenId] = useState<string | null>(mine[0]?.id ?? null);
  const open = mine.find((a) => a.id === openId) ?? mine[0];
  return (
    <div className={s.wrap}>
      <div className={s.actList}>
        <div className={s.actTop}>
          <Text size={500} weight="bold" block>Activity</Text>
          <TabList size="small" selectedValue={filter} onTabSelect={(_, d) => setFilter(String(d.value))} style={{ marginTop: 6 }}>
            <Tab value="all">All</Tab><Tab value="unread">Unread</Tab><Tab value="mentions">Mentions</Tab><Tab value="max">From Max</Tab>
          </TabList>
        </div>
        {mine.map((a) => {
          const p = PEOPLE.find((x) => x.id === a.who);
          return (
            <div key={a.id} className={mergeClasses(s.actItem, a.id === open?.id && s.itemActive)} onClick={() => setOpenId(a.id)}>
              {a.unread && <span className={s.dotUnread} />}
              {a.who === "max" ? <MaxAvatar size={36} /> : <Avatar name={personName(a.who)} color={p?.color} size={36} />}
              <span className={s.kind} style={a.kind === "max" ? { color: MAX_ORANGE } : undefined}>{KIND_ICON[a.kind]}</span>
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{ display: "flex", gap: 6 }}>
                  <Text weight={a.unread ? "bold" : "semibold"} style={a.who === "max" ? { color: MAX_ORANGE } : undefined}>{personName(a.who)}</Text>
                  <span style={{ flex: 1 }} />
                  <Text size={100} className={s.muted}>{a.time}</Text>
                </div>
                <Text size={200} block weight={a.unread ? "semibold" : "regular"}>{a.text}</Text>
                <Text size={100} className={s.muted}>{a.where}</Text>
              </div>
            </div>
          );
        })}
        {mine.length === 0 && <div style={{ padding: 20 }} className={s.muted}>Nothing here.</div>}
      </div>
      <div className={s.ctx}>
        {open ? (
          <>
            <Text size={200} className={s.muted}>{open.where}</Text>
            <div className={s.ctxCard}>
              <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8 }}>
                {open.who === "max" ? <MaxAvatar size={24} /> : <Avatar size={24} name={personName(open.who)} />}
                <Text weight="semibold" style={open.who === "max" ? { color: MAX_ORANGE } : undefined}>{personName(open.who)}</Text>
                {open.who === "max" && <Badge appearance="tint" color="informative" size="small">Only you can see this</Badge>}
              </div>
              <RichText text={open.detail ?? open.text} />
            </div>
            <Button appearance="primary" style={{ marginTop: 14 }}>Go to {open.where}</Button>
          </>
        ) : null}
      </div>
    </div>
  );
}
