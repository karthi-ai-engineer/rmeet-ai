# Max tools research: web, files, timers, apps, agents, charts

Date: 2026-11-25. Scope: use cases U16-U22. Rule: only Gemini (main `gemini-3.1-flash-lite`) plus local models. Prices are list prices; check them again before you budget.

## Short answer

| Need | Pick | Fallback |
|---|---|---|
| Web search (U19) | Gemini Grounding with Google Search, called inside our own `web_search` tool | Tavily |
| Read a web page (U19) | `httpx` + `trafilatura`, run locally | Jina Reader |
| Files (U18) | JSON spec, then our renderer (python-pptx / openpyxl / python-docx), then LibreOffice for PDF and previews | none needed |
| Timers (U16/U17) | Our own SQLite `jobs` table and one asyncio loop | APScheduler 3.x |
| Other apps (U20) | Pydantic AI MCP over streamable HTTP, behind an approval gate | stdio for local servers |
| Other agents (U21) | `ask_agent(agent, request)` placeholder that maps to A2A v1.0 later | |
| Charts (U22) | matplotlib PNG for chat, native charts inside pptx/xlsx | plotly + kaleido |

---

## 1. Internet research (U19)

**Gemini grounding.** `gemini-3.1-flash-lite` is listed as stable. Grounding costs **$14 per 1,000 search queries** after **5,000 free per month**. Those 5,000 are shared across all Gemini 3+ models, with a cap of 1,500 a day. There is no grounding on the free tier. One prompt can fire several queries, and each one is billed. Grounded page text is not billed as input tokens. ([pricing](https://ai.google.dev/gemini-api/docs/pricing), [grounding docs](https://ai.google.dev/gemini-api/docs/google-search))

**Can it share one call with our own tools?** On Gemini 3, yes. Google calls this "tool combination" and it is still **Preview** ([docs](https://ai.google.dev/gemini-api/docs/tool-combination)). Pydantic AI supports it: "Gemini 3 models support combining native tools with function tools" ([Pydantic AI built-in tools](https://ai.pydantic.dev/builtin-tools/)). But Google's grounding page does not list 3.1 Flash-Lite by name, and the feature is still Preview.

**Recommended pattern (safe either way).** Give the agent a normal function tool, `web_search(query)`. Inside it, make a separate Gemini call that has only the `google_search` tool turned on, and return `{answer, sources[]}`. The main agent never mixes tool types, the sub-call is easy to test, and we can switch to Tavily inside the same function without touching the agent.

**Terms to respect** ([Gemini API terms](https://ai.google.dev/gemini-api/terms)):
- Show grounded results only to the user who asked, together with Google's "Search Suggestions" (an HTML/CSS snippet).
- Do not change the results or mix other content into them.
- No click tracking.
- No caching or analysis of the results, apart from chat history (up to 2 years) and legal needs.

**Teams cannot render that HTML snippet** (see risks).

| Option | Price | Free | Notes |
|---|---|---|---|
| Gemini grounding | $14/1k queries | 5k/mo (paid tier) | No new vendor or key. Display terms apply |
| [Tavily](https://docs.tavily.com/documentation/api-credits) | ~$0.008/credit (basic search = 1 credit, advanced = 2) | 1,000 credits/mo | Built for agents. Search + extract. Results can be stored |
| [Brave Search API](https://api-dashboard.search.brave.com/documentation/pricing) | $5/1k | ~$5 credit/mo (card needed) | Own index. Old free tier is gone |
| [Exa](https://exa.ai/docs/reference/pricing) | $7/1k (with contents) | $10/mo | Semantic search. Higher cost |
| Serper / [SerpApi](https://serpapi.com/pricing) | ~$1/1k / ~$25/1k | 2,500 once / 250/mo | Google results scraped by a third party. Legal grey area |
| [Jina Reader](https://jina.ai/reader) (read pages) | token based, ~cents per 1M | 20 RPM with no key, 500 RPM with a free key | Handles JS-heavy pages |

**Pick:** Gemini grounding as the main search. Tavily as the fallback, and as the main search if the display terms are a blocker. For reading pages, use local `trafilatura` (Apache-2.0, no cost, no vendor) and fall back to Jina Reader when a page needs JavaScript.

## 2. Files: pptx, xlsx, docx, pdf (U18)

**The LLM writes a JSON spec, never code.** A small renderer turns the spec into the file. Example:
`{"type":"pptx","template":"house","slides":[{"layout":"title","title":"Q1 results"},{"layout":"bullets","title":"Highlights","bullets":["..."]},{"layout":"chart","chart":{"kind":"bar","categories":[...],"series":[...]}}]}`.
Pydantic validates the spec, so bad output is caught before rendering.

**House style.**
- **pptx:** Build one template with fixed, named layouts (title, bullets, two-column, chart, table, closing), the logo and colours on the slide master, and fonts in the theme. Save it as **.pptx, not .potx**: python-pptx will not open .potx directly. The renderer only picks a layout and fills its placeholders, so every deck looks the same.
- **docx:** Use a .docx template with named styles (Heading 1, Body, Table). Optionally use `docxtpl` (LGPL-2.1) for Jinja-style fill-in.
- **xlsx:** Use a template workbook with named cell styles and a header row.

**Editing an existing file.** `files.read` returns an outline (slide numbers, titles, tables, sheet names and ranges). The LLM sends back a list of operations, for example `remove_slide 3`, `update_cell Sheet1!B4`, `replace_table slide 2`. The renderer applies them and **saves a new version; it never overwrites**.
- python-pptx has no official delete or reorder for slides. Use the well-known XML fix: remove the slide id from `sldIdLst` and drop the relationship.
- openpyxl **drops existing charts and some shapes** when it opens and re-saves a workbook. Rebuild charts from the spec.

**Asking for missing details.** Each spec type lists its required fields (topic, audience, number of slides, data source). If any are missing, `files.create` returns `{"need": ["audience","data period"]}` and Max asks. For decks, Max shows a text outline first, and after the user's "ok" it renders.

**PDF and previews on Windows without Office.**
- `docx2pdf` needs MS Word, so it is not an option.
- Use **LibreOffice headless**: `soffice --headless --convert-to pdf`. It is a separate program, licensed MPL-2.0.
- Render preview PNGs from the PDF with **pypdfium2** (Apache-2.0/BSD-3). Avoid PyMuPDF, which is AGPL.
- Post slides 1-3 as images in the chat.
- Use `reportlab` (BSD) only for simple generated PDFs.
- LibreOffice notes: install the house fonts on the server, run one conversion at a time (or give each run its own `-env:UserInstallation`), and set a timeout.

| Library | Licence | Note |
|---|---|---|
| [python-pptx](https://pypi.org/project/python-pptx/) 1.0.2 | MIT | No release since Aug 2024, but stable |
| python-docx | MIT | |
| openpyxl | MIT | Native charts supported |
| reportlab | BSD | |
| LibreOffice | MPL-2.0 | Run as a separate process |
| pypdfium2 | Apache-2.0/BSD-3 | |

## 3. Timers and repeating jobs (U16/U17)

**Pick our own SQLite table plus one asyncio loop.**
- Table: `jobs(id, owner, conversation_ref, kind, payload_json, next_run_utc, repeat_rule, tz, status, attempts, last_error)`.
- Every 15-30 s the loop picks rows with `status='pending' AND next_run_utc <= now`, marks them `running`, does the work, then sets `done` or, for repeating jobs, works out the next run time.
- On startup, rows left `running` go back to `pending`. Missed one-off jobs run late with a "(late)" note. Missed repeating jobs skip ahead to their next time.

This is about 150 lines we fully understand, and it uses the same database as everything else.

**Why not APScheduler?**
- 4.0 is **still alpha** (4.0.0a6) and says it is not for production.
- 3.x works with `SQLAlchemyJobStore`, but it pickles job functions, adds SQLAlchemy, and runs jobs twice with more than one uvicorn worker.

([APScheduler docs](https://apscheduler.readthedocs.io/))

**Time parsing.** The LLM outputs structure, not text:
- One-off: `{"at":"2026-11-26T03:00","tz":"Asia/Kolkata"}`.
- Repeating: `{"repeat":{"freq":"weekly","byday":["MO"],"time":"09:00"},"tz":"..."}`.

Code checks the result (future time, valid zone) and stores UTC. Max always repeats it back: "OK, Tue 26 Nov 03:00 IST". Compute repeats with `python-dateutil` `rrule` (BSD). Avoid `croniter`, whose maintainer abandoned it in 2025. `dateparser` is only a fallback for simple relative phrases.

Notes:
- On Windows, `pip install tzdata` so `zoneinfo` works.
- Take the user's time zone from the Teams activity (`localTimezone`), and ask if it is missing.
- Store the Teams **conversation reference** with each job. Max needs it to send the proactive message later.

## 4. Other apps through MCP (U20)

Pydantic AI now uses one `MCPToolset` class, or the higher-level `MCP` capability. It covers stdio (a local process), **streamable HTTP** (remote; prefer this) and SSE (deprecated). You can also load servers from an `mcp_config.json` with `load_mcp_toolsets()` ([MCP client docs](https://ai.pydantic.dev/mcp/client/)).

Hosted servers we could add later:
- **Slack:** `https://mcp.slack.com/mcp` (OAuth, needs workspace admin approval) ([Slack docs](https://docs.slack.dev/ai/slack-mcp-server/)).
- **Notion:** `https://mcp.notion.com/mcp` (OAuth). The SSE endpoint retires on 2027-02-23 ([Notion docs](https://developers.notion.com/guides/mcp/get-started-with-mcp)).

**Security.**
1. **Allowlist** the server URLs and tool names per server with a filtered toolset. Expose only the tools we need, for example Notion `search` and `update-page`.
2. Give each server a **prefix** (`notion_*`).
3. Put any write tool behind **approval**: `ApprovalRequiredToolset` or `requires_approval=True`. The run pauses with `DeferredToolRequests`, Max posts an Approve/Deny card, and the run resumes with `DeferredToolResults` ([deferred tools](https://ai.pydantic.dev/deferred-tools/)). This matches our L3 level.
4. Keep OAuth tokens per user, never shared.
5. Treat MCP tool output as untrusted text, because of prompt-injection risk.
6. Log every call.

## 5. Agent to agent (U21)

**A2A v1.0** is the first stable spec (April 2026). It is run by the Linux Foundation and has 150+ supporting organisations ([LF press](https://www.linuxfoundation.org/press/a2a-protocol-surpasses-150-organizations-lands-in-major-cloud-platforms-and-sees-enterprise-production-use-in-first-year)). The official Python SDK is [`a2a-sdk`](https://pypi.org/project/a2a-sdk/) (spec 1.0, JSON-RPC/REST/gRPC).

MCP is for agent-to-tool calls. A2A is for agent-to-agent work: agent cards, long-running tasks, and states such as `input-required`. Pydantic AI's built-in `to_a2a()` is deprecated, and FastA2A was handed over to Datalayer in May 2026. Use `a2a-sdk` directly when the time comes.

**Placeholder now:** `ask_agent(agent: str, request: str, wait: bool = True) -> {status, task_id, result, question}`.
- `status` takes A2A's values: `submitted | working | input-required | completed | failed`.
- A small registry in config maps each name to a backend. Today that is a local Python function or an HTTP call; later it is an A2A client using the agent card URL.
- Approval level L3.

## 6. Charts (U22)

- **matplotlib** (Agg backend) for chart PNGs in chat. It is local and needs no browser.
- **Native charts** inside files, so users can edit them: python-pptx `CategoryChartData` and openpyxl `BarChart`/`LineChart`.
- **plotly + kaleido v1** looks nicer, but kaleido needs Chrome installed (`plotly_get_chrome`) ([plotly docs](https://plotly.com/python/static-image-export/)). That is one more moving part on Windows.

The LLM gives `{kind, title, categories, series}`. Code draws the chart and the LLM never writes plotting code.

## Top risks (judged by "could it break the demo?")

1. **Sending files and images in Teams.** A bot can't just attach a pptx in a channel. It needs a FileConsentCard (1:1 chat) or an upload to SharePoint/OneDrive through Graph. Test this first.
2. **Grounding display terms vs Teams.** Teams can't render Google's HTML search suggestions. Fine for a demo, but a compliance question for production. Tavily avoids it.
3. **Tool combination on 3.1 Flash-Lite is Preview and not confirmed.** The sub-call pattern sidesteps it.
4. **LibreOffice** can hang, render fonts differently, or clash when two conversions run at once. Use a timeout, one at a time, and install the fonts.
5. **openpyxl edits lose existing charts.**
6. **Time zone mistakes** ("3 AM" whose 3 AM?). Always repeat the time back with its zone.
7. **Proactive messages** need a stored conversation reference, and the bot must be installed in that chat.
8. **MCP prompt injection** and broad OAuth scopes. Use allowlists and approvals.
