// UI design mock-up: Calendar (work week) + meeting details with Max's brief. Static data.
import { useState } from "react";
import {
  Avatar,
  Badge,
  Button,
  Divider,
  Text,
  makeStyles,
  mergeClasses,
  tokens,
} from "@fluentui/react-components";
import {
  Add20Regular,
  CalendarToday20Regular,
  ChevronLeft20Regular,
  ChevronRight20Regular,
  Dismiss20Regular,
  Video20Filled,
} from "@fluentui/react-icons";
import { PEOPLE, type PersonId } from "./mock";
import { MAX_ORANGE, MaxAvatar, RichText, Sources, personName } from "./ui";

interface Meeting {
  id: string;
  title: string;
  day: number; // 0 = Mon 24 Nov … 4 = Fri 28 Nov
  start: number; // hours, e.g. 10.5 = 10:30
  end: number;
  people: PersonId[];
  organizer: PersonId;
  agenda: string[];
  bookedByMax?: boolean;
  brief?: { text: string; sources: { n: number; title: string; where: string }[] };
}

const DAYS = ["Mon 24", "Tue 25", "Wed 26", "Thu 27", "Fri 28"];
const TODAY = 2; // Wed 26 Nov
const NOW = 11.25; // 11:15
const START_H = 8;
const END_H = 19;
const HOUR_PX = 60;

const MEETINGS: Meeting[] = [
  { id: "m1", title: "Pricing weekly", day: 0, start: 10, end: 11, people: ["prince", "rachitaa", "karthi"], organizer: "prince", agenda: ["Memory prices", "Big account quotes"] },
  { id: "m2", title: "Supplier call: GPU", day: 1, start: 14, end: 15, people: ["praga", "prince"], organizer: "praga", agenda: ["Supplier B delivery date", "Volume discount"] },
  { id: "m3", title: "1:1 Prince / Praga", day: 2, start: 14.5, end: 15, people: ["prince", "praga"], organizer: "prince", agenda: ["Price list status"], bookedByMax: true },
  { id: "m4", title: "Northwind quote review", day: 2, start: 16, end: 16.5, people: ["rachitaa", "prince"], organizer: "rachitaa", agenda: ["Old vs new price", "Delivery date"] },
  {
    id: "m5", title: "New model check-in", day: 4, start: 10, end: 11, people: ["prince", "praga", "rachitaa", "karthi"], organizer: "prince",
    agenda: ["Launch date", "GPU supplier decision", "Price list"],
    brief: {
      text: "Open from last time:\n⚠️ Price list (Praga) is 2 days late [1]\n⚠️ GPU supplier decision is blocked: waiting for Supplier B's date [1]\n✅ Stock plan done [1]\n📌 Launch date is **Wed 15 Jan** (moved from 8 Jan) [2]",
      sources: [
        { n: 1, title: "New model launch plan", where: "Product Planning › Plans" },
        { n: 2, title: "New models thread, 18 Nov", where: "Prince, 11:05" },
      ],
    },
  },
  { id: "m6", title: "IT: Max status", day: 3, start: 9, end: 9.5, people: ["karthi", "prince"], organizer: "karthi", agenda: ["Health view", "Costs this week"] },
  { id: "m7", title: "Sales team sync", day: 3, start: 11, end: 12, people: ["rachitaa"], organizer: "rachitaa", agenda: ["Pipeline"] },
];

const fmt = (h: number) => `${String(Math.floor(h)).padStart(2, "0")}:${h % 1 ? "30" : "00"}`;
const DAY_NAMES = ["Mon 24 Nov", "Tue 25 Nov", "Wed 26 Nov", "Thu 27 Nov", "Fri 28 Nov"];

