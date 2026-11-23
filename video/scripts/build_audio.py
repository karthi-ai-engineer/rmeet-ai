"""
Soundtrack for the Max film: voices on their cues, UI sounds generated in code (no licences needed), an optional
licensed music bed that ducks under speech, loudness-normalised to -16 LUFS (two-pass ffmpeg loudnorm).
Then muxes the picture and sound into out/Max-film.mp4.
  .venv-tts\\Scripts\\python video\\scripts\\build_audio.py          (needs out/timeline.json from render.mjs)
"""

import json
import re
import subprocess
import tempfile
import wave
from glob import glob
from pathlib import Path

import numpy as np

V = Path(__file__).resolve().parents[1]
OUT, VO, MUSIC = V / "out", V / "assets" / "vo", V / "assets" / "music"
SR = 48000
CALL_VOICES = ("k_", "m_", "d_")          # people in the Teams call get a light "call" EQ; the narrator stays full-range


def ffmpeg() -> str:
    hits = glob(str(Path.home() / "AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg*/ffmpeg-*/bin/ffmpeg.exe"))
    return hits[0] if hits else "ffmpeg"


def run(*args) -> str:
    p = subprocess.run([ffmpeg(), "-hide_banner", "-y", *args], capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError(p.stderr[-2000:])
    return p.stderr


def load(path: Path, filters: str = "") -> np.ndarray:
    """Any audio file -> float32 stereo at 48 kHz (through ffmpeg)."""
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d) / "a.wav"
        run("-i", str(path), *(["-af", filters] if filters else []), "-ar", str(SR), "-ac", "2", "-c:a", "pcm_s16le", str(tmp))
        with wave.open(str(tmp)) as w:
            raw = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return (raw.reshape(-1, 2).astype(np.float32) / 32768.0)


def env(n: int, a: float, r: float, curve: float = 4.0) -> np.ndarray:
    t = np.arange(n) / SR
    att = np.clip(t / max(a, 1e-4), 0, 1)
    rel = np.exp(-curve * np.clip(t - a, 0, None) / max(r, 1e-4))
    return att * rel


def tone(f0: float, dur: float, f1: float | None = None, a: float = 0.004, r: float | None = None) -> np.ndarray:
    n = int(dur * SR)
    f = np.linspace(f0, f1 or f0, n)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * env(n, a, r or dur)


def noise(dur: float, seed: int = 0) -> np.ndarray:
    return np.random.default_rng(seed).standard_normal(int(dur * SR))


def lowpass(x: np.ndarray, k: int) -> np.ndarray:
    return np.convolve(x, np.ones(k) / k, mode="same")


def add(*parts: np.ndarray) -> np.ndarray:
    """Sum sounds of different lengths."""
    out = np.zeros(max(len(p) for p in parts))
    for p in parts:
        out[:len(p)] += p
    return out


def sfx(kind: str) -> np.ndarray:
    """Soft, modern UI sounds (mono)."""
    if kind == "pop":
        return add(0.5 * tone(880, 0.09, 520, 0.002, 0.08), 0.2 * tone(1760, 0.05, 1200, 0.001, 0.04))
    if kind == "key":                                       # a soft laptop key
        return add(0.22 * lowpass(noise(0.018, 11), 2) * env(int(0.018 * SR), 0.0004, 0.012), 0.08 * tone(3200, 0.01, 2600, 0.0003, 0.008))
    if kind == "send":                                      # message sent
        return add(0.3 * tone(620, 0.09, 940, 0.003, 0.08), 0.18 * tone(1240, 0.12, 1500, 0.004, 0.1))
    if kind == "blip":
        return 0.25 * tone(1320, 0.06, 1100, 0.002, 0.05)
    if kind == "tick":
        return add(0.35 * tone(2400, 0.035, 1800, 0.0008, 0.03), 0.15 * lowpass(noise(0.02, 1), 3) * env(int(0.02 * SR), 0.0005, 0.015))
    if kind == "click":
        return add(0.6 * tone(1600, 0.05, 900, 0.0005, 0.04), 0.25 * lowpass(noise(0.03, 2), 2) * env(int(0.03 * SR), 0.0003, 0.02))
    if kind == "confirm":
        a, b = tone(784, 0.35, None, 0.005, 0.3), tone(1175, 0.45, None, 0.005, 0.4)
        out = np.zeros(int(0.6 * SR)); out[:len(a)] += 0.35 * a; out[int(0.09 * SR):int(0.09 * SR) + len(b)] += 0.35 * b
        return out
    if kind == "card":
        w = lowpass(noise(0.32, 3), 40) * env(int(0.32 * SR), 0.12, 0.2) * 1.2
        out = np.zeros(int(0.45 * SR)); out[:len(w)] += w; p = tone(660, 0.12, 520, 0.002, 0.1); out[int(0.2 * SR):int(0.2 * SR) + len(p)] += 0.35 * p
        return out
    if kind in ("whoosh", "swish"):
        d = 0.55 if kind == "whoosh" else 0.35
        n = noise(d, 4 if kind == "whoosh" else 5)
        y = lowpass(n, 18)
        return 1.4 * y * np.sin(np.linspace(0, np.pi, len(y))) ** 2
    if kind == "hangup":
        out = np.zeros(int(0.9 * SR))
        for i, f in enumerate((660, 523, 392)):
            s = tone(f, 0.28, None, 0.005, 0.25); o = int(i * 0.2 * SR); out[o:o + len(s)] += 0.3 * s
        return out
    if kind == "join":
        out = np.zeros(int(1.0 * SR))
        for i, f in enumerate((523, 659, 784, 1047)):
            s = tone(f, 0.5, None, 0.004, 0.45); o = int(i * 0.09 * SR); out[o:o + len(s)] += 0.22 * s
        return out
    if kind == "chime":
        return add(0.3 * tone(1047, 0.9, None, 0.003, 0.85), 0.18 * tone(1568, 0.7, None, 0.003, 0.6))
    if kind == "deny":
        out = np.zeros(int(0.5 * SR)); a, b = tone(330, 0.16, 310, 0.003, 0.14), tone(247, 0.24, 235, 0.003, 0.22)
        out[:len(a)] += 0.35 * a; out[int(0.15 * SR):int(0.15 * SR) + len(b)] += 0.35 * b
        return out
    if kind == "hit":
        return add(tone(98, 0.6, 70, 0.002, 0.45) * 0.6, tone(784, 0.7, None, 0.002, 0.6) * 0.12,
                   0.12 * lowpass(noise(0.6, 6), 30) * env(int(0.6 * SR), 0.002, 0.2))
    if kind == "logo":
        out = np.zeros(int(2.6 * SR))
        for i, f in enumerate((392, 523, 659, 784, 1047)):
            s = tone(f, 2.2, None, 0.01, 2.0); o = int(i * 0.06 * SR); out[o:o + len(s)] += 0.13 * s
        return out
    raise KeyError(kind)


