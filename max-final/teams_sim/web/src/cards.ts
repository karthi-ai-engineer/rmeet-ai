// Adaptive Card JSON for Max's cards (content agreed in docs/plans/09-cards.md) + a Teams-like host config.
// The host config approximates Teams' look; replace it with Microsoft's official Teams host config when the real
// simulator is built (Adaptive Cards Designer → host app "Microsoft Teams").

type Json = Record<string, unknown>;

export function teamsHostConfig(dark: boolean): Json {
  const fg = dark ? "#FFFFFF" : "#242424";
  const sub = dark ? "#ADADAD" : "#616161";
  const style = (bg: string) => ({
    backgroundColor: bg,
    foregroundColors: {
      default: { default: fg, subtle: sub },
      accent: { default: dark ? "#A6A7DC" : "#5B5FC7", subtle: dark ? "#A6A7DC" : "#5B5FC7" },
      good: { default: dark ? "#92C353" : "#107C10", subtle: dark ? "#92C353" : "#107C10" },
      warning: { default: dark ? "#F8D22A" : "#8A6100", subtle: dark ? "#F8D22A" : "#8A6100" },
      attention: { default: dark ? "#E37D80" : "#C4314B", subtle: dark ? "#E37D80" : "#C4314B" },
      dark: { default: fg, subtle: sub },
      light: { default: fg, subtle: sub },
    },
  });
  return {
    fontFamily: "'Segoe UI', 'Segoe UI Web (West European)', -apple-system, sans-serif",
    supportsInteractivity: true,
    spacing: { small: 4, default: 8, medium: 16, large: 20, extraLarge: 24, padding: 16 },
    separator: { lineThickness: 1, lineColor: dark ? "#3D3D3D" : "#E0E0E0" },
    fontSizes: { small: 12, default: 14, medium: 16, large: 18, extraLarge: 24 },
    fontWeights: { lighter: 300, default: 400, bolder: 600 },
    containerStyles: {
      default: style(dark ? "#292929" : "#FFFFFF"),
      emphasis: style(dark ? "#1F1F1F" : "#F5F5F5"),
      accent: style(dark ? "#2F2F4A" : "#E8EBFA"),
      good: style(dark ? "#1E3A1E" : "#F1FAF1"),
      attention: style(dark ? "#3F1F23" : "#FDF3F4"),
      warning: style(dark ? "#3D3418" : "#FFF9E6"),
    },
    actions: { maxActions: 4, spacing: "default", buttonSpacing: 8, showCard: { actionMode: "inline", inlineTopMargin: 12 }, actionsOrientation: "horizontal", actionAlignment: "left" },
    adaptiveCard: { allowCustomStyle: true },
    factSet: { title: { color: "default", size: "default", isSubtle: true, weight: "default", wrap: true, maxWidth: 130 }, value: { color: "default", size: "default", wrap: true }, spacing: 8 },
    textBlock: { headingLevel: 2 },
  };
}

const card = (body: Json[], actions?: Json[]): Json => ({
  type: "AdaptiveCard", $schema: "http://adaptivecards.io/schemas/adaptive-card.json", version: "1.5", body, ...(actions ? { actions } : {}),
});
const title = (text: string): Json => ({ type: "TextBlock", text, weight: "Bolder", size: "Medium", wrap: true });
const textB = (text: string, extra: Json = {}): Json => ({ type: "TextBlock", text, wrap: true, ...extra });
const small = (text: string): Json => ({ type: "TextBlock", text, isSubtle: true, size: "Small", wrap: true, spacing: "Small" });
const exec = (title: string, verb: string, primary = false): Json => ({ type: "Action.Execute", title, verb, ...(primary ? { style: "positive" } : {}) });
const facts = (pairs: [string, string][]): Json => ({ type: "FactSet", facts: pairs.map(([t, v]) => ({ title: t, value: v })) });

export interface CardDemo {
  id: string;
  name: string;
  where: string; // where it appears + who sees the buttons
  before: Json;
  after?: Json;
  afterLabel?: string;
}

