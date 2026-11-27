// UI design mock-up 1: simulator bar + Teams frame + channel view (static data, Max not connected).
import { useMemo, useState } from "react";
import {
  Avatar,
  Badge,
  Button,
  FluentProvider,
  Input,
  Link,
  Menu,
  MenuItemRadio,
  MenuList,
  MenuPopover,
  MenuTrigger,
  Tab,
  TabList,
  Text,
  Textarea,

  makeStyles,
  mergeClasses,
  teamsDarkTheme,
  teamsHighContrastTheme,
  teamsLightTheme,
  tokens,
} from "@fluentui/react-components";
import {
  Alert24Regular,
  ArrowCounterclockwise16Regular,
  CalendarLtr24Regular,
  Chat24Regular,
  ChevronDown12Regular,
  ChevronRight12Regular,
  LockClosed12Regular,
  Mail24Regular,
  PeopleTeam24Filled,
  Search20Regular,
  Send20Regular,
  ThumbDislike16Regular,
  ThumbLike16Regular,
} from "@fluentui/react-icons";
import { PEOPLE, TEAMS, THREADS, type Message, type PersonId, type Thread } from "./mock";
import { MAX_ORANGE, MaxAvatar, RichText, Sources, personName } from "./ui";
import { ChatScreen, type NavTarget } from "./ChatScreen";
import { FilesTab, PlansTab } from "./ChannelTabs";
import { CalendarScreen } from "./CalendarScreen";
import { ActivityScreen, MailScreen } from "./MailActivity";
import { MaxApp } from "./MaxApp";
import { CardsGallery } from "./CardsGallery";
import { EmojiCompare } from "./EmojiCompare";
import { AvatarLab } from "./avatar/AvatarLab";

const THEMES = { light: teamsLightTheme, dark: teamsDarkTheme, contrast: teamsHighContrastTheme };
type ThemeName = keyof typeof THEMES;

