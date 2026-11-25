/*
 * Microphone recorder → 16 kHz mono WAV (base64). Used for "speak as Karthi".
 *   const rec = await MicRecorder.start(level => ...);
 *   const { wavBase64, seconds } = await rec.stop();
 */
(function () {
  'use strict';
  const TARGET_RATE = 16000;
  const WORKLET = `
    class PcmCapture extends AudioWorkletProcessor {
      constructor() { super(); this.buf = new Float32Array(2048); this.n = 0; }
      process(inputs) {
        const ch = inputs[0] && inputs[0][0];
        if (ch) {
          for (let i = 0; i < ch.length; i++) {
            this.buf[this.n++] = ch[i];
            if (this.n === this.buf.length) { this.port.postMessage(this.buf.slice(0)); this.n = 0; }
          }
        }
        return true;
      }
    }
    registerProcessor('pcm-capture', PcmCapture);`;

  async function start(onLevel) {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
    const ctx = new AudioContext();
    const url = URL.createObjectURL(new Blob([WORKLET], { type: 'application/javascript' }));
    await ctx.audioWorklet.addModule(url);
    const src = ctx.createMediaStreamSource(stream);
    const node = new AudioWorkletNode(ctx, 'pcm-capture');
    const mute = ctx.createGain();
    mute.gain.value = 0;
    src.connect(node); node.connect(mute); mute.connect(ctx.destination);

    const chunks = [];
    let level = 0;
    node.port.onmessage = (e) => {
      const d = e.data;
      chunks.push(d);
      let sum = 0;
      for (let i = 0; i < d.length; i++) sum += d[i] * d[i];
      level = Math.max(Math.min(1, Math.sqrt(sum / d.length) * 7), level * 0.82);
      if (onLevel) onLevel(level);
    };

    return {
      async stop() {
        src.disconnect(); node.disconnect();
        stream.getTracks().forEach((t) => t.stop());
        const rate = ctx.sampleRate;
        await ctx.close();
        URL.revokeObjectURL(url);
        const pcm = merge(chunks);
        return { wavBase64: toBase64(encodeWav(downsample(pcm, rate, TARGET_RATE), TARGET_RATE)), seconds: pcm.length / rate };
      },
    };
  }

  function merge(chunks) {
    const out = new Float32Array(chunks.reduce((n, c) => n + c.length, 0));
    let off = 0;
    for (const c of chunks) { out.set(c, off); off += c.length; }
    return out;
  }
  function downsample(input, inRate, outRate) {
    if (outRate >= inRate) return input;
    const ratio = inRate / outRate, outLen = Math.floor(input.length / ratio), out = new Float32Array(outLen);
    for (let i = 0; i < outLen; i++) {
      const s = Math.floor(i * ratio), e = Math.min(input.length, Math.floor((i + 1) * ratio));
      let sum = 0;
      for (let j = s; j < e; j++) sum += input[j];
      out[i] = sum / Math.max(1, e - s);
    }
    return out;
  }
  function encodeWav(samples, rate) {
    const buf = new ArrayBuffer(44 + samples.length * 2), v = new DataView(buf);
    const str = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
    str(0, 'RIFF'); v.setUint32(4, 36 + samples.length * 2, true); str(8, 'WAVE'); str(12, 'fmt ');
    v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true); v.setUint32(24, rate, true);
    v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
    str(36, 'data'); v.setUint32(40, samples.length * 2, true);
    for (let i = 0, off = 44; i < samples.length; i++, off += 2) {
      const s = Math.max(-1, Math.min(1, samples[i]));
      v.setInt16(off, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    }
    return new Uint8Array(buf);
  }
  function toBase64(bytes) {
    let bin = '';
    for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
    return btoa(bin);
  }

  window.MicRecorder = { start };
})();
