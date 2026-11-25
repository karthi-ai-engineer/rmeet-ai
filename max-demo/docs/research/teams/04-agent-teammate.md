# 04: Max as a full teammate (own account, mail, calendar, SharePoint, approvals, triggers)

Checked 21 Nov 2026 on Microsoft Learn / Graph docs and Google AI docs. "Not confirmed" = test it.

## Own account
- **Today (supported):** a licensed user mailbox `max@tenant`, used **app-only**, limited to that one mailbox with
  **Exchange RBAC for Applications** (`New-ManagementRoleAssignment -App … -CustomResourceScope`).
  ApplicationAccessPolicy is now "legacy". Pitfall: remove tenant-wide Mail.*/Calendars.* consent in Entra, or the
  app can still reach every mailbox. Changes take 30 min-2 h.
  https://learn.microsoft.com/en-us/exchange/permissions-exo/application-rbac
- **Later:** Entra **agent users** (Agent 365 "AI teammate": own mailbox, calendar, OneDrive, Teams presence) are
  Frontier preview only (needs M365 Copilot/E7, Copilot Credits). Keep identity behind one interface to switch later.
  https://learn.microsoft.com/en-us/entra/agent-id/agent-users

## Graph APIs (app-only, least privilege)
| Need | API | Permission |
|---|---|---|
| Draft email (approve first) | `POST /users/{max}/messages` then `/send` | Mail.ReadWrite + **Mail.Send** (send needs it; corrected after review) |
| Attachment 3-150 MB | `createUploadSession` | Mail.ReadWrite |
| Read replies to Max | `/users/{max}/messages` | Mail.Read |
| Meeting with Teams link | `POST /users/{max}/events` with `isOnlineMeeting: true` | Calendars.ReadWrite |
| Others' free/busy | `POST /users/{max}/calendar/getSchedule` | Calendars.ReadBasic (cross-mailbox with scoped RBAC: not confirmed) |
| findMeetingTimes | delegated only → **not usable**; do our own slot picking | |
| SharePoint read/write | drive/driveItem APIs on the team site | **Sites.Selected** (+ `POST /sites/{id}/permissions`) |
| SharePoint search | `/search/query` needs Files/Sites.Read.All; driveItem search not with Sites.Selected → use delta + our own index | |
Avoid standalone `POST /onlineMeetings` (not on any calendar). Teams RSC has no file-write permission.

## Triggers
- Subscriptions: mail/events < 7 days, driveItem ~29 days (root folder only, then delta), chatMessage 3 days.
  Renew on a timer; handle `lifecycleNotificationUrl`.
- Proactive posts: stored conversation reference + `app.send` (app must be installed where we post; 1:1 needs
  personal-scope install).
- Reminders: no Graph API needed → Max's own scheduler.

## Approvals
- Adaptive Cards **Action.Execute** (Universal Actions): click → `adaptiveCard/action` invoke → bot returns the
  updated card. `refresh.userIds` (≤ 60) shows buttons only to approvers. **Always re-check the approver on the
  server** (`from.aadObjectId`). The Teams Approvals Graph API is beta + delegated only → not usable by a bot.

## Tools / SDK
- Teams SDK for Python is GA (May 2026): keep it. M365 Agents SDK is for multi-channel agents.
- Microsoft's **Work IQ MCP** is delegated-only + Copilot licensed → not for an app-only bot today. If we want MCP,
  wrap our own Graph tools as an internal MCP server.

## Model tool calling
- Gemini 3.1/3.5 flash-lite: function calling (auto / any / none / validated), parallel calls.
  **Send every `thoughtSignature` back unchanged** in the same part (else HTTP 400); all calls before all responses;
  copy each call `id` into its response. Keep ≤ ~20 tools per request.
- Qwen (company gateway): OpenAI-style `tools`; to be tested.
