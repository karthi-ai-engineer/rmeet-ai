# Making Max feel alive inside Teams (animation research)

Researched 27 Nov 2026. Sources: Microsoft Learn (Teams platform docs), the Teams SDK docs, the Microsoft Tech Community forums and W3C. Anything marked **(not verified)** is my inference or comes from memory, so test it before relying on it.

## Answer first
1. **Animated GIFs in Adaptive Cards are officially "not supported".** They often play on desktop, web and Android but not on iOS. Use them only as a bonus: the first frame and the last frame must be a good still pose.
2. **Full animation (our real React/SVG Max, CSS, JS) runs only in our own web surfaces:** personal tab, dialog, Stageview, meeting side panel and stage. All of them can be opened from a card button.
3. **New: "HTML widgets"** (preview, 16 Nov 2026) put live HTML/JS inside a chat message. Microsoft says not to ship preview features to production, so they are R2 material.
4. **Built-in Teams motion is the professional core:** streaming with informative updates (an animated status line), reactions (GA July 2026), suggested actions and the AI label. A bot **cannot** trigger confetti, message effects or stickers.
5. **Don't animate by updating cards.** Update a card only when the state really changes (about one update every few seconds at most). Keep every looping animation under 5 seconds, and respect reduced motion.

## 1. Animated images in Adaptive Cards

