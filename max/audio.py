"""PCM helpers. Teams meeting media is 16 kHz, 16-bit mono, sent and received in 20 ms frames (640 bytes)."""

import array
import io
import struct
import wave

RATE = 16000
FRAME_BYTES = 640


def wav_to_pcm16k(wav_bytes: bytes) -> bytes:
    with wave.open(io.BytesIO(wav_bytes)) as w:
        rate, ch, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if width != 2:
        raise ValueError("only 16-bit PCM WAV is supported")
    s = array.array("h", raw)
    if ch > 1:
        s = array.array("h", (int(sum(s[i:i + ch]) / ch) for i in range(0, len(s), ch)))
    if rate == RATE:
        return s.tobytes()
    n_out = int(len(s) * RATE / rate)
    out = array.array("h", bytes(n_out * 2))
    ratio, last = rate / RATE, len(s) - 1
    for i in range(n_out):
        x = i * ratio
        j = int(x)
        a = s[j] if j <= last else 0
        b = s[j + 1] if j + 1 <= last else a
        out[i] = int(a + (b - a) * (x - j))
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
        out[-1] += bytes(FRAME_BYTES - len(out[-1]))
    return out


def unpack_media(msg: bytes) -> tuple[dict, bytes]:
    """Media frame: 4-byte LE header length + JSON header + PCM payload."""
    import json
    n = struct.unpack("<I", msg[:4])[0]
    return json.loads(msg[4:4 + n]), msg[4 + n:]