const useStyles = makeStyles({
  wrap: { flex: 1, display: "flex", minWidth: 0, minHeight: 0, backgroundColor: tokens.colorNeutralBackground1 },
  main: { flex: 1, display: "flex", flexDirection: "column", minWidth: 0 },
  top: { display: "flex", alignItems: "center", gap: "8px", padding: "10px 16px", borderBottom: `1px solid ${tokens.colorNeutralStroke2}` },
  title: { fontSize: tokens.fontSizeBase500, fontWeight: tokens.fontWeightBold, marginRight: "12px" },
  head: { display: "flex", paddingLeft: "56px", borderBottom: `1px solid ${tokens.colorNeutralStroke2}` },
  dayHead: { flex: 1, padding: "8px 10px", fontSize: tokens.fontSizeBase300, color: tokens.colorNeutralForeground2 },
  dayToday: { color: tokens.colorBrandForeground1, fontWeight: tokens.fontWeightBold },
  grid: { flex: 1, overflowY: "auto", display: "flex", position: "relative" },
  hours: { width: "56px", flexShrink: 0 },
  hour: { height: `${HOUR_PX}px`, fontSize: tokens.fontSizeBase100, color: tokens.colorNeutralForeground3, textAlign: "right", paddingRight: "8px", transform: "translateY(-6px)" },
  col: { flex: 1, position: "relative", borderLeft: `1px solid ${tokens.colorNeutralStroke3}` },
  colToday: { backgroundColor: tokens.colorNeutralBackground2 },
  line: { height: `${HOUR_PX}px`, borderTop: `1px solid ${tokens.colorNeutralStroke3}` },
  event: {
    position: "absolute", left: "4px", right: "6px", padding: "4px 8px", overflow: "hidden", cursor: "pointer",
    borderRadius: tokens.borderRadiusMedium, borderLeft: `4px solid ${tokens.colorBrandStroke1}`,
    backgroundColor: tokens.colorBrandBackground2, color: tokens.colorNeutralForeground1, fontSize: tokens.fontSizeBase200,
    ":hover": { boxShadow: tokens.shadow4 },
  },
  eventActive: { backgroundColor: tokens.colorBrandBackground, color: tokens.colorNeutralForegroundOnBrand, borderLeftColor: tokens.colorBrandStroke1 },
  eventMax: { borderLeftColor: MAX_ORANGE },
  now: { position: "absolute", left: 0, right: 0, height: "2px", backgroundColor: tokens.colorPaletteRedBackground3, zIndex: 2 },
  nowDot: { position: "absolute", left: "-5px", top: "-4px", width: "10px", height: "10px", borderRadius: "50%", backgroundColor: tokens.colorPaletteRedBackground3 },
  // details panel
  panel: { width: "420px", flexShrink: 0, overflowY: "auto", borderLeft: `1px solid ${tokens.colorNeutralStroke2}`, backgroundColor: tokens.colorNeutralBackground1 },
  pHead: { display: "flex", alignItems: "flex-start", gap: "8px", padding: "16px 12px 8px 20px" },
  pBody: { padding: "0 20px 20px", display: "flex", flexDirection: "column", gap: "14px" },
  label: { fontSize: tokens.fontSizeBase200, color: tokens.colorNeutralForeground3, fontWeight: tokens.fontWeightSemibold, marginBottom: "4px" },
  person: { display: "flex", alignItems: "center", gap: "8px", padding: "3px 0" },
  brief: {
    borderRadius: tokens.borderRadiusLarge, padding: "12px 14px", backgroundColor: tokens.colorNeutralBackground2,
    borderLeft: `3px solid ${MAX_ORANGE}`,
  },
  countdown: {
    display: "inline-flex", alignItems: "baseline", gap: "6px", padding: "6px 12px", borderRadius: tokens.borderRadiusCircular,
    backgroundColor: tokens.colorNeutralBackground3, fontWeight: tokens.fontWeightSemibold,
  },
});

