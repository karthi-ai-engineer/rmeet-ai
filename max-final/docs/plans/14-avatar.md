# Max: avatar (identity)

**Status: IN DISCUSSION (26 Nov 2026).** Until now: an orange cloud placeholder (`02-use-cases.md`: "orange cloud for
now, richer animations later"). Max orange `#F7630C` is the brand colour (agreed in `13-ui-design.md`).

## Part 1: options (PROPOSED 26 Nov 2026)
Picture: `pictures/avatar-1-options.png` (source `pictures/avatar-1-options.html`). Each option shown at Teams sizes
(192 app icon · 48 · 32 chat · 20 lists), on light and dark, in a chat row, and as the white 32×32 outline icon Teams
also needs.
| Option | Idea | Strong | Weak |
|---|---|---|---|
| A · Cloud | white cloud on orange (today's, refined) | simple, known, clear at 20 px | plain, could be any cloud app |
| **B · Friendly cloud** (recommended) | same cloud + two small eyes and a smile | feels like a teammate; still clean small; easy to animate | — |
| C · M cloud | letter M drawn as cloud bumps | says "Max" at a glance | more logo than character |
| D · Spark | AI sparkle on orange | reads as "AI" | looks like Copilot / Gemini, least unique |

Later (Max Meeting / voice): living states for the chosen avatar: idle (breathing glow), thinking (pulse ring),
speaking (moves with the voice), done (small check).

## Part 2: blob-style character (PROPOSED 26 Nov 2026, from Karthi's reference)
Karthi's reference: `pictures/image.png` (simple blob shapes with two white pill eyes). Not copied: Max gets its
own shape in that style. Picture: `pictures/avatar-2-blob.png` (source `avatar-2-blob.html`).
| Option | Idea |
|---|---|
| **1 · Cloud, upright eyes** (recommended) | Max's orange cloud blob, two calm white pill eyes |
| 2 · Cloud, tilted eyes | same cloud, eyes tilted like a relaxed smile (more playful) |
| 3 · Soft round, with shine | smooth round body, soft highlight (cleanest when tiny, less "cloud") |
Expressions for animation later: normal · blink · happy · thinking · listening · sorry.

## Part 3: the animated cloud from the prototype (found 26 Nov 2026, Karthi pointed to it)
`../max-demo/bot-avatar/index.html` + `avatar.js` (read-only prototype): a ready **animated cloud avatar engine**:
orange cloud body, white capsule eyes that move as if on a 3D sphere, auto blink and glance, follow-cursor,
**14 expressions** (idle, listening, look left/right/up/down, surprised, squint, thinking, speaking with voice rings,
happy, sleepy, confused, wink), colour and background switch, meeting-tile mode, a "meeting demo".
Screenshot: `pictures/avatar-3-demo-cloud.png`. Karthi's reference `pictures/image.png` is the same picture as
`max-demo/bot-avatar/image.png` (the style source for that engine).
**Likely direction (to confirm):** reuse this engine's look (it matches option 1 "cloud, upright eyes") as Max's
avatar, rebuilt cleanly in `teams_sim/web` for Max's pages and meetings; still icon = its idle frame.

## Open questions (paused 26 Nov 2026, Karthi: "stop till here, we will do things later")
1. Final avatar: the prototype's animated cloud (recommended), or blob option 1 / 2 / 3?
2. Animation plan: Teams' own motion in the chat (streaming, status, in-place card updates) + a few Max GIF moments
   in cards; the full living avatar only on Max's own pages and meetings. OK?
3. Add a **Max home page** (living avatar) to the Max app, next to Setup / Health / Costs?
