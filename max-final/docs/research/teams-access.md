# Research: getting Max into real Teams (25 Nov 2026)

Short version. Unverified items are marked **(?)**.

## Headline
- **Text features need only small asks from IT:** reading the channel, answering @Max, reading files, and notes from the transcript after a meeting. They can be limited to **one team**.
- **Live voice in meetings** still needs a **C#/.NET bot on a Windows server in Azure**. There is no Python option. That makes it a later phase.

## Developing without company admin rights

| Option | Cost | Real Teams? | Notes |
|---|---|---|---|
| M365 Developer Program E5 sandbox | Free | Yes (25 users) | Only for Visual Studio Pro/Enterprise subscribers, Microsoft partners, or Premier/Unified Support customers |
| Own tenant + Business Basic | About $7/user/month, so about $15-25/month for 2-3 users | Yes, you are admin | 30-day trial may exist **(?)** |
| Azure free account | Free | No (no Teams licenses) | Only for hosting (Azure Bot resource, VM) |
| Agents Playground (local) | Free | Fake only | No meetings, Graph or files. Our fake cloud already covers more than this. |

- The Agents Toolkit is deprecated for Teams. Use the **Teams SDK for Python** (generally available) and `teams app create`.
- A bot registered in our own tenant **can** be installed in the company tenant if custom app upload is allowed. Max must check the tenant ID on every message.
- Calling with a Teams-managed registration is unconfirmed **(?)**. Plan on an Azure Bot resource for meetings.

## What to ask IT for (smallest set)

| Ask | Why |
|---|---|
| A dedicated test team | Max lives there only |
| Custom app upload for Karthi (or IT uploads the app for a test group) | Install Max |
| Team-owner consent (RSC) turned on, can be limited to selected owners | Max gets permissions for **that team only** |
| "Graph API transcript access" switch on (new since July 2026) | Notes from transcripts |
| Transcription on in the meeting policy | Transcripts exist |
| **No `.All` (tenant-wide) permissions** | These would cover the whole company |

Team-scoped permissions (team owner consents): `ChannelMessage.Read.Group`, `ChannelMessage.Send.Group`, `File.Read.Group` (file content unclear **(?)**), `TeamMember.Read.Group`, `ChannelMeeting.ReadBasic.Group`.
Meeting-scoped permissions: `OnlineMeetingTranscript.Read.Chat`, `OnlineMeeting.ReadBasic.Chat`, `ChatMessage.Read.Chat`, `Calls.JoinGroupCalls.Chat` and `Calls.AccessMedia.Chat` (might avoid a tenant admin **(?)**).
Transcript note: there is no team-scoped transcript permission for **channel** meetings. For the demo, use a normal scheduled meeting with Max added.

## Live meetings
- Real-time audio: C#/.NET, Windows Server VM in Azure, public IP, still "developer preview".
- Work IQ Real-Time Transcripts: live text for apps, read-only. Preview around Dec 2026, general availability around Jan 2027 **(?)**. Licensing unknown.
- Meeting AI Insights: after the meeting only, needs a Copilot license.
- Plan for later: Python brain plus a small C# audio bridge (per-speaker audio unconfirmed **(?)**).

## Recommended path
1. **Now:** fake cloud for daily work, plus our own small tenant (or the E5 sandbox if we qualify) for real-Teams tests.
2. **First company demo:** text features in one test team, with the smallest IT asks above.
3. **Later:** live voice through the C# bridge, after IT reviews the calling permissions.

Sources: learn.microsoft.com (RSC list, agent registration and tenancy, Agents Playground, media bot requirements, Developer Program FAQ); Message Center items MC1393806, RM572674, RM570651, MC1087634.