def place(bus: np.ndarray, clip: np.ndarray, t: float, gain: float = 1.0) -> None:
    o = int(round(t * SR))
    if clip.ndim == 1:
        clip = np.stack([clip, clip], axis=1)
    n = min(len(clip), len(bus) - o)
    if n > 0:
        bus[o:o + n] += gain * clip[:n]


def follower(x: np.ndarray, attack: float = 0.03, release: float = 0.45) -> np.ndarray:
    """Envelope of a mono signal (fast attack, slow release), computed on 10 ms blocks."""
    blk = SR // 100
    m = np.abs(x[: len(x) // blk * blk]).reshape(-1, blk).max(axis=1)
    out, e = np.zeros_like(m), 0.0
    a, r = np.exp(-0.01 / attack), np.exp(-0.01 / release)
    for i, v in enumerate(m):
        e = a * e + (1 - a) * v if v > e else r * e + (1 - r) * v
        out[i] = e
    return np.repeat(out, blk)[: len(x)] if len(out) else out


def main() -> None:
    tl = json.loads((OUT / "timeline.json").read_text(encoding="utf-8"))
    n = int((tl["duration"] + 0.5) * SR)
    vo, fx, mus = np.zeros((n, 2), np.float32), np.zeros((n, 2), np.float32), np.zeros((n, 2), np.float32)
    for c in tl["vo"]:
        call = c["key"].startswith(CALL_VOICES)
        filt = "highpass=f=170,lowpass=f=7200,aecho=0.8:0.35:24:0.12,volume=0.95" if call else "highpass=f=70,volume=1.05"
        clip = load(VO / f"{c['key']}.wav", filt)
        mono = np.abs(clip.mean(axis=1))
        active = mono[mono > 0.01]                                        # speech only, not the pauses
        rms = float(np.sqrt(np.mean(active ** 2))) if len(active) else 1.0
        place(vo, clip * ((0.15 if call else 0.12) / max(rms, 1e-4)), c["t"])   # same speaking level; the call a touch forward
    for s in tl["sfx"]:
        place(fx, sfx(s["type"]).astype(np.float32), s["t"], 0.55 * s["gain"])
    tracks = sorted(MUSIC.glob("*.mp3")) + sorted(MUSIC.glob("*.wav"))
    if tracks:
        m = load(tracks[0])
        m = np.concatenate([m, np.zeros((max(0, n - len(m)), 2), np.float32)])[:n]   # never loop: the track ends, the close is quiet
        t = np.arange(n) / SR
        fade = np.clip(t / 2.5, 0, 1) * np.clip((tl["duration"] - 0.4 - t) / 3.5, 0, 1)
        e = follower(vo.mean(axis=1))
        duck = 1 - 0.72 * np.clip(e / 0.05, 0, 1)                      # music steps back while anyone speaks
        mus = m * (0.16 * fade * duck)[:, None]
        print(f"music: {tracks[0].name}")
    else:
        print("music: none (add a licensed track to video/assets/music/)")
    mix = vo + fx + mus
    peak = np.abs(mix).max()
    mix = mix / max(peak, 1e-6) * 0.89
    pre = OUT / "mix_pre.wav"
    with wave.open(str(pre), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(mix, -1, 1) * 32767).astype(np.int16).tobytes())
    # two-pass loudness normalisation to -16 LUFS, true peak -1.5 dBTP
    log = run("-i", str(pre), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-")
    meas = json.loads(re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", log, re.S).group(0))
    run("-i", str(pre), "-af", (f"loudnorm=I=-16:TP=-1.5:LRA=11:measured_I={meas['input_i']}:measured_TP={meas['input_tp']}:"
                                f"measured_LRA={meas['input_lra']}:measured_thresh={meas['input_thresh']}:offset={meas['target_offset']}"
                                ":linear=true"), "-ar", str(SR), str(OUT / "mix.wav"))
    print(f"mix: out/mix.wav (measured {meas['input_i']} LUFS -> -16)")
    if (OUT / "video.mp4").exists():
        run("-i", str(OUT / "video.mp4"), "-i", str(OUT / "mix.wav"), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
            "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", "-shortest", str(OUT / "Max-film.mp4"))
        print("film: out/Max-film.mp4")


if __name__ == "__main__":
    main()
