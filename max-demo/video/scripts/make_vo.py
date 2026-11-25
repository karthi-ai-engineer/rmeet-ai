"""
Voice-over for the Max film: every spoken line from the local Kokoro server (http://127.0.0.1:8400, free, on the GPU),
saved as WAV in video/assets/vo/, plus durations in video/assets/vo/durations.json (the film's timeline uses them).
  .venv-tts\\Scripts\\python video\\scripts\\make_vo.py
"""

import io
import json
import urllib.request
import wave
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "assets" / "vo"
TTS = "http://127.0.0.1:8400/tts"

NARRATOR, MAX, KARTHI, PRINCE, DANIEL = "af_heart", "Charon", "Alnilam", "Iapetus", "Achird"   # project voices

# film v3 (call first, then the channel montage). People: Karthi M, Prince Alex, Daniel.
LINES = {
    "n_hook1": (NARRATOR, "Every decision is made in a meeting."),
    "n_hook2": (NARRATOR, "And lost, the moment the call ends."),
    "n_meet": (NARRATOR, "Meet Max. Your AI teammate, in every Teams call."),
    "k_who": (KARTHI, "Max, who said LiftLine was forty K cheaper?"),
    "m_who": (MAX, "You did, Karthi. In our October twentieth meeting."),
    "k_book": (KARTHI, "Max, book a follow-up on Tuesday with Prince and Daniel."),
    "m_card": (MAX, "I've put the invite in the chat, for Karthi to approve."),
    "n_yes": (NARRATOR, "Nothing happens until the right person says yes."),
    "m_booked": (MAX, "Booked. Tuesday, ten thirty."),
    "k_mail": (KARTHI, "Max, send Elena the budget draft."),
    "p_cc": (PRINCE, "And copy Tom, at gmail dot com."),
    "m_refuse": (MAX, "I can't. That address is outside the company."),
    "k_wrap": (KARTHI, "Okay, let's wrap up."),
    "m_recap": (MAX, "Before we finish: two decisions, three action items. Anything to correct?"),
    "d_fix": (DANIEL, "Max, my date is the twenty-seventh."),
    "m_gotit": (MAX, "Got it."),
    "n_chan": (NARRATOR, "After the call, Max keeps working in your channel."),
    "n_tag": (NARRATOR, "Max does the work. You give the yes."),
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    durations = {}
    for key, (voice, text) in LINES.items():
        req = urllib.request.Request(TTS, data=json.dumps({"text": text, "voice": voice}).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        wav = urllib.request.urlopen(req, timeout=120).read()
        (OUT / f"{key}.wav").write_bytes(wav)
        with wave.open(io.BytesIO(wav)) as w:
            durations[key] = round(w.getnframes() / w.getframerate(), 3)
        print(f"{key:10s} {durations[key]:5.2f}s  [{voice}] {text}")
    (OUT / "durations.json").write_text(json.dumps(durations, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
