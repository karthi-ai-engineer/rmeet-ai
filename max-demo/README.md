# rmeet-ai

**Max** is an AI teammate that lives in Microsoft Teams. It reads the team's channel and files, answers
`@Max` questions in threads, joins meetings like a person (listens, answers out loud when someone says
"Max…"), and writes meeting notes it remembers next time.

To build and test Max without a real company tenant, this repo also contains **rmeet-ai**: a Teams-like
app plus a fake Microsoft cloud (sign-in, Bot Connector, Graph, calling + media) and a simulated team
(Business Planning at Thirdwave Corporation: GALLERIA, raytrek, Dospara; fictional internal data) with AI
colleagues who speak in their own voices.

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

## Quick start: one command

Needs Python 3.12+. In the project folder:

```
run                  # Windows (cmd or PowerShell: .\run)   ·   macOS/Linux: python3 run.py
```

It creates `.venv` and installs libraries (only when `requirements.txt` changed), checks the keys in
`voice-chat/.env` (creates it from the example on first run; paste the Gemini + company Qwen keys),
refreshes Max's settings (`register_app.py`), starts rmeet-ai (http://localhost:8100) and Max (port 3978),
waits until both answer and opens the browser. **Ctrl+C** stops both. Other options: `run --no-browser`,
`run --stop` (stop a demo started from another window). Logs: `logs/rmeet.log`, `logs/max.log`.

Per-machine extras (kept out of git, started by `run` when present): `local_tts/` (local Kokoro voice server,
port 8400, used when `TTS_PROVIDER=local`) and `gemini_usage/` (Gemini usage meter + live cost dashboard,
http://localhost:8600). Without them the demo still runs (Gemini voices / no dashboard).

Manual way (two terminals): `.venv\Scripts\python simulations\rmeet\server.py` and
`.venv\Scripts\python max\app.py` (set `PYTHONIOENCODING=utf-8` for Max on Windows).

Status, decisions and next steps: **`HANDOVER.md`**.
