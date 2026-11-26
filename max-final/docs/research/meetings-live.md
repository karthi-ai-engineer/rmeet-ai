# Research: following a live Teams meeting as text (26 Nov 2026)

Goal: Max answers "Max, ..." in the meeting chat within about 15 s, and gives late joiners
"what did I miss?". Text mode only. Voice comes later.
Anything we could not confirm is marked **(not verified)**.

## Answer first
1. **Graph transcripts are still after the meeting only.** No partial or live content (Microsoft Q&A, Apr 2026).
2. **There is now one official live-text route: Work IQ real-time transcripts.** It is brand new (admin switch dated
   14 Nov 2026). It needs a signed-in user, Teams transcription running, and pay-per-use Copilot Credits.
   How an app actually receives the live feed is **not documented publicly yet (not verified)**.
3. **Meeting chat works today:** with `ChatMessage.Read.Chat`, Max reads every chat message without @mention and can post replies. GA, Python.
4. **Own audio bot = C#/.NET on Windows Server in Azure.** There is still no Python or Linux option, and it is still "developer preview".
   Microsoft now says plainly that real-time media bots are **not recommended for AI agents**.
5. **Recall.ai-style guest bots work, but send meeting data to a third party.** Since mid-2026, Teams also detects them,
   holds them in the lobby by default, and admins can block them.

## Recommendation table

| Option | What it gives live | Needs | Effort | Risks |
|---|---|---|---|---|
| **A. Meeting chat (RSC)** | Every typed chat message. Max can reply in the chat. | `ChatMessage.Read.Chat` (+ send). Max added to the meeting. | Low (Python, GA) | No speech. "What did I miss?" only covers the chat. |
| **B. Work IQ real-time transcript** | Live spoken text with speaker names | Tenant Work IQ setup, Copilot Credits billing, "WorkIQ access" + "Allow AI in meetings" on, transcription running, a **user's** delegated token | Medium (REST/MCP, any language) | Very new; feed mechanism and latency not documented; per-use cost; needs a signed-in user; the organizer's org decides |
| **C. Graph transcript after the meeting** | Nothing live. Full transcript minutes after the end. | `OnlineMeetingTranscript.Read.Chat` (RSC) + admin "Microsoft Graph access" switch on | Low (Python, GA) | Delay (minutes, no SLA); transcription must have run |
| **D. Own media bot + own speech-to-text** | Live audio, speaker IDs per frame, can speak back later | C#/.NET, Windows Server VM in Azure, public IP per VM, `Calls.JoinGroupCall.All` + `Calls.AccessMedia.All` (admin) or RSC `.Chat` versions | High | Preview platform; SDK must be ≤3 months old; must call `updateRecordingStatus` first; Microsoft advises against for AI agents |
| **E. Third-party bot API (Recall.ai etc.)** | Live captions/transcript from a guest bot | Vendor account; organizer admits bot from the lobby | Low | **Meeting data leaves the company**; lobby/blocking by Teams policy; browser-scraping can break |

**R1 (text):** A + C now, plus B as the live source once we can test it in a real tenant (details at the end).
**Later (voice):** D, as a thin C# media gateway that streams audio to the Python Max. Not E.

---

## 1. Is there an official live transcript?

