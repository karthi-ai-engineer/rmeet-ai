/*
 * Voice chat test: tap mic → record → send audio to our server → Gemini →
 * show transcript + reply as text, and drive the cloud avatar's expressions.
 */
(() => {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const micBtn = $('micBtn'), statusEl = $('status'), messagesEl = $('messages');
  const emptyEl = $('empty'), modelBadge = $('modelBadge');

  const MAX_SECONDS = 30;
  const MIN_SECONDS = 0.4;
  const TARGET_RATE = 16000;

  const avatar = CloudAvatar.create($('avatarHost'), { background: 'tint' });
  avatar.setColour('#FF6B00');
  avatar.setState('idle');

  const history = [];       // [{role: 'user'|'model', text}]
  let recorder = null;      // active recording
  let busy = false;         // waiting for Gemini / typing reply
  let maxTimer = null;
  let moodTimer = null;

  // ---------- Status ----------
  function setStatus(text, isError = false) {
    statusEl.textContent = text;
    statusEl.classList.toggle('error', isError);
  }

  // ---------- Server config ----------
  fetch('/api/config')
    .then((r) => r.json())
    .then((cfg) => {
      modelBadge.textContent = cfg.model;
      if (!cfg.hasKey) $('keyBanner').classList.add('show');
    })
    .catch(() => {
      modelBadge.textContent = 'offline';
      setStatus('Server not reachable. Start it with: python voice-chat/server.py', true);
    });

  // ---------- Audio recording (16 kHz mono WAV) ----------
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

  async function createRecorder(onLevel) {
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
    src.connect(node);
    node.connect(mute);
    mute.connect(ctx.destination);

    const chunks = [];
    let level = 0;
    node.port.onmessage = (e) => {
      const d = e.data;
      chunks.push(d);
      let sum = 0;
      for (let i = 0; i < d.length; i++) sum += d[i] * d[i];
      const rms = Math.sqrt(sum / d.length);
      level = Math.max(Math.min(1, rms * 7), level * 0.82);
      onLevel(level);
    };

    return {
      async stop() {
        src.disconnect();
        node.disconnect();
        stream.getTracks().forEach((t) => t.stop());
        const rate = ctx.sampleRate;
        await ctx.close();
        URL.revokeObjectURL(url);
        const pcm = mergeChunks(chunks);
        const down = downsample(pcm, rate, TARGET_RATE);
        return { wavBase64: toBase64(encodeWav(down, TARGET_RATE)), seconds: pcm.length / rate };
      },
    };
  }

  function mergeChunks(chunks) {
    const total = chunks.reduce((n, c) => n + c.length, 0);
    const out = new Float32Array(total);
    let off = 0;
    for (const c of chunks) { out.set(c, off); off += c.length; }
    return out;
  }

  function downsample(input, inRate, outRate) {
    if (outRate >= inRate) return input;
    const ratio = inRate / outRate;
    const outLen = Math.floor(input.length / ratio);
    const out = new Float32Array(outLen);
    for (let i = 0; i < outLen; i++) {
      const start = Math.floor(i * ratio), end = Math.min(input.length, Math.floor((i + 1) * ratio));
      let sum = 0;
      for (let j = start; j < end; j++) sum += input[j];
      out[i] = sum / Math.max(1, end - start);
    }
    return out;
  }

  function encodeWav(samples, rate) {
    const buf = new ArrayBuffer(44 + samples.length * 2);
    const v = new DataView(buf);
    const str = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
    str(0, 'RIFF'); v.setUint32(4, 36 + samples.length * 2, true); str(8, 'WAVE');
    str(12, 'fmt '); v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
    v.setUint32(24, rate, true); v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
    str(36, 'data'); v.setUint32(40, samples.length * 2, true);
    let off = 44;
    for (let i = 0; i < samples.length; i++, off += 2) {
      const s = Math.max(-1, Math.min(1, samples[i]));
      v.setInt16(off, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    }
    return new Uint8Array(buf);
  }

  function toBase64(bytes) {
    let bin = '';
    for (let i = 0; i < bytes.length; i += 0x8000) {
      bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
    }
    return btoa(bin);
  }

  // ---------- Conversation UI ----------
  function addMessage(role, text, meta) {
    emptyEl.style.display = 'none';
    const wrap = document.createElement('div');
    wrap.className = `msg ${role}`;
    const who = document.createElement('div');
    who.className = 'who';
    who.textContent = role === 'user' ? 'You' : 'Max';
    const body = document.createElement('div');
    body.className = 'text';
    body.textContent = text;
    wrap.append(who, body);
    if (meta) {
      const m = document.createElement('div');
      m.className = 'meta';
      m.textContent = meta;
      wrap.appendChild(m);
    }
    messagesEl.appendChild(wrap);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return wrap;
  }

  function typeOut(wrap, text) {
    const body = wrap.querySelector('.text');
    wrap.classList.add('typing');
    return new Promise((resolve) => {
      let i = 0;
      const tick = () => {
        i = Math.min(text.length, i + 2);
        body.textContent = text.slice(0, i);
        messagesEl.scrollTop = messagesEl.scrollHeight;
        if (i < text.length) setTimeout(tick, 35);
        else { wrap.classList.remove('typing'); resolve(); }
      };
      tick();
    });
  }

  $('clearBtn').addEventListener('click', () => {
    history.length = 0;
    messagesEl.querySelectorAll('.msg').forEach((m) => m.remove());
    emptyEl.style.display = '';
  });

  // ---------- Talk flow ----------
  function setMood(state, holdMs) {
    clearTimeout(moodTimer);
    avatar.setState(state);
    if (holdMs) {
      moodTimer = setTimeout(() => {
        if (!recorder && !busy) avatar.setState('idle');
      }, holdMs);
    }
  }

  async function startRecording() {
    if (!navigator.mediaDevices || !window.AudioWorkletNode) {
      setStatus('This browser cannot record audio. Please use Chrome or Edge.', true);
      return;
    }
    try {
      recorder = await createRecorder((lvl) => {
        avatar.setLevel(lvl);
        micBtn.style.setProperty('--lvl', lvl.toFixed(3));
      });
    } catch (err) {
      recorder = null;
      setMood('confused', 2500);
      setStatus('Microphone access was blocked. Allow the mic in the browser and try again.', true);
      return;
    }
    clearTimeout(moodTimer);
    avatar.setState('listening');
    micBtn.classList.add('recording');
    micBtn.setAttribute('aria-label', 'Stop and send');
    setStatus('Listening… tap again when you are done.');
    maxTimer = setTimeout(stopAndSend, MAX_SECONDS * 1000);
  }

  async function stopAndSend() {
    clearTimeout(maxTimer);
    if (!recorder) return;
    const rec = recorder;
    recorder = null;
    micBtn.classList.remove('recording');
    micBtn.setAttribute('aria-label', 'Start talking');
    micBtn.style.setProperty('--lvl', '0');
    avatar.setLevel(0);

    const { wavBase64, seconds } = await rec.stop();
    if (seconds < MIN_SECONDS) {
      setMood('confused', 1800);
      setStatus('That was too short. Tap, speak, then tap again.');
      return;
    }

    busy = true;
    micBtn.disabled = true;
    avatar.setState('thinking');
    setStatus('Thinking…');

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ audio: wavBase64, mimeType: 'audio/wav', history: history.slice(-10) }),
      });
      let data = {};
      try { data = await res.json(); } catch (_) { /* non-JSON error */ }
      if (!res.ok) throw new Error(data.error || `Server error ${res.status}`);

      addMessage('user', data.transcript || '(Max could not make out any words)');
      const botMsg = addMessage('bot', '', `${data.model} · ${(data.latencyMs / 1000).toFixed(1)}s`);
      avatar.setState('speaking');
      setStatus('Max is replying…');
      await typeOut(botMsg, data.reply || '…');

      if (data.transcript) history.push({ role: 'user', text: data.transcript });
      if (data.reply) history.push({ role: 'model', text: data.reply });

      const mood = data.emotion && data.emotion !== 'idle' ? data.emotion : 'happy';
      busy = false;
      setMood(mood, 2200);
      setStatus('Tap the mic to talk again.');
    } catch (err) {
      busy = false;
      setMood('confused', 3000);
      setStatus(err.message || 'Something went wrong.', true);
    } finally {
      busy = false;
      micBtn.disabled = false;
    }
  }

  let starting = false;
  async function toggle() {
    if (busy || starting) return;
    if (recorder) { stopAndSend(); return; }
    starting = true;
    try { await startRecording(); } finally { starting = false; }
  }

  micBtn.addEventListener('click', toggle);
  window.addEventListener('keydown', (e) => {
    if (e.code === 'Space' && !e.repeat && e.target === document.body) {
      e.preventDefault();
      toggle();
    }
  });
})();