| Question | Answer | Source |
|---|---|---|
| Formats | PNG, JPEG, GIF. "Animated GIF and SVG formats aren't supported." | [cards-reference](https://learn.microsoft.com/en-us/microsoftteams/platform/task-modules-and-cards/cards/cards-reference) (13 Oct 2026) |
| Size limits | At most 1024 x 1024 px, file under 1 MB | [cards-format](https://learn.microsoft.com/en-us/microsoftteams/platform/task-modules-and-cards/cards/cards-format) (22 Oct 2026) |
| Hosting | Public HTTPS URL. A CDN is recommended. **Redirects are not supported.** | cards-reference |
| Data URIs | Allowed from card v1.2 ([Image schema](https://learn.microsoft.com/en-us/adaptive-cards/schema-explorer/image), Dec 2025). A data-URI GIF rendered "broken or distorted" in Teams. | [forum, Nov 2023](https://techcommunity.microsoft.com/discussions/teamsdeveloper/issue-with-displaying-timer-in-adaptive-cards-using-data-uri-in-microsoft-teams-/3973689) |
| Does a GIF play? | Observed: Android yes, iOS no (2020). Desktop played it the first time, but later cards using the same URL showed a frozen frame (2023, so caching by URL). | [forum, Apr 2020](https://techcommunity.microsoft.com/discussions/teamsdeveloper/animated-gifs-in-adaptive-cards-not-playing-on-ios-devices/1297661), forum 2023 |
| Loop / autoplay | No documented behaviour. Where it animates, the client follows the GIF's own loop count **(not verified)**. | - |
| Animated WebP / APNG | Not in the supported list. APNG is a .png, so Chromium-based clients might animate it. **Not verified, test only.** | - |
| 1:1 vs group vs channel vs meeting chat | Same card renderer in every scope. No scope-specific GIF rules are documented **(not verified)**. | - |
| `Media` element | Video only, from OneDrive, SharePoint, YouTube, Vimeo or Dailymotion. Click to play. Inline on desktop, full screen or picture-in-picture on mobile. No autoplay. Not usable for a mascot. | [media elements](https://learn.microsoft.com/en-us/microsoftteams/platform/task-modules-and-cards/cards/media-elements-in-adaptive-cards) (Jun 2026) |
| Theme | The card background changes with the light or dark theme, and the bot **cannot know** the user's theme. A `themedUrls` property may exist on the new Adaptive Cards hub. **Not verified.** | - |

**What this means for Max:** a GIF is fine for a short "flourish". It must never carry meaning, and the card must look complete as a still image.

## 2. Images in normal bot messages
- Bot messages can embed images: HTML `<img>` in default mode, or `![alt](url)` in **extended Markdown** (GA 8 Oct 2026). Source: [format agent messages](https://learn.microsoft.com/en-us/microsoftteams/platform/bots/how-to/format-your-bot-messages).
- No doc says whether these images animate when they are GIFs. Old reports (2016) said bot GIFs don't play. **Test it in the real tenant.**
- Hero and thumbnail cards follow the same inline-image rules as above (static PNG, JPEG or GIF). Bot Framework's **AnimationCard is not supported in Teams** (cards-reference).
- Message size limit is 100 KB (stay under 80 KB). Base64 images don't count toward it.

## 3. Updating cards in place

| Limit (one bot, one conversation) | Value |
|---|---|
| Send to conversation | 7 per 1 s, 8 per 2 s, 60 per 30 s, 1800 per hour |
| All bots in one conversation | 14 per 1 s, 16 per 2 s |
| Whole app, per tenant | 50 requests per second |
| Streaming | 1 request per second per stream, closes after 10 min |
| Reactions | 2 adds or removes per second **across all conversations** |

Sources: [rate limits](https://learn.microsoft.com/en-us/microsoftteams/platform/bots/how-to/rate-limit) (updated Jul 2026), [streaming](https://learn.microsoft.com/en-us/microsoftteams/platform/bots/streaming-ux) (28 Oct 2026), [reactions](https://learn.microsoft.com/en-us/microsoftteams/platform/agents-in-teams/agent-reactions) (23 Nov 2026).

- "All requests are subject to the same rate limiting policy", so card updates count against these limits (my reading).
- Microsoft says limits "are subject to change" and to "avoid issuing multiple requests to the same ... conversation".
- **Universal Actions refresh** (`refresh` + `Action.Execute`) updates a card **when a user views it**. Auto refresh covers up to 60 users; bigger chats get a manual "Refresh card" menu item. Use it for "fresh when you look" (for example "starts in 5 min"), not for motion. Source: [Universal Actions](https://learn.microsoft.com/en-us/microsoftteams/platform/task-modules-and-cards/cards/universal-actions-for-adaptive-cards/work-with-universal-actions-for-adaptive-cards).
- **Verdict:** frame-by-frame card updates are a bad idea. A countdown that ticks every second, or a spinner made of updates, wastes the rate budget, flickers, and can hit HTTP 429. Update a card when the step changes (for example "Searching > Reading 3 files > Done"), at most about every 2 to 5 seconds. Make that interval a setting.

## 4. Surfaces where our own web content runs (full JS, CSS, Lottie, our React Max)

| Surface | Full animation? | Opened from a bot card? | Mobile | Notes |
|---|---|---|---|---|
| Personal app tab (static tab) | Yes (iframe on desktop, webview on mobile) | Yes, deep link with `Action.OpenUrl` | Yes | Best home for Max's full character. Lives next to the bot chat in the personal app. |
| Channel or group tab | Yes | Yes, deep link | Yes | Needs to be added to the channel or chat. |
| Dialog (task module) | Yes (`url` = our page in an iframe) | Yes, `TaskFetchAction` button | Yes | Sizes small, medium or large (20/50/60% width, 20/50/66% height) or pixels. Domain must be in `validDomains`. [dialogs](https://learn.microsoft.com/en-us/microsoftteams/platform/task-modules-and-cards/task-modules/invoking-task-modules) |
| Stageview (modal, pop-out, pop-out with chat) | Yes | Yes, `tab/tabInfoAction` invoke or a stage deep link | Partly (web = modal only) | Good for "open Max big". [Stageview](https://learn.microsoft.com/en-us/microsoftteams/platform/tabs/open-content-in-stageview) (Sep 2026) |
| Meeting side panel | Yes (narrow, about 320 px **not verified**) | Via the meeting app | Yes | Needs meeting contexts in the manifest. |
| Meeting stage (share to stage) | Yes | Only from the side panel, by a presenter or organizer | View on mobile | Needs RSC `MeetingStage.Write.Chat`. [stage](https://learn.microsoft.com/en-us/microsoftteams/platform/apps-in-teams-meetings/build-apps-for-teams-meeting-stage) |
| In-meeting notification (bubble) | Yes (our URL in a small popup) | Sent **by the bot** during a meeting | Yes | Can target specific people (50 per call). [in-meeting notification](https://learn.microsoft.com/en-us/microsoftteams/platform/apps-in-teams-meetings/in-meeting-notification-for-meeting) |
| Message extension or link unfurl preview | No (cards only) | - | - | Same image rules as cards. |
| **HTML widget in chat (preview)** | **Yes, live JS inside the message** | It *is* the message | Yes (docs say test on iOS and Android) | See below. |

**HTML widgets** ([send](https://learn.microsoft.com/en-us/microsoftteams/platform/html-widgets/send-html-widgets), 3 Nov 2026; [UX](https://learn.microsoft.com/en-us/microsoftteams/platform/html-widgets/ux-guidelines); [accessibility](https://learn.microsoft.com/en-us/microsoftteams/platform/html-widgets/accessibility-guidelines)):
- A sandboxed iframe inside the message. It is sent as an extended Markdown message with an `html-widget` code block. Built on the MCP Apps standard. The Python SDK has helpers ([teams.py guide](https://microsoft.github.io/teams-sdk/python/in-depth-guides/html-widgets/)).
- External scripts and calls are blocked unless listed in `securityPolicy`. The widget reports its own height. It can go "fullscreen" or picture-in-picture.
- Rules: must support light and dark themes, **must respect `prefers-reduced-motion`**, no harmful flashing, no auto-advancing content, "autoplay is not recommended".
- Risks: it is a **preview** ("don't integrate preview features in agents or apps released to production", [preview page](https://learn.microsoft.com/en-us/microsoftteams/platform/developer-preview-features)). Users need public preview turned on. Widget content **can't be exported** by compliance tools, and Microsoft says orgs "can disable bots" that send widgets. The HTML probably counts toward the 100 KB message limit **(not verified)**.
- Verdict: an ideal future home for a small live Max in chat. Watch for GA, and always keep a card fallback.

## 5. Built-in Teams motion a bot can trigger

| Feature | Can Max trigger it? | Details |
|---|---|---|
| Streaming response | Yes, in 1:1, group chats, channels and meeting chats (Oct 2026) | Text grows live, and the bubble animates when it finishes. Only one stream per conversation. Not for proactive messages. |
| Informative updates | Yes | Short status text (up to 1000 characters) with an **animated icon** under the user's message. No notification. Everyone in a group sees it. Stops when content starts. |
| Typing indicator | Yes (`typing` activity) | Standard Bot Framework. Streaming builds on it. Exact duration **not verified**. |
| AI-generated label, citations, sensitivity label | Yes (`add_ai_generated()`) | All scopes. Text can't be customized. Shown after the stream ends. [labels](https://learn.microsoft.com/en-us/microsoftteams/platform/agents-in-teams/integrate-ai/ai-content-labels) |
| Feedback (thumbs up/down) | Yes | Only on the final message. |
| Suggested actions | Yes, all scopes | Up to 3 shown. Not allowed together with attachments. [suggested actions](https://learn.microsoft.com/en-us/microsoftteams/platform/bots/how-to/conversations/suggested-actions) |
| Prompt starters | Yes (manifest only, static) | GA Apr 2026. Up to 12 per command list. |
| Reactions on messages | **Yes** (GA 10 Jul 2026) | Max can add or remove emoji on any message. Microsoft says use them "for acknowledgment or status, not sentiment" and "avoid using reactions to add personality". |
| Targeted (private) messages in group chats | Yes (GA 30 Jul 2026) | Good for private status without noise. |
| Confetti, "message effects", celebrations | **No** | No API found. |
| Stickers, GIPHY, Teams GIF picker | **No** | No bot API found. `Action.Compose` can only pre-fill the *user's* compose box. |

## 6. Accessibility and good practice
- **WCAG 2.2.2 (Pause, Stop, Hide):** motion that starts on its own, lasts **more than 5 seconds** and sits next to other content needs a pause or stop control. A GIF can't offer that, so **every GIF must finish within 5 seconds**: play 1 to 2 times, then stop. [W3C](https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide.html)
- **WCAG 2.3.1:** no more than 3 flashes per second. Avoid big brightness flashes.
- **Reduced motion:** GIFs can't detect it. Our web surfaces must honour `prefers-reduced-motion` and show a still pose instead.
- Always set `altText` (for example "Max, smiling"). Never put meaning only in the animation.
- **File size:** the Teams cap is 1 MB. Our targets: **under 150 KB per GIF** (hard ceiling 250 KB), still images under 30 KB. Always reuse a few cached assets instead of new files per message.
- **Frame timing:** use 20 to 25 fps (40 to 50 ms per frame). Browsers slow frames under 20 ms down to about 100 ms.

## 7. Producing assets from our SVG character
**Format:** use **GIF** in cards and messages (the only allowed animated-capable format), plus a **static PNG** of the same pose. Use the real React SVG (not files) in tabs, dialogs and widgets. Test WebP and APNG once, but don't rely on them.

**Pipeline (offline, at build time, output not kept in git):**
1. **Render frames:** use Playwright (headless Chromium) to open the avatar lab with `?mood=happy&render=1` on a transparent page. Step time precisely: `page.clock` drives JS/rAF-based Motion animations **(check Motion works with it)**. `document.getAnimations()` with `currentTime` drives CSS animations. Take one screenshot per frame with `omitBackground: true`, giving PNGs with alpha.
2. **Encode:** use [gifski](https://gif.ski) (best quality GIF from PNG frames, supports `--fps`, `--width` and repeat count). Alternative: ffmpeg `palettegen` + `paletteuse`.
3. **Shrink:** use [gifsicle](https://www.lcdf.org/gifsicle/) `-O3 --lossy=30 --colors 64`. An orange cloud needs few colours.
4. **Check:** a script verifies size under 150 KB, total length under 5 s, a fixed loop count, and a first frame equal to the last frame.

**Size:** draw at 128 px and display at 64 to 96 px (sharp on high-DPI screens). Max 160 px. Keep 1.5 to 3 s per play.

**Transparency:** GIF has only on/off alpha, so soft edges get a halo on the wrong background. Since the bot can't know the theme, choose one of these:
- **(A, recommended)** Bake Max onto his own small rounded **tile** (soft warm background, in the image itself). It looks right on both light and dark cards, with no halo.
- (B) Use a hard pixel edge with no anti-aliasing. It looks cheap.
- (C) Make two versions, one matted for light and one for dark. Only useful if `themedUrls` turns out to work (not verified).

## 8. Recommendation for Max

| Moment | Surface | Format | How often | Notes |
|---|---|---|---|---|
| Thinking or working on a reply | Streaming **informative updates** ("Reading the sprint notes...") | Built-in | Every reply that takes over 1 to 2 s | The main "alive" signal. Professional, and costs nothing. |
| Answer arriving | Streaming text + AI label + feedback | Built-in | Every AI reply | Required good practice anyway. |
| "Got it" for longer jobs | **Reaction** on the user's message (for example ⏳ then ✅) | Built-in | Only for tasks over about 10 s | Status, not mood. Stay under 2 per second app-wide. |
| Welcome / first meeting with Max | Card with a **tiled GIF** (wave, plays twice, under 5 s) + "Open Max" button | GIF + still first frame | Once per user | The one place a mascot GIF earns its keep. |
| Big success (task done, meeting summary ready) | Card header with a tiled **celebrate GIF**, played once | GIF | Rare (at most about once a day per user, a setting) | No confetti API exists. This is the closest honest option. |
| Sorry, error, can't help | Card with a **static** "sorry" pose | PNG | When it happens | No motion on errors. |
| Normal cards (answers, lists, approvals) | Small **static** Max icon or none | PNG | Always | Calm by default. |
| Long job progress | Update the **same card** when the step changes | Card update | 1 per 2 to 5 s at most (a setting) | Never frame by frame. |
| Full personality (all moods, idle motion, talking) | **Personal tab** "Max" + **dialog / Stageview** opened from cards | Live React/SVG + reduced-motion fallback | User-chosen | The real character lives here. |
| In meetings | Side panel (live SVG) + bot **in-meeting notification** bubble for key moments | Live web | Few per meeting | Never on stage without a presenter's action. |
| Later (R2) | **HTML widget** with a mini live Max inside chat | Live HTML | When GA | Keep a card fallback. Admins may block it. |

**What NOT to do**
- Don't rely on GIFs animating (iOS doesn't). Don't put information only in motion.
- No looping GIFs, nothing over 5 s, no flashing, no GIF on every message.
- Don't animate by rapid card updates or by editing messages every second.
- Don't use reactions for mood or personality (Microsoft's own guidance). Don't react to every message.
- No data-URI GIFs, no redirecting image URLs, no images behind login. Version the URLs (`max-wave.v3.gif`) so caches update.
- Don't ship preview features (HTML widgets) in R1.
- Our `teams_sim` should copy these rules (static-first cards, GIF optional), so we don't design something real Teams won't show.

## Open questions for Karthi
1. Is the "Max on his own tile" look (option A) OK for card GIFs and stills?
2. Should R1 use GIFs in only two moments (welcome, big success) and stay static everywhere else?
3. Should the personal tab be the "home" of the full animated Max in R1, with cards linking to it?
