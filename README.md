# rmeet-ai

**Max** is an AI teammate that lives in Microsoft Teams. It reads the team's channel and files, answers
`@Max` questions in threads, joins meetings like a person (listens, answers out loud when someone says
"Max…"), and writes meeting notes it remembers next time.

To build and test Max without a real company tenant, this repo also contains **rmeet-ai**: a Teams-like
app plus a fake Microsoft cloud (sign-in, Bot Connector, Graph, calling + media) and a simulated team
(Planning Department of Kestrel Home Goods) with AI colleagues who speak in their own voices.

```
  Browser (Teams-like UI)  ──>  rmeet-ai  :8100  ── fake Microsoft (identity, Bot Connector, Graph, calls, media)
                                   │   ▲                       │   ▲
               AI colleagues (Qwen)│   │ Gemini voices         ▼   │ real Microsoft contracts only
                                   ▼   │                     Max  :3978  (Teams SDK for Python)
                         simulations/planning-department          Qwen brain · Gemini ears + voice
```

| Folder | What |
|---|---|
| `max/` | Max, the bot (separate program). See `max/README.md` |
| `simulations/` | rmeet-ai app (`rmeet/`), fake Microsoft (`teams/`), the world (`planning-department/`). See `simulations/README.md` |
| `bot-avatar/` | Max's cloud avatar (eyes-only, emotions) |
| `voice-chat/` | First Gemini voice test app; its `.env` holds the model keys for everything |
| `docs/research/teams/` | Research: bot messaging, Graph knowledge APIs, meeting calling |
| `tests/` | End-to-end tests per phase |

## Quick start (Windows)

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy voice-chat\.env.example voice-chat\.env        # then paste the Gemini + company Qwen keys
.venv\Scripts\python simulations\teams\register_app.py
.venv\Scripts\python simulations\rmeet\server.py     # terminal 1  -> http://localhost:8100
.venv\Scripts\python max\app.py                      # terminal 2
```

macOS/Linux: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`, then the same
commands with `.venv/bin/python` and `/` paths.

Status, decisions and next steps: **`HANDOVER.md`**.
