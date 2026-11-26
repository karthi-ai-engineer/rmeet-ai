// Mock data for the UI design mock-ups only. The real world comes from world/ through the fake Microsoft cloud.

export type PersonId = "karthi" | "prince" | "praga" | "rachitaa";

export interface Person {
  id: PersonId;
  name: string;
  role: string;
  color: "brand" | "dark-red" | "teal" | "magenta";
}

export const PEOPLE: Person[] = [
  { id: "prince", name: "Prince", role: "Product Planning · department lead", color: "brand" },
  { id: "praga", name: "Praga", role: "Procurement · parts buyer", color: "teal" },
  { id: "rachitaa", name: "Rachitaa", role: "Sales · account manager", color: "magenta" },
  { id: "karthi", name: "Karthi", role: "IT / AI · Max's developer", color: "dark-red" },
];

export interface Channel {
  id: string;
  name: string;
  privateFor?: PersonId[]; // private channel: only these people see it
}

export interface Team {
  id: string;
  name: string;
  members: PersonId[];
  channels: Channel[];
}

export const TEAMS: Team[] = [
  {
    id: "planning",
    name: "Product Planning",
    members: ["prince", "rachitaa", "karthi"],
    channels: [
      { id: "pp-general", name: "General" },
      { id: "pp-models", name: "New models" },
      { id: "pp-pricing", name: "Pricing" },
      { id: "pp-budget", name: "Budget", privateFor: ["prince", "karthi"] },
    ],
  },
  {
    id: "procurement",
    name: "Procurement",
    members: ["praga"],
    channels: [
      { id: "pr-general", name: "General" },
      { id: "pr-suppliers", name: "Suppliers" },
    ],
  },
  {
    id: "sales",
    name: "Sales",
    members: ["rachitaa"],
    channels: [
      { id: "sa-general", name: "General" },
      { id: "sa-accounts", name: "Big accounts" },
    ],
  },
];

export interface Source {
  n: number;
  title: string;
  where: string;
}

export interface Message {
  id: string;
  author: PersonId | "max" | string; // string = background person
  time: string;
  text: string;
  sources?: Source[];
  edited?: boolean;
}

export interface Thread {
  id: string;
  channelId: string;
  post: Message;
  replies: Message[];
}

export const BACKGROUND: Record<string, string> = { mei: "Lena (Finance)", omar: "Omar (Sales)" };

export const THREADS: Thread[] = [
  {
    id: "t1",
    channelId: "pp-pricing",
    post: {
      id: "m1",
      author: "prince",
      time: "Thu 20 Nov 14:32",
      text: "Decision from today's pricing review: all desktop models go up 5% from 1 Jan, because of the memory price rise. Rachitaa, please let the big accounts know before 5 Dec.",
    },
    replies: [
      { id: "m2", author: "rachitaa", time: "Thu 20 Nov 14:40", text: "Noted. Does that include the order we're quoting for Northwind (300 units)?" },
      { id: "m3", author: "prince", time: "Thu 20 Nov 14:52", text: "Quotes sent before 1 Dec keep the old price." },
    ],
  },
  {
    id: "t2",
    channelId: "pp-pricing",
    post: {
      id: "m4",
      author: "praga",
      time: "Mon 24 Nov 10:05",
      text: "New memory quotes are in the sheet (Parts prices.xlsx › Memory). 32 GB DDR5 is up again this month.",
    },
    replies: [
      { id: "m5", author: "rachitaa", time: "Wed 26 Nov 09:12", text: "@Max how much did the 32 GB memory price change since October, and what did we decide about prices?" },
      {
        id: "m6",
        author: "max",
        time: "Wed 26 Nov 09:12",
        text:
          "**32 GB DDR5: ¥14,200 → ¥16,900 (+19%)** from October to November [1].\n📌 **Decided on 20 Nov:** desktop prices go up 5% from 1 Jan; quotes sent before 1 Dec keep the old price [2].",
        sources: [
          { n: 1, title: "Parts prices.xlsx › Memory", where: "rows 4-5, Oct and Nov" },
          { n: 2, title: "Pricing thread, 20 Nov", where: "Prince, 14:32 and 14:52" },
        ],
      },
    ],
  },
];
