# Max: avatar (identity)

**Status: BASE AGREED (27 Nov 2026).** The new flat-bottom animated cloud (Part 4) is Max's character; we keep improving it. Until now: an orange cloud placeholder (`02-use-cases.md`: "orange cloud for
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

## Part 4: the look, decided direction (Karthi, 27 Nov 2026)
- Start from the prototype's animated cloud, **but change the shape**: puffy bumps on top and a **flatter bottom with
  a gentle bulge** (a cloud sitting on the ground). Reason: a round cloud hides body motion; a flat base makes
  squash-and-stretch, leaning and hops clearly visible.
- **Body animation must be clearly visible**, not only the eyes: breathing, sway, lean toward the gaze, hops,
  squash and stretch, follow-through, a ground shadow that reacts. "Very interactive", polished.
- Built by the frontend specialist as a reusable component: `teams_sim/web/src/avatar/MaxCharacter.tsx`, playground
  `?view=avatar` (`AvatarLab.tsx`). Pictures will be `pictures/avatar-4-*.png`.
**Built 27 Nov 2026** (frontend specialist, checked by Claude): `teams_sim/web/src/avatar/MaxCharacter.tsx` +
`AvatarLab.tsx`, page `?view=avatar`. New shape: 4 puffy top bumps, wide base with rounded corners and a gentle
bulge, 1.36:1, orange #F7630C with a lighter top band; 3-bump simplified shape at 40 px and below. 16 moods with
visible body motion (squash and stretch, hops, lean toward the gaze, rocking, slump), springs between states,
ground shadow reacts, reduced-motion mode, pauses when off-screen; 61 fps measured.
Pictures: `pictures/avatar-4-lab.png`, `avatar-4-poses.png`, `avatar-4-all-moods.png`, `avatar-4-meeting-dark.png`.

**Karthi (27 Nov 2026): agreed as the base.** We keep working on it from here (next ideas: talking mouth / cheek
squish, in-between moves such as a wake-up jolt, shape-check tests, then using it in the real places).

## Part 5: animation plan (AGREED 27 Nov 2026)
- **Teams chat:** Teams' own motion (streaming, status lines, cards updating in place) + a few small Max animation
  moments in cards. **Which moments and where GIFs can play: research first** (Karthi), then decide, aiming to make
  Max as interactive as Teams allows.
- **Max's own pages (Max app, home page):** the full living Max (all moods, hover, poke).
- **Meetings (Max Meeting, later):** Max listens, thinks and speaks live on its tile.
Research: `docs/research/teams-animation.md` (running 27 Nov).

## Part 6: polish round 1 (built 27 Nov 2026)
Talking mouth (dark "D" with coral tongue, faint blush cheeks, only while speaking / briefly when happy); in-between
moves (wake-up jolt, startle, satisfied settle, recover, ready nod; 0.5-0.85 s, springs); interactive: hover lean +
**poke** (click / tap / Enter: dent, giggle wobble, happy eyes), keyboard focus ring, state-aware label.
Pictures: `pictures/avatar-5-speaking-mouth.png`, `avatar-5-transitions.png`, `avatar-5-lab.png`.
Open points from the specialist: ready nod subtle in stills; mouth tiny at 48 px; settle shows dot eyes for 0.15 s;
"!" pops slightly early in the startle; reduced motion still has a small voice stretch; cheeks faint on purpose;
no automated tests yet for moves / poke.

## Part 7: where Max can animate in Teams (research 27 Nov 2026: `docs/research/teams-animation.md`)
- Animated GIFs in cards are officially **not supported** (often play on desktop/web/Android, not iOS): bonus only,
  first/last frame must be a good still pose. No confetti / message effects / stickers API for bots.
- **Full live Max only in our own pages inside Teams:** personal tab, dialog, Stageview, meeting side panel and stage;
  all can be opened from a card button. "HTML widgets" (live HTML in chat) are preview since 16 Nov 2026 → R2 at most.
- Built-in Teams motion is the professional core: streaming with status lines, reactions (⏳ → ✅ for long tasks),
  suggested actions, AI label. Don't animate by updating cards (only on real state changes, every few seconds max).
- Proposed: GIF moments only for **welcome wave** and **big success (celebrate)**, Max on his own small rounded tile
  (fixes GIF transparency on light/dark), under 150 KB, plays twice, < 5 s; static Max elsewhere; the **personal tab
  = home of the full animated Max**, cards link to it. To decide with Karthi.
**Agreed (Karthi, 27 Nov 2026):** GIF moments only for the **welcome wave** and **big success (celebrate)**; calm
everywhere else; **Max's personal tab is the home of the full animated Max** (cards link to it with "Open Max").
Polish fixes: Claude decides what looks best (hide mouth below ~64 px, half-closed lids instead of dot eyes while
settling, "!" timed to the flinch, cheeks slightly stronger but still soft).
