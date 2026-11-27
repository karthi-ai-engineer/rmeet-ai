// Simulator bar + Teams frame + channel view. Real mode: data and live updates from the simulator server (api.ts).
// Showcase mode (?demo= / ?fresh= / ?step=, or server not reachable): the agreed design mock-ups on mock data.
import { Fragment, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
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
import { SHOWCASE, api, chatTime, postTime, startLive, stopLive, useLive, type ApiMessage, type ApiThread, type World } from "./api";
import { MAX_ORANGE, MaxAvatar, RichText, Sources, personName, setDirectory } from "./ui";
import { ChatScreen, type NavTarget } from "./ChatScreen";
import { ChannelFiles, FilesTab, PlansTab } from "./ChannelTabs";
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
    maxWidth: "860px", flexShrink: 0, // long history: cards keep their size, the feed scrolls backgroundColor: tokens.colorNeutralBackground1, borderRadius: tokens.borderRadiusLarge,
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
  dayDivider: {
    maxWidth: "860px", display: "flex", alignItems: "center", gap: "12px", flexShrink: 0,
    fontSize: tokens.fontSizeBase200, color: tokens.colorNeutralForeground3,
    "::before": { content: '""', flex: 1, borderTop: `1px solid ${tokens.colorNeutralStroke2}` },
    "::after": { content: '""', flex: 1, borderTop: `1px solid ${tokens.colorNeutralStroke2}` },
  },
});

// server messages in the shape the screens use
const toMessage = (m: ApiMessage): Message => ({ id: m.id, author: m.author, time: postTime(m.created_at), at: m.created_at, text: m.text,
  edited: !!m.edited_at, aiLabel: !!m.ai_label, feedback: !!m.feedback });
const toThread = (t: ApiThread): Thread => ({ id: t.id, channelId: t.where_id, post: toMessage(t), replies: t.replies.map(toMessage) });

/** A live message or edit in the open channel, merged into the threads (same id = replace). */
function mergeLive(ts: Thread[], m: ApiMessage): Thread[] {
  const msg = toMessage(m);
  if (!m.thread_id) {
    if (m.deleted) return ts.filter((t) => t.id !== m.id);
    if (ts.some((t) => t.id === m.id)) return ts.map((t) => (t.id === m.id ? { ...t, post: msg } : t));
    return [...ts, { id: m.id, channelId: m.where_id, post: msg, replies: [] }];
  }
  return ts.map((t) => {
    if (t.id !== m.thread_id) return t;
    if (m.deleted) return { ...t, replies: t.replies.filter((r) => r.id !== m.id) };
    if (t.replies.some((r) => r.id === m.id)) return { ...t, replies: t.replies.map((r) => (r.id === m.id ? msg : r)) };
    return { ...t, replies: [...t.replies, msg] };
  });
}

function MessageView({ m, isReply }: { m: Message; isReply?: boolean }) {
  const s = useStyles();
  const isMax = m.author === "max";
  const person = PEOPLE.find((p) => p.id === m.author);
  return (
    <div className={mergeClasses(s.msg, isReply && s.reply)} data-testid="msg" data-author={m.author} data-msg-id={m.id}>
      {isMax ? <MaxAvatar size={isReply ? 28 : 32} /> : (
        <Avatar name={personName(m.author)} color={person?.color ?? "neutral"} size={isReply ? 28 : 32} />
      )}
      <div style={{ minWidth: 0, flex: 1 }}>
        <div className={s.msgHead}>
          <Text weight="semibold" className={isMax ? s.maxName : undefined}>{personName(m.author)}</Text>
          <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>{m.time}</Text>
          {isMax && (m.aiLabel ?? true) && <Badge appearance="tint" color="informative" size="small" className={s.aiTag}>AI generated</Badge>}
          {m.edited && <Text size={200} italic>Edited</Text>}
        </div>
        <RichText text={m.text} />
        {m.sources && <Sources sources={m.sources} />}
        {isMax && (m.feedback ?? true) && (
          <div className={s.feedback}>
            <Button size="small" appearance="subtle" icon={<ThumbLike16Regular />} aria-label="Helpful" />
            <Button size="small" appearance="subtle" icon={<ThumbDislike16Regular />} aria-label="Not helpful" />
          </div>
        )}
      </div>
    </div>
  );
}

