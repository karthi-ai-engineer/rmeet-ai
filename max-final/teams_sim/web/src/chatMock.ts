// Mock chats for the Chat screen design (static; the real ones come from the world + live play).
import type { PersonId, Source } from "./mock";

export interface ChatMessage {
  id: string;
  author: PersonId | "max";
  time: string; // shown time
  day: string; // divider label
  text: string;
  sources?: Source[];
  quote?: { author: string; text: string }; // quote-reply
  reactions?: { emoji: string; count: number }[];
  buttons?: string[]; // quick buttons under a Max message (cards are designed later)
  followUps?: string[]; // tappable suggested next questions (Teams suggested actions)
  card?: { before: object; after?: object; done?: boolean; afterText?: string; retry?: string }; // an Adaptive Card attached to the message
  botReaction?: string; // a reaction Max put on this message (status for long tasks: ⏳ while working, ✅ when done)
  system?: boolean; // Max's own notices (welcome, done, errors): no "AI generated" label, no 👍/👎
}

export interface Chat {
  id: string;
  kind: "max" | "group" | "oneToOne";
  title?: string; // group name
  members: PersonId[]; // people (Max is implied for kind "max")
  messages: ChatMessage[];
}

/** Every person has a 1:1 chat with Max; its content is written for that person. */
export function maxChatFor(me: PersonId): Chat {
  const first: Record<PersonId, string> = { prince: "Prince", praga: "Praga", rachitaa: "Rachitaa", karthi: "Karthi" };
  return {
    id: "max",
    kind: "max",
    members: [me],
    messages: [
      {
        id: "x1", author: "max", day: "Yesterday", time: "09:00",
        text: `👋 Morning ${first[me]}, 2 things today:\n⏰ Supplier report due **today**\n📅 1:1 with ${me === "prince" ? "Praga" : "Prince"} at **14:00 JST**`,
      },
      { id: "x2", author: me, day: "Today", time: "08:41", text: "What's on my plate this week?" },
      {
        id: "x3", author: "max", day: "Today", time: "08:41",
        text:
          "**3 open items this week:**\n⚠️ Price list (new model launch) was due **Mon 24 Nov** [1]\n⏰ Supplier report due **Mon 1 Dec** [1]\n📅 New model check-in **Fri 28 Nov, 10:00 JST** [2]",
        sources: [
          { n: 1, title: "Launch plan", where: "Product Planning › Plans" },
          { n: 2, title: "Calendar", where: "New model check-in" },
        ],
      },
      { id: "x4", author: me, day: "Today", time: "08:43", text: "and who's waiting on the price list?" },
      {
        id: "x5", author: "max", day: "Today", time: "08:43",
        text: "**Rachitaa** is: she needs it for the Northwind quote (300 units), which must go out before **1 Dec** to keep the old price [1].",
        sources: [{ n: 1, title: "Pricing thread, 20 Nov", where: "Prince, 14:52" }],
        followUps: ["Remind me about the price list tomorrow", "Ask Praga for a new date", "What else is late?"],
      },
    ],
  };
}

export const CHATS: Chat[] = [
  {
    id: "sync",
    kind: "group",
    title: "New model sync",
    members: ["prince", "praga", "rachitaa"],
    messages: [
      { id: "g1", author: "praga", day: "Yesterday", time: "16:10", text: "GPU quotes from both suppliers are in. Supplier B is 6% cheaper but ships 2 weeks later." },
      { id: "g2", author: "prince", day: "Yesterday", time: "16:14", text: "2 weeks later breaks the launch date. Let's discuss tomorrow.", reactions: [{ emoji: "👍", count: 2 }] },
      { id: "g3", author: "rachitaa", day: "Today", time: "09:20", text: "@Max what's the current launch date for the new model?" },
      {
        id: "g4", author: "max", day: "Today", time: "09:20",
        text: "📅 **Wed 15 Jan** (moved from 8 Jan on 18 Nov) [1]. Supplier B's later delivery would push it past that [2].",
        sources: [
          { n: 1, title: "New models thread, 18 Nov", where: "Prince, 11:05" },
          { n: 2, title: "This chat", where: "Praga, yesterday 16:10" },
        ],
      },
      { id: "g5", author: "rachitaa", day: "Today", time: "09:21", text: "and does Northwind know?" },
      {
        id: "g6", author: "max", day: "Today", time: "09:21",
        text: "🔍 I couldn't find any message telling Northwind about the new date. The last update to them was on 12 Nov, still saying 8 Jan [1].",
        sources: [{ n: 1, title: "Sales › Big accounts", where: "Rachitaa, 12 Nov" }],
      },
      {
        id: "g7", author: "prince", day: "Today", time: "09:25", text: "Rachitaa, can you send them the update today?",
        quote: { author: "Max", text: "I couldn't find any message telling Northwind about the new date…" },
      },
    ],
  },
  {
    id: "prince-rachitaa",
    kind: "oneToOne",
    members: ["prince", "rachitaa"],
    messages: [
      { id: "o1", author: "prince", day: "Today", time: "09:30", text: "Thanks for picking up the Northwind update." },
      { id: "o2", author: "rachitaa", day: "Today", time: "09:31", text: "Sure, sending it before lunch 🙂" },
    ],
  },
  {
    id: "prince-praga",
    kind: "oneToOne",
    members: ["prince", "praga"],
    messages: [
      { id: "p1", author: "praga", day: "Yesterday", time: "17:02", text: "Can we move our 1:1 to 14:30?" },
      { id: "p2", author: "prince", day: "Yesterday", time: "17:05", text: "Works for me." },
    ],
  },
];