### Graph transcripts (`onlineMeeting/transcripts`, `callTranscript`)
- After the meeting only. A Microsoft answer (24 Apr 2026): "Fetching transcripts for an ongoing meeting is
  not currently supported. Transcripts are available only after the meeting ends." No partial content.
  A feedback idea asks to "Re-enable API to download transcriptions for ongoing meetings", so it existed once and was removed.
  [Q&A 5870080](https://learn.microsoft.com/en-au/answers/questions/5870080/microsoft-teams-graph-api-mid-meeting-transcript-p)
- `OnlineMeetingTranscript.Read.Chat` (RSC) works only for **scheduled private chat meetings**, not channel meetings.
  [Graph change notifications, updated 29 Jun 2026](https://learn.microsoft.com/en-us/graph/teams-changenotifications-callrecording-and-calltranscript)
- Admin switch: **"Microsoft Graph access" for transcripts is OFF by default.** Speaker names are a second switch, also off.
  [Manage transcript API access, 20 Oct 2026](https://learn.microsoft.com/en-us/microsoftteams/meeting-transcript-api-access)

### Work IQ real-time transcripts (new)
- Official text: "Work IQ lets agents and apps, including ones your organization builds, receive the transcript of a
  Teams meeting or call while it's in progress." Off by default. Takes effect **14 Nov 2026**.
  [Manage transcript API access, 20 Oct 2026](https://learn.microsoft.com/en-us/microsoftteams/meeting-transcript-api-access)
- An app gets the live transcript only when **all** of these are true:
  - "Allow AI in all meetings" is on, and "WorkIQ access" is on (`-EnableWorkIQTranscriptAccess $true`).
  - Transcription is already running. **Work IQ does not start transcription.**
  - The app acts **on behalf of a signed-in user** with the right Entra permissions.
  - Work IQ is enabled for the user's organization.
  - The **organizer's** organization's setting decides. Speaker names are included.
- Work IQ API facts: protocols A2A, MCP and REST. **Delegated auth only; app-only is not supported.** Paid per use with
  Copilot Credits. [Work IQ API overview, 3 Nov 2026](https://learn.microsoft.com/en-us/microsoft-365-copilot/extensibility/work-iq/api-overview),
  [Enable Work IQ, Jun 2026](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/work-iq/enable-work-iq)
- Tenant setup: create the Work IQ service principal once, plus a Copilot Studio usage billing plan tied to an Azure subscription.
- Status is unclear. Roadmap RM570651 "Work IQ: Real Time Transcripts": preview Sep 2026, GA Nov 2026, "In development"
  ([roadmap mirror](https://mc.merill.net/message/RM570651)). Another roadmap item reportedly says preview Dec 2026 and GA Jan 2027 **(not verified)**.
  Ignite blog (17 Nov 2026) says only "Teams real-time transcripts make meeting content available while the meeting is
  still happening." [Ignite 2026 Work IQ blog](https://techcommunity.microsoft.com/blog/microsoft_365blog/whats-new-in-work-iq-at-ignite-2026-agents-that-get-work-done/4572219)
- **Gaps (not verified):** the MCP tool reference (updated 20 Nov 2026) lists generic tools (`fetch`, `retrieve`, `ask`...)
  and nothing transcript-specific. We found no page on how the live feed is delivered (push or poll), its latency, or its exact cost.
  [MCP tool reference](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/work-iq/mcp/tool-reference)
- Licensing (community answer, 20 Nov 2026, **not official**): no Copilot seat needed. Custom apps pay Copilot Credits.
  Scope `api://workiq.svc.cloud.microsoft/WorkIQAgent.Ask`. MCP endpoint `https://workiq.svc.cloud.microsoft/mcp`.
  [Q&A 6077573](https://learn.microsoft.com/en-us/answers/questions/6077573/work-iq-api-access-through-the-remote-mcp-endpoint)
- A third-party guide says a tool call costs 0.1 credit (about $0.001) **(not verified)**.
  [aguidetocloud](https://www.aguidetocloud.com/blog/microsoft-work-iq-api-day-1-ga/)
- Design note: use Work IQ only as a **data source** (the transcript). Do not use its `ask` tool (Copilot reasoning).
  The model must stay swappable.

### Meeting events bots receive (GA, Teams SDK for Python)
- `meetingStart`, `meetingEnd`, `meetingParticipantJoin`, `meetingParticipantLeave`.
  Python handlers: `@app.on_meeting_start`, `@app.on_meeting_end`, `@app.on_meeting_participant_join`, `@app.on_meeting_participant_leave`.
- RSC: `OnlineMeeting.ReadBasic.Chat`, `ChannelMeeting.ReadBasic.Group`; participant events also need
  `OnlineMeetingParticipant.Read.Chat` and "Meeting Event Subscriptions" ticked in the Developer Portal.
  [Teams SDK Python meeting events](https://microsoft.github.io/teams-sdk/python/in-depth-guides/meeting-events),
  [Meeting apps APIs, updated 22 Oct 2026](https://learn.microsoft.com/en-us/microsoftteams/platform/apps-in-teams-meetings/meeting-apps-apis)
- Use: join/leave tells Max who is late, so it knows who needs "what did I miss?". Meeting start/end gives the real times.
- No live transcript or caption **read** API exists in the Teams SDK. "Send real-time captions" (CART) can only **write** captions.
- Python Teams SDK reached GA on 1 May 2026. [devblog](https://devblogs.microsoft.com/microsoft365dev/python-support-for-the-microsoft-teams-sdk-is-now-generally-available/)

### Copilot, Facilitator and "agentic users"
- Facilitator writes live AI notes, but it is Microsoft's own agent and needs a Copilot license. No third-party hook was found.
- "Agentic Users" (public preview, Ignite 2026) can be added to chats, channels and meetings under their own identity.
  Whether they get live transcripts **is not verified**. [UC Today, 25 Nov 2026](https://uctoday.com/microsoft-ignite-roundup-agents-got-names-the-dial-tone-got-skipped)

## 2. Own media bot (application-hosted media)
Source: [Requirements, updated 22 Jul 2026](https://learn.microsoft.com/en-us/microsoftteams/platform/bots/calls-and-meetings/requirements-considerations-application-hosted-media-bots),
[Real-time media concepts, updated 29 May 2026](https://learn.microsoft.com/en-us/microsoftteams/platform/bots/calls-and-meetings/real-time-media-concepts),
[Register calling bot, updated 3 Aug 2026](https://learn.microsoft.com/en-us/microsoftteams/platform/bots/calls-and-meetings/registering-calling-bot)

| Item | 2026 status |
|---|---|
| Language | C#/.NET only (`Microsoft.Graph.Communications.Calls.Media`). "C++ and Node.js APIs don't support access to real-time media." **No Python.** |
| OS / hosting | Production: Windows Server in Azure (Cloud Service, VMSS, IaaS VM, or AKS). Not an Azure Web App. On-prem Windows only for dev/test. |
| Network | Public IP per VM instance (ILPIP) plus a public port per instance. A call is pinned to one VM. |
| Size | Minimum 2 cores (4 vCPU for most VM types). |
| SDK freshness | Must be the newest version or at most 3 months old. Older versions stop working. |
| Status | "Developer preview". |
| Microsoft's advice | "Real-time Media bots are not recommended for AI agent scenarios." Microsoft points to Copilot Studio or Graph transcripts instead. |
| Audio | 16 kHz, 16-bit PCM, 50 frames of 20 ms per second. Active and dominant speaker IDs are given per frame. Up to 10 video streams. |
| Unmixed audio per speaker | Not described on these pages. The SDK is said to offer unmixed audio for a few dominant speakers **(not verified)**. |
| Permissions | App: `Calls.JoinGroupCall.All` (or `...asGuest.All`) + `Calls.AccessMedia.All`, admin consent. RSC versions: `Calls.JoinGroupCalls.Chat`, `Calls.AccessMedia.Chat`. |

- Rough effort: a separate C# service plus an Azure Windows VM running all the time, plus our own speech-to-text.
  A few weeks of specialist work, and constant SDK upgrades. VM cost depends on size **(not verified)**.
- The usual pattern: a thin C# "media gateway" that streams PCM to the Python bot over a WebSocket. This keeps Max in Python.

## 3. Meeting chat
- With the RSC permission `ChatMessage.Read.Chat`, Max receives **all user messages** in the group chats it is in, without @mention.
  A meeting chat is a chat. In the Developer Portal this sits under "Chat/Meeting permissions". The chat owner consents when Max is installed.
  [Receive all messages, updated 28 Oct 2026](https://learn.microsoft.com/en-us/microsoftteams/platform/agents-in-teams/enable-receive-all-chat-messages)
- Limits:
  - Messages written by **other bots** (including Workflows) are not delivered to Max (they can still be read through Graph).
  - It only adds messages in chats Max is already in. Max must be added to the meeting first.
  - The app description must say how Max uses chat data (Store rule).
- Posting: Max can reply in the meeting chat like in any chat (normal bot send). In-meeting notifications (small pop-ups) also exist.
  Throttling limits were not checked **(not verified)**.

## 4. When is the transcript ready after the meeting?
- Change notifications exist for "transcript available": per meeting
  (`communications/onlineMeetings/{id}/transcripts?useResourceSpecificConsentBasedAuthorization=true`, RSC OK) or
  for every meeting Max is installed in (`appCatalogs/teamsApps/{app-id}/installedToOnlineMeetings/getAllTranscripts`).
  [Graph change notifications](https://learn.microsoft.com/en-us/graph/teams-changenotifications-callrecording-and-calltranscript)
- Rules: the subscription must exist **before transcription starts**. It fails with 403 `GraphAccessToTranscriptsDisabled` if the admin switch is off.
  Subscriptions longer than 1 hour need a lifecycle URL. Private channel meetings are not supported.
- Delay: there is no SLA. Microsoft's own sample waits 30 s after `meetingEnd` and retries.
  Users report about 20 minutes, and an answer calls "5 to 30 minutes" common (anecdotal).
  [Q&A 5488376, Jul 2025](https://learn.microsoft.com/en-us/answers/questions/5488376/delay-in-getting-meeting-transcript-via-graph-api)
- Cost: Teams transcript APIs are no longer metered since 25 Aug 2025 ([MC1122144](https://mc.merill.net/message/MC1122144)).

## 5. What competitors do
- Otter, Fireflies and Read.ai join as a **visible meeting participant (bot)**. Most join as an external guest.
  Recall.ai's own tutorials describe a **browser bot** that joins as a guest, turns on captions and reads them from the page.
  [Recall.ai blog](https://www.recall.ai/blog/how-to-build-a-microsoft-teams-bot)
- Teams' response (2026): external bots are detected and **held in the lobby by default** (`RequireApprovalWhenDetected`).
  Admins can set `BlockDetectedBots`. Otter, Read AI and Recall.ai are in Microsoft's bot identification program.
  [Manage external bots, updated 24 Nov 2026](https://learn.microsoft.com/en-us/microsoftteams/manage-external-bots),
  [Office365ITPros, 24 Aug 2026](https://office365itpros.com/2026/08/24/teams-meeting-notetaking-bots/)
- Recall.ai: $0.50 per recording hour, plus $0.15 per hour for transcription. Regions are US, EU or APAC. No self-hosting.
  [Recall.ai pricing 2026](https://www.recall.ai/blog/new-recall-ai-pricing-for-2026) (vendor claims).
- **Flag:** with any meeting-bot API, audio and transcripts go to a third-party cloud. That is a hard sell for IT. It also clashes
  with "Max talks only through real Microsoft contracts".

## 6. Consent and the recording banner
- Media bot rule (official): you may not record **or keep data derived from** meeting media "without first calling the
  **updateRecordingStatus** API to indicate that recording has begun, and receiving a success reply". Live speech-to-text
  produces derived data, so Max must call it. Teams then shows the recording state to everyone.
  [updateRecordingStatus](https://learn.microsoft.com/en-us/graph/api/call-updaterecordingstatus?view=graph-rest-1.0)
- The same page says the API "requires the use of the Teams policy-based recording solution". Whether a normal (non-compliance)
  bot can call it without a recording policy **is not verified**. Test it before committing to option D.
- Options B and C use **Teams' own transcription**, so Teams shows its own "transcription started" banner and consent flow.
  Max starts nothing itself. Someone must start transcription, or the organizer turns on automatic transcription in meeting
  options **(not verified)**. An "explicit recording consent" meeting policy may also ask each person to agree **(not verified)**.
- Good product design either way: Max says in the chat that it is following the meeting, and stops when asked.

---

## Recommendation

**R1 (text mode):**
1. Build a provider-neutral **"live meeting feed"** inside Max (chat lines and transcript lines, each with speaker and time).
   `teams_sim` fakes this feed for development.
2. Real sources, in this order:
   - **A. Meeting chat (GA):** "Max, ..." questions typed in the chat, answered in the chat.
   - **B. Work IQ real-time transcript:** spoken content for "what did I miss?" and spoken questions. Turn it on only after a
     real-tenant test confirms: (a) how the feed is delivered, (b) latency well under 15 s, (c) cost per meeting.
   - **C. Graph transcript after the meeting:** final notes, and a fallback when B is off.
3. If B is off in a tenant, Max says so honestly: "I can only see the chat in this meeting."

**IT asks this adds** (all one-time switches, which fits "install once"): Work IQ service principal, Copilot Credits billing,
"WorkIQ access" + "Allow AI in meetings" + "Graph transcript access" switches, and transcription allowed in the meeting policy.
Max also needs one user to sign in (SSO) so it can read the transcript on their behalf.

**Later (voice):** option D. A small C# media gateway on an Azure Windows VM. It joins the meeting, calls `updateRecordingStatus`,
and streams audio to Python (speech-to-text in, Kokoro voice out). This is the only official way for Max to **speak**.
Re-check first: (1) has Microsoft shipped a simpler agent voice path, and (2) can a non-compliance bot call `updateRecordingStatus`?

**Not recommended:** E (Recall.ai etc.). Data leaves the company, guest bots get held in the lobby or blocked, and
caption scraping breaks easily.