function ThreadView({ t, me, onReply, maxTyping }: { t: Thread; me: PersonId; onReply: (id: string, text: string) => Promise<boolean>; maxTyping?: boolean }) {
  const s = useStyles();
  const [open, setOpen] = useState(t.replies.length <= 2);
  const [draft, setDraft] = useState("");
  const shown = open ? t.replies : t.replies.slice(-1);
  const send = async () => { if (draft.trim() && await onReply(t.id, draft.trim())) setDraft(""); }; // keep the text if it failed
  return (
    <div className={s.thread} data-testid="thread" data-thread-id={t.id}>
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
      {maxTyping && (
        <div className={mergeClasses(s.msg, s.reply)} data-testid="typing" style={{ alignItems: "center" }}>
          <MaxAvatar size={28} />
          <Text size={200} italic style={{ color: tokens.colorNeutralForeground3 }}>Max is typing…</Text>
        </div>
      )}
      <div className={s.replyBox}>
        <Input
          data-testid="reply-box"
          placeholder={`Reply as ${personName(me)}`}
          value={draft}
          onChange={(_, d) => setDraft(d.value)}
          onKeyDown={(e) => { if (e.key === "Enter") send(); }}
          contentAfter={draft.trim() ? (
            <Button data-testid="reply-send" size="small" appearance="transparent" aria-label="Send reply"
              icon={<Send20Regular />} onClick={send} />
          ) : undefined}
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

  // ---- real mode vs showcase mode: THE one switch. Real = data from the simulator server, Max answers for real.
  const [world, setWorld] = useState<World | null>(null);
  const [offline, setOffline] = useState(false); // server not reachable at the start: fall back to the mock-ups
  const real = !SHOWCASE && !offline;
  const ready = real && world?.me.id === me; // the loaded data belongs to the person being played
  const [reloadKey, setReloadKey] = useState(0); // bump = load everything again (reset, reconnect)
  const [resetKey, setResetKey] = useState(0);   // bump = world was reset: screens start fresh (a reconnect keeps your place)
  const [maxTyping, setMaxTyping] = useState<{ where: string; thread: string | null } | null>(null);

  useEffect(() => {
    if (!real) return;
    let gone = false;
    api.state(me).then((w) => { if (!gone) { setDirectory(w.directory); setWorld(w); } }).catch(() => { if (!gone && !world) setOffline(true); });
    return () => { gone = true; };
  }, [real, me, reloadKey]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!real) return;
    startLive(me);
    return () => stopLive();
  }, [real, me]);

  const myTeams = useMemo(
    () => real
      ? (world?.teams ?? []).map((t) => ({ ...t, channels: t.channels.map((c) => ({ id: c.id, name: c.name, locked: !!c.private })) }))
      : TEAMS.filter((t) => t.members.includes(me)).map((t) => ({
          ...t,
          channels: t.channels.filter((c) => !c.privateFor || c.privateFor.includes(me)).map((c) => ({ id: c.id, name: c.name, locked: !!c.privateFor })),
        })),
    [me, real, world],
  );
  const allChannels = myTeams.flatMap((t) => t.channels.map((c) => ({ ...c, team: t.name })));
  const current = allChannels.find((c) => c.id === channelId) ?? allChannels[0];
  const meP = PEOPLE.find((p) => p.id === me) ?? PEOPLE[0];
  const people = real && world ? world.people.map((p) => ({ ...p, color: PEOPLE.find((x) => x.id === p.id)?.color ?? "brand" as const })) : PEOPLE;

  // real mode: the open channel's threads from the server
  const arrivedWhileLoading = useRef<ApiMessage[] | null>(null);
  useEffect(() => {
    if (!ready || !current) return;
    let gone = false;
    setMaxTyping(null);
    arrivedWhileLoading.current = []; // live messages that come in while loading are applied on top of the result
    api.threads(me, current.id).then((ts) => {
      if (gone) return;
      let next = ts.map(toThread);
      for (const m of arrivedWhileLoading.current ?? []) next = mergeLive(next, m);
      arrivedWhileLoading.current = null;
      setThreads(next);
    }).catch(() => {});
    return () => { gone = true; };
  }, [ready, me, current?.id, reloadKey]); // eslint-disable-line react-hooks/exhaustive-deps

  useLive((e) => {
    if (e.type === "reset") setResetKey((k) => k + 1);
    if (e.type === "reset" || e.type === "connected") { setReloadKey((k) => k + 1); return; }
    if (e.type === "typing" || e.type === "stream") {
      if (e.kind === "channel" && e.where === current?.id) setMaxTyping({ where: e.where, thread: e.thread_id });
      return;
    }
    const m = e.message;
    if (m.where_kind !== "channel" || m.where_id !== current?.id) return;
    if (m.author === "max") setMaxTyping(null);
    arrivedWhileLoading.current?.push(m);
    setThreads((ts) => mergeLive(ts, m));
  }, real);
  useEffect(() => { // a typing note goes away by itself if no answer comes
    if (!maxTyping) return;
    const t = window.setTimeout(() => setMaxTyping(null), 20_000);
    return () => window.clearTimeout(t);
  }, [maxTyping]);

  // the open channel's posts; real mode opens at the newest post (bottom, like Teams) and follows new posts
  // while you are at the bottom (scrolled up to read older posts = it stays where you are)
  const shown = current ? threads.filter((t) => t.channelId === current.id) : [];
  const feedRef = useRef<HTMLDivElement>(null);
  const stickRef = useRef(true);
  const feedKey = `${me}|${current?.id}|${tab}|${view}`;
  const lastFeedKey = useRef("");
  useLayoutEffect(() => {
    if (!real) return;
    if (lastFeedKey.current !== feedKey) { lastFeedKey.current = feedKey; stickRef.current = true; }
    const el = feedRef.current;
    if (el && stickRef.current) el.scrollTop = el.scrollHeight;
  }, [real, feedKey, threads]);

  const switchPerson = (id: PersonId) => {
    setMe(id);
    const u = new URL(window.location.href);
    u.searchParams.set("as", id);
    window.history.replaceState(null, "", u);
  };
  const resetWorld = () => {
    if (!real) { setThreads(THREADS); return; }
    api.reset().then(() => setReloadKey((k) => k + 1)).catch(() => {});
  };

  const now = () => "Wed 26 Nov " + new Date().toTimeString().slice(0, 5);
  const [sendError, setSendError] = useState<string | null>(null);
  const sent = (m: ApiMessage) => { setSendError(null); setThreads((ts) => mergeLive(ts, m)); return true; };
  const failed = (e: unknown) => { setSendError(`Couldn't send: ${e instanceof Error ? e.message : e}. Your text is kept.`); return false; };
  const addReply = async (threadId: string, text: string): Promise<boolean> => {
    if (real) {
      if (!current) return false;
      return api.post({ as: me, kind: "channel", where: current.id, text, thread_id: threadId }).then(sent, failed);
    }
    setThreads((ts) => ts.map((t) => t.id === threadId
      ? { ...t, replies: [...t.replies, { id: crypto.randomUUID(), author: me, time: now(), text }] }
      : t));
    if (/@max\b/i.test(text)) {
      setTimeout(() => setThreads((ts) => ts.map((t) => t.id === threadId
        ? { ...t, replies: [...t.replies, { id: crypto.randomUUID(), author: "max", time: now(),
            text: "This is a design mock-up, so I'm not connected yet. In the real simulator I'd answer here with sources." }] }
        : t)), 900);
    }
    return true;
  };
  const addPost = () => {
    if (!newPost.trim() || !current) return;
    if (real) { // the box is cleared only when the server has the post
      stickRef.current = true; // your own new post: show it
      api.post({ as: me, kind: "channel", where: current.id, text: newPost.trim() })
        .then((m) => { sent(m); setNewPost(""); }, failed);
      return;
    }
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
              <Button size="small" appearance="transparent" className={s.simBtn} icon={<ChevronDown12Regular />} iconPosition="after"
                data-testid="person-switcher">
                Playing as {meP.name}
              </Button>
            </MenuTrigger>
            <MenuPopover>
              <MenuList checkedValues={{ who: [me] }} onCheckedValueChange={(_, d) => switchPerson(d.checkedItems[0] as PersonId)}>
                {people.map((p) => (
                  <MenuItemRadio key={p.id} name="who" value={p.id} secondaryContent={p.role} data-testid="person-option" data-person-id={p.id}
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
            onClick={resetWorld} data-testid="reset-world">
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
              <div key={r.key} className={mergeClasses(s.railItem, r.key === view && s.railActive)} data-testid={`rail-${r.key}`}
                onClick={() => { if (r.key !== view) setNav((o) => ({ ...o, mtab: undefined, meeting: undefined, n: o.n + 1 })); setView(r.key); }}>
                {r.icon}
                <span>{r.label}</span>
              </div>
            ))}
          </nav>

          {view === "chat" && real && !ready && <div className={s.empty} style={{ flex: 1 }}>Loading…</div>}
          {view === "chat" && (!real || ready) && <ChatScreen me={me} initialChat={nav.chat ?? "max"} fresh={firstLoad && q.get("fresh") === "1"} demo={firstLoad ? q.get("demo") ?? undefined : undefined} dark={themeName !== "light"} onOpen={open}
            live={real ? world!.chats : undefined} key={real ? `${me}-${resetKey}` : me} />}
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
                    onClick={() => setChannelId(c.id)} data-testid="channel-item" data-channel-id={c.id}>
                    {c.name}
                    {c.locked && <LockClosed12Regular aria-label="Private channel" />}
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
                    {current.locked && <LockClosed12Regular />}
                    <div><Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>{current.team}</Text></div>
                  </div>
                  <TabList selectedValue={tab} onTabSelect={(_, d) => setTab(String(d.value))} style={{ marginLeft: "12px" }}>
                    <Tab value="posts">Posts</Tab>
                    <Tab value="files" data-testid="files-tab">Files</Tab>
                    <Tab value="plans">Plans</Tab>
                  </TabList>
                </div>
                {tab === "files" && (real
                  ? <ChannelFiles key={`${me}-${current.id}`} me={me} channel={current.id} reload={reloadKey} initialFile={firstLoad ? q.get("file") : undefined} />
                  : <FilesTab />)}
                {tab === "plans" && <PlansTab me={me} initialView={q.get("pview") ?? "list"} />}
                {tab === "posts" && <div className={s.feed} ref={feedRef} data-testid="feed"
                  onScroll={(e) => { const el = e.currentTarget; stickRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80; }}>
                  {shown.length === 0 && <div className={s.empty}>No posts yet in {current.name}.</div>}
                  {shown.map((t, i) => {
                    const day = t.post.at ? chatTime(t.post.at).day : null; // real mode only: Teams-like day dividers
                    const prev = i > 0 && shown[i - 1].post.at ? chatTime(shown[i - 1].post.at!).day : null;
                    return (
                      <Fragment key={t.id}>
                        {day && day !== prev && (
                          <div className={s.dayDivider} data-testid="day-divider"><span>{day}</span></div>
                        )}
                        <ThreadView t={t} me={me} onReply={addReply}
                          maxTyping={!!maxTyping && maxTyping.where === current.id && maxTyping.thread === t.id} />
                      </Fragment>
                    );
                  })}
                </div>}
                {tab === "posts" && (
                  <div className={s.compose}>
                    <div className={s.composeInner}>
                      <Textarea resize="vertical" style={{ flex: 1 }} value={newPost} data-testid="post-box"
                        placeholder={`Start a post in ${current.name} as ${meP.name} (type @Max to ask Max)`}
                        onChange={(_, d) => setNewPost(d.value)} />
                      <Button appearance="primary" icon={<Send20Regular />} onClick={addPost} data-testid="post-send">Post</Button>
                    </div>
                    {sendError && <Text size={200} block data-testid="send-error" style={{ color: tokens.colorPaletteRedForeground1, marginTop: 6 }}>{sendError}</Text>}
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
