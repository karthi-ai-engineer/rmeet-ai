# Voice chat test (Gemini + cloud avatar)

First use case: you talk to Max through your mic, Gemini hears the audio and
replies, and the reply is shown as **text** (no voice yet). The cloud avatar
reacts: listening → thinking → replying → emotion.

## Setup (one time)

1. Get a free Gemini API key: https://aistudio.google.com/apikey
2. Copy `voice-chat/.env.example` to `voice-chat/.env` and paste your key.

## Run

```
python voice-chat/server.py
```

Then open http://localhost:8000 in **Chrome or Edge** and allow the microphone.

## How it works

```
Browser (mic) ──WAV audio──► server.py ──► Gemini (gemini-3.5-flash-lite)
     ▲                                          │
     └──── {transcript, reply, emotion} ◄───────┘
```

- `index.html` / `app.js`: page, mic recording (16 kHz WAV), chat panel, avatar control
- `server.py`: serves the pages and calls Gemini; keeps the API key off the browser
- `../bot-avatar/avatar.js`: the shared cloud avatar engine

To try another model, change `GEMINI_MODEL` in `.env` and restart the server.