export const CARDS: CardDemo[] = [
  {
    id: "working", name: "Working on it + Stop", where: "In the thread, for tasks longer than ~5 s · Stop: the asker or the team lead",
    before: card([textB("Working on it: reading 12 threads…"), small("Step 3 of about 8")], [exec("Stop", "stop")]),
    after: card([textB("Stopped by Prince at 10:42."), small("Nothing was posted or sent. Ask again any time.")]), afterLabel: "After Stop",
  },
  {
    id: "email", name: "Approval: send an email", where: "Private chat with the person who asked · only they see the buttons",
    before: card([
      title("⚠️ Send this email?"), small("Rachitaa asked me to email Prince."),
      facts([["To", "Prince"], ["Subject", "Q1 pricing summary for big accounts"]]),
      { type: "Container", style: "emphasis", spacing: "Medium", items: [
        textB("Hi Prince, here is the summary you asked for:\n- Desktop prices go up **5% from 1 Jan** (decided 20 Nov) [1]\n- Quotes sent **before 1 Dec** keep the old price [1]\n- 32 GB DDR5 rose **19%** from October to November [2]", { size: "Small" }),
      ] },
      small("Only Rachitaa can approve · expires in 24 h · sources [1] [2]"),
    ], [exec("Approve and send", "approve", true), { type: "Action.ShowCard", title: "Edit", card: card([
      { type: "Input.Text", id: "subject", label: "Subject", value: "Q1 pricing summary for big accounts" },
      { type: "Input.Text", id: "body", label: "Message", isMultiline: true, value: "Hi Prince, here is the summary you asked for: …" },
    ], [exec("Approve and send", "approveEdited", true)]) }, exec("Deny", "deny")]),
    after: card([title("✅ Email sent"), facts([["To", "Prince"], ["Subject", "Q1 pricing summary for big accounts"]]), small("Approved by Rachitaa, 10:42 · sent from Max's mailbox")], [{ type: "Action.OpenUrl", title: "View email", url: "https://example.invalid/mail" }]),
    afterLabel: "After Approve",
  },
  {
    id: "meeting", name: "Approval: book a meeting", where: "Where it was asked · only the asker sees the buttons",
    before: card([
      title("📅 Book this meeting?"),
      facts([["Who", "Prince, Praga"], ["When", "Tue 2 Dec, 14:00–14:30 JST"], ["Topic", "Price list"], ["Agenda", "Late items, new due date"]]),
      small("Both are free then · Teams meeting link added · expires in 24 h"),
    ], [exec("Book it", "book", true), exec("Other time", "other"), exec("Deny", "deny")]),
    after: card([title("✅ Meeting booked"), facts([["When", "Tue 2 Dec, 14:00–14:30 JST"], ["Who", "Prince, Praga"]]), small("Booked after Prince's OK, 10:44 · invite sent to Praga")]),
    afterLabel: "After Book it",
  },
  {
    id: "continue", name: "Continue?", where: "In the thread · only the asker sees the buttons",
    before: card([
      title("⚠️ This is bigger than expected"),
      textB("Done so far: read 40 of 95 supplier threads (summary below)."),
      textB("To finish: about 10 more steps, ~2 min, ~$0.02."),
      small("Only Praga can choose · expires in 24 h"),
    ], [exec("Continue", "continue", true), exec("Stop here, post what you have", "stopHere")]),
    after: card([textB("Continued by Praga, 10:47. Working on it…")], [exec("Stop", "stop")]), afterLabel: "After Continue",
  },
  {
    id: "plan", name: "Living plan card", where: "Channel · one card per plan, updated in place · each owner sees buttons only on their own items (this is Praga's view)",
    before: card([
      title("📅 New model launch · launch Wed 15 Jan"),
      small("6 of 9 done · 1 late · owner Prince"),
      { type: "Container", spacing: "Medium", separator: true, items: [
        { type: "ColumnSet", columns: [
          { type: "Column", width: "stretch", items: [textB("⚠️ **Price list** · Praga · was due Mon 24 Nov", { color: "Attention" })] },
        ] },
        { type: "ActionSet", actions: [exec("Done", "done", true), exec("New date", "newDate"), { type: "Action.ShowCard", title: "Blocked", card: card([
          { type: "Input.Text", id: "reason", label: "What's blocking it?", placeholder: "e.g. waiting for supplier costs" },
        ], [exec("Send to Prince", "blocked", true)]) }] },
        textB("• Supplier report · Praga · due Mon 1 Dec", { spacing: "Medium" }),
        textB("• Launch post · Rachitaa · due Fri 12 Dec"),
        small("+ 6 more done"),
      ] },
      small("Updated 10:55 (Praga accepted the price list)"),
    ], [{ type: "Action.OpenUrl", title: "Open plans tab", url: "https://example.invalid/plans" }]),
    after: card([
      title("📅 New model launch · launch Wed 15 Jan"), small("7 of 9 done · on track · owner Prince"),
      { type: "Container", spacing: "Medium", separator: true, items: [
        textB("✅ Price list · Praga · done 27 Nov", { isSubtle: true }),
        textB("• Supplier report · Praga · due Mon 1 Dec"), textB("• Launch post · Rachitaa · due Fri 12 Dec"), small("+ 7 more done"),
      ] },
      small("Updated 11:20 (Praga marked the price list done)"),
    ]),
    afterLabel: "After Done",
  },
  {
    id: "chase", name: "Chase", where: "Private chat with the task owner · kind, no blame · max 1 per task per day",
    before: card([
      textB("⏰ Hi Praga, the **price list** you own was due **Mon 24 Nov** (new model launch) [1]."),
      small("You get this because you own the task · Stop these"),
    ], [exec("Done", "done", true), exec("New date", "newDate"), exec("Blocked", "blocked"), exec("Stop these", "stopThese")]),
    after: card([textB("✅ Marked done. The plan is updated."), small("Praga, 11:20")]), afterLabel: "After Done",
  },
  {
    id: "brief", name: "Meeting brief + live countdown", where: "Meeting chat, 15 min before · updated every minute",
    before: card([
      { type: "ColumnSet", columns: [
        { type: "Column", width: "stretch", items: [title("📅 New model check-in · 10:00 JST")] },
        { type: "Column", width: "auto", verticalContentAlignment: "Center", items: [
          { type: "Container", style: "accent", bleed: false, items: [textB("Starts in **12 min**", { size: "Small" })] },
        ] },
      ] },
      small("Prince, Praga, Rachitaa, Karthi"),
      { type: "Container", spacing: "Medium", separator: true, items: [
        textB("**Open from last time**", { size: "Small" }),
        textB("⚠️ Price list (Praga) is 2 days late [1]", { size: "Small", spacing: "Small" }),
        textB("⚠️ GPU supplier decision is blocked [1]", { size: "Small", spacing: "None" }),
        textB("✅ Stock plan done [1]", { size: "Small", spacing: "None" }),
        textB("**Related:** New model launch plan [1] · Stock forecast.xlsx [2]", { size: "Small" }),
      ] },
    ], [{ type: "Action.OpenUrl", title: "Join meeting", url: "https://example.invalid/join" }]),
  },
  {
    id: "memory", name: "\"What do you know about me?\"", where: "Private chat · anyone, about themselves",
    before: card([
      title("What I remember about you, Praga"), small("Work only. Each line shows where I learned it."),
      { type: "Container", spacing: "Medium", separator: true, items: [
        textB("Handles memory and GPU suppliers · since 3 Nov [1]"),
        { type: "ActionSet", actions: [{ type: "Action.ShowCard", title: "Correct", card: card([{ type: "Input.Text", id: "fact", label: "What's right?", value: "Handles memory and GPU suppliers" }], [exec("Save", "correct", true)]) }, exec("Delete", "delete")] },
        textB("Prefers summaries as bullet points · 12 Nov [2]", { spacing: "Medium" }),
        { type: "ActionSet", actions: [{ type: "Action.ShowCard", title: "Correct", card: card([{ type: "Input.Text", id: "fact2", label: "What's right?", value: "Prefers summaries as bullet points" }], [exec("Save", "correct", true)]) }, exec("Delete", "delete")] },
      ] },
      small("Only you can see this"),
    ]),
  },
  {
    id: "lesson", name: "New lesson to accept", where: "Private chat with the team lead",
    before: card([
      title("📌 New lesson from Praga"),
      { type: "Container", style: "emphasis", items: [textB("\"For memory prices, use the Parts prices sheet, not the slides.\"")] },
      small("From a 👎 on an answer, Tue 25 Nov [1] · active lessons: 7"),
    ], [exec("Accept", "accept", true), exec("Edit", "edit"), exec("Reject", "reject")]),
    after: card([title("✅ Lesson active"), small("Accepted by Prince, 14:05 · used in future answers · Praga was told their feedback was used")]),
    afterLabel: "After Accept",
  },
  {
    id: "alert", name: "Alert", where: "Private chat with the team lead and the developer · only when something needs attention",
    before: card([
      { type: "Container", style: "warning", items: [title("⚠️ #Pricing is 3 hours behind")] },
      textB("Teams stopped sending updates for #Pricing at 05:10. I'm catching up now."),
      small("Until then, answers there may miss the last 3 hours, and I say so when it matters."),
    ], [{ type: "Action.OpenUrl", title: "Open health view", url: "https://example.invalid/health" }]),
    after: card([title("✅ #Pricing is up to date again"), small("Caught up at 08:22 · 46 messages added · nothing lost")]), afterLabel: "When fixed",
  },
  {
    id: "limit", name: "A limit was reached", where: "Private chat with the team lead",
    before: card([
      title("⚠️ Daily AI budget reached ($1.00)"),
      textB("New questions get a short \"paused\" note until 00:00 JST."),
      small("Today: 142 answers · 3 summaries · 2 long tasks · all limits are settings"),
    ], [exec("Raise today's limit", "raise", true), { type: "Action.OpenUrl", title: "Open settings", url: "https://example.invalid/setup" }]),
  },
];