const useStyles = makeStyles({
  root: { display: "flex", flexDirection: "column", height: "100vh", backgroundColor: tokens.colorNeutralBackground3 },
  simBar: {
    display: "flex", alignItems: "center", gap: "12px", height: "32px", padding: "0 12px", flexShrink: 0,
    backgroundColor: "#1b1a19", color: "#ffffff", fontSize: tokens.fontSizeBase200,
    backgroundImage: "repeating-linear-gradient(135deg, #1b1a19 0 14px, #252423 14px 28px)",
  },
  simTag: { fontWeight: tokens.fontWeightSemibold, letterSpacing: "0.04em", color: "#ffd8a8" },
  simBtn: { color: "#ffffff", minWidth: "auto" },
  titleBar: {
    display: "flex", alignItems: "center", justifyContent: "center", height: "48px", flexShrink: 0, position: "relative",
    backgroundColor: tokens.colorNeutralBackground2, borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  search: { width: "min(560px, 50vw)" },
  me: { position: "absolute", right: "16px" },
  body: { display: "flex", flex: 1, minHeight: 0 },
  rail: {
    width: "68px", display: "flex", flexDirection: "column", alignItems: "center", paddingTop: "4px", gap: "2px",
    backgroundColor: tokens.colorNeutralBackground2, borderRight: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  railItem: {
    width: "64px", height: "56px", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
    gap: "2px", fontSize: tokens.fontSizeBase100, color: tokens.colorNeutralForeground2, cursor: "pointer",
    borderRadius: tokens.borderRadiusMedium, position: "relative",
    ":hover": { backgroundColor: tokens.colorNeutralBackground1Hover, color: tokens.colorBrandForeground1 },
  },
  railActive: {
    color: tokens.colorBrandForeground1,
    "::before": {
      content: '""', position: "absolute", left: "0", top: "14px", bottom: "14px", width: "3px",
      borderRadius: "2px", backgroundColor: tokens.colorBrandForeground1,
    },
  },
  list: {
    width: "280px", flexShrink: 0, display: "flex", flexDirection: "column", overflowY: "auto",
    backgroundColor: tokens.colorNeutralBackground2, borderRight: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  listHeader: { padding: "16px 16px 8px", fontSize: tokens.fontSizeBase500, fontWeight: tokens.fontWeightBold },
  teamRow: {
    display: "flex", alignItems: "center", gap: "8px", padding: "6px 12px", cursor: "pointer",
    fontWeight: tokens.fontWeightSemibold, ":hover": { backgroundColor: tokens.colorNeutralBackground1Hover },
  },
  teamAvatar: { borderRadius: tokens.borderRadiusMedium },
  channelRow: {
    display: "flex", alignItems: "center", gap: "6px", padding: "6px 12px 6px 52px", cursor: "pointer",
    color: tokens.colorNeutralForeground2, ":hover": { backgroundColor: tokens.colorNeutralBackground1Hover },
  },
  channelActive: {
    backgroundColor: tokens.colorNeutralBackground1Selected, color: tokens.colorNeutralForeground1,
    fontWeight: tokens.fontWeightSemibold,
  },
  main: { flex: 1, display: "flex", flexDirection: "column", minWidth: 0, backgroundColor: tokens.colorNeutralBackground3 },
  channelHeader: {
    display: "flex", alignItems: "center", gap: "12px", padding: "8px 20px 0", flexShrink: 0,
    backgroundColor: tokens.colorNeutralBackground1, borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  feed: { flex: 1, overflowY: "auto", padding: "16px 20px", display: "flex", flexDirection: "column", gap: "16px" },
  thread: {
    maxWidth: "860px", backgroundColor: tokens.colorNeutralBackground1, borderRadius: tokens.borderRadiusLarge,
    boxShadow: tokens.shadow2, overflow: "hidden",
  },
  msg: { display: "flex", gap: "12px", padding: "12px 16px" },
  reply: { padding: "10px 16px 10px 32px", borderTop: `1px solid ${tokens.colorNeutralStroke3}` },
  msgHead: { display: "flex", alignItems: "baseline", gap: "8px", flexWrap: "wrap" },
  msgText: { whiteSpace: "pre-wrap", lineHeight: tokens.lineHeightBase300, marginTop: "2px" },
  maxName: { color: MAX_ORANGE, fontWeight: tokens.fontWeightSemibold },
  aiTag: { fontSize: tokens.fontSizeBase100 },
  cite: {
    display: "inline-flex", alignItems: "center", justifyContent: "center", minWidth: "16px", height: "16px",
    padding: "0 3px", margin: "0 1px", borderRadius: "4px", fontSize: "10px", verticalAlign: "1px",
    backgroundColor: tokens.colorNeutralBackground5, color: tokens.colorNeutralForeground2, cursor: "pointer",
  },
  sources: { marginTop: "8px", display: "flex", flexDirection: "column", gap: "2px", fontSize: tokens.fontSizeBase200 },
  feedback: { display: "flex", gap: "4px", marginTop: "6px" },
  moreReplies: { padding: "6px 16px 6px 32px", borderTop: `1px solid ${tokens.colorNeutralStroke3}` },
  replyBox: { padding: "8px 16px 12px 32px", borderTop: `1px solid ${tokens.colorNeutralStroke3}` },
  compose: { padding: "12px 20px 16px", flexShrink: 0 },
  composeInner: { maxWidth: "860px", display: "flex", gap: "8px", alignItems: "flex-end" },
  empty: { color: tokens.colorNeutralForeground3, padding: "40px", textAlign: "center" },
});

function MessageView({ m, isReply }: { m: Message; isReply?: boolean }) {
  const s = useStyles();
  const isMax = m.author === "max";
  const person = PEOPLE.find((p) => p.id === m.author);
  return (
    <div className={mergeClasses(s.msg, isReply && s.reply)}>
      {isMax ? <MaxAvatar size={isReply ? 28 : 32} /> : (
        <Avatar name={personName(m.author)} color={person?.color ?? "neutral"} size={isReply ? 28 : 32} />
      )}
      <div style={{ minWidth: 0, flex: 1 }}>
        <div className={s.msgHead}>
          <Text weight="semibold" className={isMax ? s.maxName : undefined}>{personName(m.author)}</Text>
          <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>{m.time}</Text>
          {isMax && <Badge appearance="tint" color="informative" size="small" className={s.aiTag}>AI generated</Badge>}
          {m.edited && <Text size={200} italic>Edited</Text>}
        </div>
        <RichText text={m.text} />
        {m.sources && <Sources sources={m.sources} />}
        {isMax && (
          <div className={s.feedback}>
            <Button size="small" appearance="subtle" icon={<ThumbLike16Regular />} aria-label="Helpful" />
            <Button size="small" appearance="subtle" icon={<ThumbDislike16Regular />} aria-label="Not helpful" />
          </div>
        )}
      </div>
    </div>
  );
}

function ThreadView({ t, me, onReply }: { t: Thread; me: PersonId; onReply: (id: string, text: string) => void }) {
  const s = useStyles();
  const [open, setOpen] = useState(t.replies.length <= 2);
  const [draft, setDraft] = useState("");
  const shown = open ? t.replies : t.replies.slice(-1);
  return (
    <div className={s.thread}>
      <MessageView m={t.post} />
      {!open && t.replies.length > 1 && (
        <div className={s.moreReplies}>
          <Link onClick={() => setOpen(true)}>
            {t.replies.length - 1} more {t.replies.length - 1 === 1 ? "reply" : "replies"} from{" "}
            {[...new Set(t.replies.slice(0, -1).map((r) => personName(r.author)))].join(", ")}
          </Link>
        </div>
      )}
      {shown.map((r) => <MessageView key={r.id} m={r} isReply />)}
      <div className={s.replyBox}>
        <Input
          placeholder={`Reply as ${personName(me)}`}
          value={draft}
          onChange={(_, d) => setDraft(d.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && draft.trim()) { onReply(t.id, draft.trim()); setDraft(""); }
          }}
          style={{ width: "100%" }}
        />
      </div>
    </div>
  );
}

export function App() {
  const s = useStyles();
  const q = new URLSearchParams(window.location.search);
  const [themeName, setThemeName] = useState<ThemeName>(
    (q.get("theme") as ThemeName) ?? (window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light"),
  );
  const [me, setMe] = useState<PersonId>((q.get("as") as PersonId) ?? "prince");
  const [channelId, setChannelId] = useState(q.get("channel") ?? "pp-pricing");
  const [openTeams, setOpenTeams] = useState<Record<string, boolean>>({ planning: true, procurement: true, sales: true });
  const [threads, setThreads] = useState<Thread[]>(THREADS);
  const [newPost, setNewPost] = useState("");
  const [tab, setTab] = useState(q.get("tab") ?? "posts");
  const [view, setView] = useState(q.get("view") ?? "teams");
  // deep links from cards and Max's pages ("Open Max", "Open plan", "Ask Max"); demo flags only apply to the first load
  const [nav, setNav] = useState<NavTarget & { n: number }>({
    view: q.get("view") ?? "teams", chat: q.get("chat") ?? "max", mtab: q.get("mtab") ?? undefined, meeting: q.get("meeting") ?? undefined, n: 0,
  });
  const open = (to: NavTarget) => {
    setNav((o) => ({ ...o, ...to, n: o.n + 1 }));
    if (to.channel) setChannelId(to.channel);
    if (to.tab) setTab(to.tab);
    setView(to.view);
  };
  const firstLoad = nav.n === 0;

  const myTeams = useMemo(
    () =>
      TEAMS.filter((t) => t.members.includes(me)).map((t) => ({
        ...t,
        channels: t.channels.filter((c) => !c.privateFor || c.privateFor.includes(me)),
      })),
    [me],
  );
  const allChannels = myTeams.flatMap((t) => t.channels.map((c) => ({ ...c, team: t.name })));
  const current = allChannels.find((c) => c.id === channelId) ?? allChannels[0];
  const meP = PEOPLE.find((p) => p.id === me)!;

  const now = () => "Wed 26 Nov " + new Date().toTimeString().slice(0, 5);
  const addReply = (threadId: string, text: string) => {
    setThreads((ts) => ts.map((t) => t.id === threadId
      ? { ...t, replies: [...t.replies, { id: crypto.randomUUID(), author: me, time: now(), text }] }
      : t));
    if (/@max\b/i.test(text)) {
      setTimeout(() => setThreads((ts) => ts.map((t) => t.id === threadId
        ? { ...t, replies: [...t.replies, { id: crypto.randomUUID(), author: "max", time: now(),
            text: "This is a design mock-up, so I'm not connected yet. In the real simulator I'd answer here with sources." }] }
        : t)), 900);
    }
  };
  const addPost = () => {
    if (!newPost.trim() || !current) return;
    setThreads((ts) => [...ts, { id: crypto.randomUUID(), channelId: current.id,
      post: { id: crypto.randomUUID(), author: me, time: now(), text: newPost.trim() }, replies: [] }]);
    setNewPost("");
  };

  const rail = [
    { key: "activity", label: "Activity", icon: <Alert24Regular /> },
    { key: "chat", label: "Chat", icon: <Chat24Regular /> },
    { key: "teams", label: "Teams", icon: <PeopleTeam24Filled /> },
    { key: "calendar", label: "Calendar", icon: <CalendarLtr24Regular /> },
    { key: "mail", label: "Mail", icon: <Mail24Regular /> },
    { key: "max", label: "Max", icon: <MaxAvatar size={24} /> },
  ];

  return (
    <FluentProvider theme={THEMES[themeName]} style={{ height: "100%" }}>
      <div className={s.root}>
        {/* 1. Simulator bar: never part of the Teams look */}
        <div className={s.simBar}>
          <span className={s.simTag}>SIMULATED TEAMS</span>
          <span>·</span>
          <Menu>
            <MenuTrigger disableButtonEnhancement>
              <Button size="small" appearance="transparent" className={s.simBtn} icon={<ChevronDown12Regular />} iconPosition="after">
                Playing as {meP.name}
              </Button>
            </MenuTrigger>
            <MenuPopover>
              <MenuList checkedValues={{ who: [me] }} onCheckedValueChange={(_, d) => setMe(d.checkedItems[0] as PersonId)}>
                {PEOPLE.map((p) => (
                  <MenuItemRadio key={p.id} name="who" value={p.id} secondaryContent={p.role}
                    icon={<Avatar name={p.name} color={p.color} size={20} />}>
                    {p.name}
                  </MenuItemRadio>
                ))}
              </MenuList>
            </MenuPopover>
          </Menu>
          <Menu>
            <MenuTrigger disableButtonEnhancement>
              <Button size="small" appearance="transparent" className={s.simBtn} icon={<ChevronDown12Regular />} iconPosition="after">
                Theme: {themeName === "contrast" ? "High contrast" : themeName[0].toUpperCase() + themeName.slice(1)}
              </Button>
            </MenuTrigger>
            <MenuPopover>
              <MenuList checkedValues={{ theme: [themeName] }} onCheckedValueChange={(_, d) => setThemeName(d.checkedItems[0] as ThemeName)}>
                <MenuItemRadio name="theme" value="light">Light</MenuItemRadio>
                <MenuItemRadio name="theme" value="dark">Dark</MenuItemRadio>
                <MenuItemRadio name="theme" value="contrast">High contrast</MenuItemRadio>
              </MenuList>
            </MenuPopover>
          </Menu>
          <div style={{ flex: 1 }} />
          <Button size="small" appearance="transparent" className={s.simBtn} icon={<ArrowCounterclockwise16Regular />}
            onClick={() => setThreads(THREADS)}>
            Reset world
          </Button>
        </div>

        {/* 2. Teams title bar */}
        <div className={s.titleBar}>
          <Input className={s.search} contentBefore={<Search20Regular />} placeholder="Search" appearance="filled-darker" />
          <Avatar className={s.me} name={meP.name} color={meP.color} size={32} badge={{ status: "available" }} />
        </div>

        <div className={s.body}>
          {/* App rail */}
          <nav className={s.rail}>
            {rail.map((r) => (
              <div key={r.key} className={mergeClasses(s.railItem, r.key === view && s.railActive)}
                onClick={() => { if (r.key !== view) setNav((o) => ({ ...o, mtab: undefined, meeting: undefined, n: o.n + 1 })); setView(r.key); }}>
                {r.icon}
                <span>{r.label}</span>
              </div>
            ))}
          </nav>

          {view === "chat" && <ChatScreen me={me} initialChat={nav.chat ?? "max"} fresh={firstLoad && q.get("fresh") === "1"} demo={firstLoad ? q.get("demo") ?? undefined : undefined} dark={themeName !== "light"} onOpen={open} key={me} />}
          {view === "calendar" && <CalendarScreen me={me} initialMeeting={nav.meeting} key={me} />}
          {view === "mail" && <MailScreen me={me} key={me} />}
          {view === "emoji" && <EmojiCompare />}
          {view === "avatar" && <AvatarLab />}
          {view === "cards" && <CardsGallery dark={themeName !== "light"} only={q.get("cards")?.split(",")} />}
          {view === "max" && <MaxApp me={me} key={me} initialTab={nav.mtab} initialStep={Number(q.get("step") ?? 0)} onOpen={open} />}
          {view === "activity" && <ActivityScreen me={me} key={me} />}
          {!["chat", "teams", "calendar", "mail", "activity", "max", "cards", "emoji", "avatar"].includes(view) && <div className={s.empty} style={{ flex: 1 }}>The {view} screen is designed in a later mock-up.</div>}
          {view === "teams" && <>
          {/* 3. Teams and channels */}
          <aside className={s.list}>
            <div className={s.listHeader}>Teams</div>
            {myTeams.map((t) => (
              <div key={t.id}>
                <div className={s.teamRow} onClick={() => setOpenTeams((o) => ({ ...o, [t.id]: !o[t.id] }))}>
                  {openTeams[t.id] ? <ChevronDown12Regular /> : <ChevronRight12Regular />}
                  <Avatar shape="square" name={t.name} size={28} className={s.teamAvatar} />
                  {t.name}
                </div>
                {openTeams[t.id] && t.channels.map((c) => (
                  <div key={c.id} className={mergeClasses(s.channelRow, c.id === current?.id && s.channelActive)}
                    onClick={() => setChannelId(c.id)}>
                    {c.name}
                    {c.privateFor && <LockClosed12Regular aria-label="Private channel" />}
                  </div>
                ))}
              </div>
            ))}
          </aside>

          {/* Channel view */}
          <main className={s.main}>
            {current && (
              <>
                <div className={s.channelHeader}>
                  <Avatar shape="square" name={current.team} size={32} />
                  <div>
                    <Text weight="bold" size={400}>{current.name}</Text>{" "}
                    {current.privateFor && <LockClosed12Regular />}
                    <div><Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>{current.team}</Text></div>
                  </div>
                  <TabList selectedValue={tab} onTabSelect={(_, d) => setTab(String(d.value))} style={{ marginLeft: "12px" }}>
                    <Tab value="posts">Posts</Tab>
                    <Tab value="files">Files</Tab>
                    <Tab value="plans">Plans</Tab>
                  </TabList>
                </div>
                {tab === "files" && <FilesTab />}
                {tab === "plans" && <PlansTab me={me} initialView={q.get("pview") ?? "list"} />}
                {tab === "posts" && <div className={s.feed}>
                  {tab === "posts" && threads.filter((t) => t.channelId === current.id).length === 0 && (
                    <div className={s.empty}>No posts yet in {current.name}.</div>
                  )}
                  {tab === "posts" && threads.filter((t) => t.channelId === current.id).map((t) => (
                    <ThreadView key={t.id} t={t} me={me} onReply={addReply} />
                  ))}
                </div>}
                {tab === "posts" && (
                  <div className={s.compose}>
                    <div className={s.composeInner}>
                      <Textarea resize="vertical" style={{ flex: 1 }} value={newPost}
                        placeholder={`Start a post in ${current.name} as ${meP.name} (type @Max to ask Max)`}
                        onChange={(_, d) => setNewPost(d.value)} />
                      <Button appearance="primary" icon={<Send20Regular />} onClick={addPost}>Post</Button>
                    </div>
                  </div>
                )}
              </>
            )}
          </main>
          </>}
        </div>
      </div>
    </FluentProvider>
  );
}
