"""PCM helpers for the media stand-in: Teams meeting audio is 16 kHz, 16-bit mono, 20 ms frames (640 bytes)."""

import array
import io
import struct
import wave

RATE = 16000
FRAME_SAMPLES = 320            # 20 ms at 16 kHz
FRAME_BYTES = FRAME_SAMPLES * 2
SILENCE = bytes(FRAME_BYTES)


def wav_to_pcm16k(wav_bytes: bytes) -> bytes:
    """Any PCM WAV (mono/stereo, any rate) -> 16 kHz mono s16le."""
    with wave.open(io.BytesIO(wav_bytes)) as w:
        rate, ch, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if width != 2:
        raise ValueError("only 16-bit PCM WAV is supported")
    samples = array.array("h", raw)
    if ch > 1:
        samples = array.array("h", (int(sum(samples[i:i + ch]) / ch) for i in range(0, len(samples), ch)))
    return resample(samples.tobytes(), rate, RATE)


def resample(pcm: bytes, src: int, dst: int) -> bytes:
    if src == dst:
        return pcm
    s = array.array("h", pcm)
    n_out = int(len(s) * dst / src)
    out = array.array("h", bytes(n_out * 2))
    ratio = src / dst
    last = len(s) - 1
    for i in range(n_out):
        x = i * ratio
        j = int(x)
        frac = x - j
        a = s[j] if j <= last else 0
        b = s[j + 1] if j + 1 <= last else a
        out[i] = int(a + (b - a) * frac)
    return out.tobytes()


def pcm_to_wav(pcm: bytes, rate: int = RATE) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def frames(pcm: bytes) -> list[bytes]:
    out = [pcm[i:i + FRAME_BYTES] for i in range(0, len(pcm), FRAME_BYTES)]
    if out and len(out[-1]) < FRAME_BYTES:
        out[-1] = out[-1] + bytes(FRAME_BYTES - len(out[-1]))
    return out


def rms(frame: bytes) -> float:
    s = array.array("h", frame)
    return (sum(v * v for v in s) / max(1, len(s))) ** 0.5 if s else 0.0


def pack_media(header: dict, payload: bytes) -> bytes:
    """Binary media message: 4-byte little-endian header length + JSON header + PCM payload."""
    import json
    h = json.dumps(header, separators=(",", ":")).encode()
    return struct.pack("<I", len(h)) + h + payload