export function CalendarScreen({ me, initialMeeting }: { me: PersonId; initialMeeting?: string }) {
  const s = useStyles();
  const mine = MEETINGS.filter((m) => m.people.includes(me));
  const [openId, setOpenId] = useState<string | null>(initialMeeting && mine.some((m) => m.id === initialMeeting) ? initialMeeting : null);
  const open = mine.find((m) => m.id === openId);
  const hours = Array.from({ length: END_H - START_H }, (_, i) => START_H + i);
  const top = (h: number) => (h - START_H) * HOUR_PX;

  return (
    <div className={s.wrap}>
      <div className={s.main}>
        <div className={s.top}>
          <span className={s.title}>Calendar</span>
          <Button icon={<CalendarToday20Regular />}>Today</Button>
          <Button appearance="subtle" icon={<ChevronLeft20Regular />} aria-label="Previous week" />
          <Button appearance="subtle" icon={<ChevronRight20Regular />} aria-label="Next week" />
          <Text weight="semibold">24 – 28 November 2026</Text>
          <div style={{ flex: 1 }} />
          <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>Work week · JST</Text>
          <Button appearance="primary" icon={<Add20Regular />}>New meeting</Button>
        </div>
        <div className={s.head}>
          {DAYS.map((d, i) => <div key={d} className={mergeClasses(s.dayHead, i === TODAY && s.dayToday)}>{d}{i === TODAY ? " · Today" : ""}</div>)}
        </div>
        <div className={s.grid}>
          <div className={s.hours}>{hours.map((h) => <div key={h} className={s.hour}>{h > START_H ? fmt(h) : ""}</div>)}</div>
          {DAYS.map((d, i) => (
            <div key={d} className={mergeClasses(s.col, i === TODAY && s.colToday)}>
              {hours.map((h) => <div key={h} className={s.line} />)}
              {i === TODAY && <div className={s.now} style={{ top: top(NOW) }}><span className={s.nowDot} /></div>}
              {mine.filter((m) => m.day === i).map((m) => (
                <div key={m.id}
                  className={mergeClasses(s.event, m.bookedByMax && s.eventMax, m.id === openId && s.eventActive)}
                  style={{ top: top(m.start) + 1, height: (m.end - m.start) * HOUR_PX - 3 }}
                  onClick={() => setOpenId(m.id)}>
                  <div style={{ fontWeight: 600, display: "flex", alignItems: "center", gap: 6 }}>
                    <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{m.title}</span>
                    {m.brief && <span title="Max's brief is ready" style={{ background: MAX_ORANGE, color: "#fff", borderRadius: 8, padding: "0 6px", fontSize: 10, fontWeight: 600 }}>Brief</span>}
                  </div>
                  {m.end - m.start >= 1 && <div>{fmt(m.start)} – {fmt(m.end)} · {personName(m.organizer)}</div>}
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>

      {open && (
        <aside className={s.panel}>
          <div className={s.pHead}>
            <div style={{ flex: 1 }}>
              <Text size={500} weight="bold" block>{open.title}</Text>
              <Text size={300} style={{ color: tokens.colorNeutralForeground2 }}>
                {DAY_NAMES[open.day]} · {fmt(open.start)} – {fmt(open.end)} JST
              </Text>
            </div>
            <Button appearance="subtle" icon={<Dismiss20Regular />} onClick={() => setOpenId(null)} aria-label="Close" />
          </div>
          <div className={s.pBody}>
            <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
              <Button appearance="primary" icon={<Video20Filled />}>Join</Button>
              {open.day > TODAY || (open.day === TODAY && open.start > NOW) ? (
                <span className={s.countdown}>Starts in {open.day === TODAY ? `${Math.round((open.start - NOW) * 60)} min` : `${open.day - TODAY} days`}</span>
              ) : null}
            </div>
            {open.bookedByMax && (
              <Badge appearance="tint" color="warning" icon={<MaxAvatar size={14} />}>Booked by Max for {personName(open.organizer)} (approved)</Badge>
            )}
            {open.brief && (
              <div className={s.brief}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
                  <MaxAvatar size={20} />
                  <Text weight="semibold" style={{ color: MAX_ORANGE }}>Max's brief</Text>
                  <Badge appearance="tint" color="informative" size="small">AI generated</Badge>
                </div>
                <RichText text={open.brief.text} />
                <Sources sources={open.brief.sources} />
                <Text size={100} style={{ color: tokens.colorNeutralForeground3, display: "block", marginTop: 6 }}>
                  Also posted in the meeting chat 15 min before, with a live countdown.
                </Text>
              </div>
            )}
            <div>
              <div className={s.label}>Agenda</div>
              {open.agenda.map((a, i) => <Text key={a} block>{i + 1}. {a}</Text>)}
            </div>
            <Divider />
            <div>
              <div className={s.label}>People · {open.people.length}</div>
              {open.people.map((p) => {
                const person = PEOPLE.find((x) => x.id === p);
                return (
                  <div key={p} className={s.person}>
                    <Avatar size={28} name={personName(p)} color={person?.color} />
                    <Text style={{ flex: 1 }}>{personName(p)}</Text>
                    <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>{p === open.organizer ? "Organizer" : "Accepted"}</Text>
                  </div>
                );
              })}
            </div>
          </div>
        </aside>
      )}
    </div>
  );
}
