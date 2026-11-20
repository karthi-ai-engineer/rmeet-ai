/* rmeet-ai front end: team channel + live simulated meeting. */
(() => {
  'use strict';

  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const ORDER = ['karthi', 'prince', 'daniel', 'jacob', 'max'];
  const CLOUD = '<svg viewBox="0 0 40 40" style="width:78%;height:78%;stroke:none"><g fill="#FF6B00"><circle cx="20" cy="22" r="11"/><circle cx="11" cy="24" r="7"/><circle cx="29" cy="24" r="7"/><circle cx="15" cy="15" r="7"/><circle cx="25" cy="13" r="8"/></g><rect x="15.5" y="18" width="3" height="6" rx="1.5" fill="#fff"/><rect x="22" y="18" width="3" height="6" rx="1.5" fill="#fff"/></svg>';

  let W = null;                 // world data from /api/world
  let meetingStatus = 'lobby';
  let notes = null, scoreResult = null, notesPosted = false;
  let t0 = null, timerId = null;
  let speed = 1;
  let maxThinking = false;
  let speechToken = 0;
  let pendingTurn = null;
  const avatars = {};
  const moodTimers = {};

  // ------------------------------------------------------------ helpers
  const member = (id) => (W && W.members[id]) || { name: id, colour: '#888', role: '' };
  const first = (id) => (id === 'max' ? 'Max' : member(id).name.split(' ')[0]);
  const initials = (n) => n.split(/\s+/).map((p) => p[0]).join('').slice(0, 2).toUpperCase();
  const tagColour = (id) => (id === 'karthi' ? '#5B5B66' : member(id).colour);
  // Channel times are the team's wall clock stored "as UTC", so format in UTC to show them unchanged.
  const fmtTime = (iso) => new Date(/Z$|[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: 'UTC' });
  const fmtDate = (iso) => new Date(/Z$|[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' });
  const extOf = (n) => (n.split('.').pop() || '').toLowerCase();
  const FLABEL = { xlsx: 'XLS', pdf: 'PDF', docx: 'DOC', md: 'MD' };
  const ficon = (name) => `<span class="ficon ${extOf(name)}">${FLABEL[extOf(name)] || 'FILE'}</span>`;

  function pavatar(id, sm = false) {
    if (id === 'max') return `<div class="pavatar ${sm ? 'sm' : ''}" style="background:#FFF1E6">${CLOUD}</div>`;
    return `<div class="pavatar ${sm ? 'sm' : ''}" style="background:${tagColour(id)}">${esc(initials(member(id).name))}</div>`;
  }

  let toastTimer;
  function toast(msg, isErr = false) {
    const t = $('#toast');
    t.textContent = msg;
    t.classList.toggle('err', isErr);
    t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { t.hidden = true; }, isErr ? 7000 : 3500);
  }

  async function api(path, body) {
    const res = await fetch(path, body === undefined ? {} : {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    });
    let data = {};
    try { data = await res.json(); } catch (_) { /* empty */ }
    if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
    return data;
  }

  // Minimal markdown → HTML (headings, tables, lists, bold, hr, paragraphs)
  function md(src) {
    const inline = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/`(.+?)`/g, '<code>$1</code>');
    const lines = src.replace(/\r/g, '').split('\n');
    let html = '', i = 0, para = [];
    const flush = () => { if (para.length) { html += `<p>${para.map(inline).join(' ')}</p>`; para = []; } };
    while (i < lines.length) {
      const l = lines[i];
      if (/^\s*\|/.test(l)) {
        flush();
        const rows = [];
        while (i < lines.length && /^\s*\|/.test(lines[i])) { rows.push(lines[i]); i++; }
        const cells = (r) => r.trim().replace(/^\||\|$/g, '').split('|').map((c) => c.trim());
        const body = rows.filter((r) => !/^\s*\|\s*:?-{2,}/.test(r));
        html += '<table>' + body.map((r, ri) => '<tr>' + cells(r).map((c) => (ri === 0 ? `<th>${inline(c)}</th>` : `<td>${inline(c)}</td>`)).join('') + '</tr>').join('') + '</table>';
        continue;
      }
      let m;
      if ((m = l.match(/^(#{1,3})\s+(.*)/))) { flush(); html += `<h${m[1].length}>${inline(m[2])}</h${m[1].length}>`; }
      else if (/^---+\s*$/.test(l)) { flush(); html += '<hr>'; }
      else if (/^\s*[-*]\s+/.test(l)) {
        flush();
        html += '<ul>';
        while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) { html += `<li>${inline(lines[i].replace(/^\s*[-*]\s+/, ''))}</li>`; i++; }
        html += '</ul>';
        continue;
      } else if (!l.trim()) flush();
      else para.push(l);
      i++;
    }
    flush();
    return `<div class="md">${html}</div>`;
  }

  // ------------------------------------------------------------ channel
  function renderModels() {
    const m = W.models;
    $('#modelInfo').innerHTML =
      `<div><span class="dot" style="background:${m.qwenReady ? '#1D9E57' : '#D93025'}"></span>Brain: <b>${esc(m.brain)}</b></div>` +
      `<div><span class="dot" style="background:${m.geminiReady ? '#1D9E57' : '#D93025'}"></span>Hearing: <b>${esc(m.hearing)}</b></div>`;
  }

  function renderMeetingCard() {
    const mt = W.meeting;
    const live = meetingStatus === 'live' || meetingStatus === 'summarizing';
    $('#meetingCard').innerHTML = `
      <div class="mc-icon">📅</div>
      <div class="mc-text">
        <div class="mc-title">${esc(mt.title)}</div>
        <div class="mc-sub">${live ? '🔴 In progress' : 'Today · Fri 20 Nov · 10:00 to 10:30'} · Karthi, Prince, Daniel, Jacob + Max (AI)</div>
      </div>
      <button class="btn primary" data-join>${live ? 'Rejoin' : meetingStatus === 'ended' ? 'Run again' : 'Join'}</button>`;
  }

  // ------------------------------------------------------------ channel (live, from the fake Teams store)
  let CH = { posts: [], install: { installed: false }, app: null };
  const typingTimers = {};
  const PERM_TEXT = {
    'ChannelMessage.Read.Group': "Read this team's channel messages",
    'TeamMember.Read.Group': "Read this team's members",
    'ChannelSettings.Read.Group': "Read this team's channel names and settings",
    'TeamSettings.Read.Group': "Read this team's settings",
    'File.Read.Group': "Read this team's files",
  };
  const MENTIONABLE = () => [
    ...(CH.install.installed ? [{ id: 'max', name: 'Max', sub: 'App · AI teammate' }] : []),
    ...['prince', 'daniel', 'jacob', 'karthi'].map((id) => ({ id, name: member(id).name, sub: member(id).role })),
  ];

  // Highlight @Name mentions of known people/apps.
  function mentionify(escapedHtml) {
    const names = ['Max', ...['karthi', 'prince', 'daniel', 'jacob'].map((id) => member(id).name)];
    names.sort((a, b) => b.length - a.length);
    let out = escapedHtml;
    names.forEach((n) => {
      const rx = new RegExp(`@${n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'g');
      out = out.replace(rx, `<span class="mention">@${n}</span>`);
    });
    return out;
  }

  // Markdown-lite for bot messages (bold, italic, bullets, paragraphs).
  function mdLite(text) {
    const lines = esc(text).split('\n');
    let html = '', list = false, para = [];
    const inline = (s) => mentionify(s).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/(^|[^*])\*(?!\s)(.+?)\*/g, '$1<i>$2</i>');
    const flush = () => { if (para.length) { html += `<p>${para.map(inline).join('<br>')}</p>`; para = []; } };
    lines.forEach((l) => {
      if (/^\s*[-*•]\s+/.test(l)) { flush(); if (!list) { html += '<ul>'; list = true; } html += `<li>${inline(l.replace(/^\s*[-*•]\s+/, ''))}</li>`; return; }
      if (list) { html += '</ul>'; list = false; }
      if (!l.trim()) flush(); else para.push(l);
    });
    if (list) html += '</ul>';
    flush();
    return html;
  }

  function msgBody(m) {
    if (m.deleted) return '<div class="post-text"><span class="deleted">This message has been deleted.</span></div>';
    const body = m.isBot && m.textFormat !== 'plain' ? `<div class="post-text md">${mdLite(m.text)}</div>`
      : `<div class="post-text">${mentionify(esc(m.text))}</div>`;
    const cards = (m.cards || []).map((c) => `<pre class="card-json">${esc(JSON.stringify(c, null, 1)).slice(0, 600)}</pre>`).join('');
    return body.replace(/<\/div>$/, `${m.edited ? '<span class="edited">(edited)</span>' : ''}</div>`) + cards;
  }

  function nameOf(m) { return m.isBot ? 'Max' : member(m.author).name; }

  function postHtml(p) {
    const chips = (p.attachments || []).map((a) =>
      `<button class="file-chip" data-path="${esc(a.path)}" data-name="${esc(a.name)}">${ficon(a.name)}<span class="fn">${esc(a.name)}</span></button>`).join('');
    const counts = {};
    (p.reactions || []).forEach((r) => { (counts[r.emoji] = counts[r.emoji] || []).push(member(r.user).name); });
    const reacts = Object.entries(counts).map(([e, who]) => `<span class="reaction" title="${esc(who.join(', '))}">${e} ${who.length}</span>`).join('');
    const replies = (p.replies || []).map((r) => `
      <div class="reply" data-id="${esc(r.id)}">${pavatar(r.isBot ? 'max' : r.author, true)}
        <div class="post-body"><div class="post-meta"><b>${esc(nameOf(r))}</b>${r.isBot ? '<span class="bot-badge">BOT</span>' : ''}<time>${fmtTime(r.time)}</time></div>
        ${msgBody(r)}</div></div>`).join('');
    const role = p.isBot ? '<span class="bot-badge">BOT</span>' : `<span class="role">${esc(member(p.author).role || '')}</span>`;
    const meetingChip = p.meeting ? `<div class="meeting-chip">📅 ${esc(p.meeting.title)} ·
      ${p.meeting.state === 'live' ? '<span class="live">● Live now</span> <button class="btn primary" data-join>Join</button>'
        : '<span class="ended">Ended · notes and transcript below</span>'}</div>` : '';
    return `<article class="post ${p.isBot ? 'bot' : ''} ${p.meeting ? 'meeting-post' : ''}" data-id="${esc(p.id)}">
      <div class="post-main">${pavatar(p.isBot ? 'max' : p.author)}
        <div class="post-body">
          <div class="post-meta"><b>${esc(nameOf(p))}</b>${role}<time>${fmtTime(p.time)}</time></div>
          ${msgBody(p)}
          ${meetingChip}
          ${chips ? `<div class="chips">${chips}</div>` : ''}
          ${reacts ? `<div class="reactions">${reacts}</div>` : ''}
        </div>
      </div>
      <div class="replies" ${replies ? '' : 'hidden'}>${replies}</div>
      <div class="typing" hidden><span class="dots"><span></span><span></span><span></span></span> Max is typing…</div>
      <div class="reply-actions"><button class="reply-btn" data-reply="${esc(p.id)}">↩ Reply</button></div>
    </article>`;
  }

  function renderPosts(scrollToEnd = false) {
    $('#posts').innerHTML = CH.posts.map(postHtml).join('');
    renderInstallState();
    if (scrollToEnd) {
      const pane = $('#pane-posts');
      const toEnd = () => { pane.scrollTop = pane.scrollHeight; };
      toEnd();
      setTimeout(toEnd, 60);
      setTimeout(toEnd, 400);
    }
  }

  function renderInstallState() {
    const inst = CH.install.installed;
    $('#appsLabel').innerHTML = inst ? 'Max <span class="chip-ok"></span>' : 'Apps';
    const banner = $('#installBanner');
    banner.hidden = inst;
    if (!inst) {
      banner.innerHTML = `<div class="app-icon">${CLOUD}</div>
        <div class="ib-text"><b>Add Max to this team</b><span class="muted">Max reads the channel through Microsoft Graph, answers @Max in threads and joins your meetings.</span></div>
        <button class="btn primary" data-open-app>Add Max</button>`;
    }
  }

  async function loadChannel(scroll = false) {
    try {
      CH = await api('/api/channel');
      renderPosts(scroll);
      renderFiles();
    } catch (e) {
      toast(`Could not load the channel: ${e.message}`, true);
    }
  }

  function onChannelEvent(ev) {
    const pane = $('#pane-posts');
    const nearBottom = pane.scrollHeight - pane.scrollTop - pane.clientHeight < 160;
    if (ev.type === 'message') {
      const m = ev.message;
      if (m.rootId) {
        const root = CH.posts.find((p) => p.id === m.rootId);
        if (root && !root.replies.some((r) => r.id === m.id)) root.replies.push(m);
        if (m.isBot) stopTyping(m.rootId);
      } else if (!CH.posts.some((p) => p.id === m.id)) {
        CH.posts.push({ ...m, replies: [] });
      }
      renderPosts(nearBottom || (!m.rootId && m.isBot));
    } else if (ev.type === 'message_updated' || ev.type === 'message_deleted') {
      loadChannel();
    } else if (ev.type === 'typing') {
      showTyping(ev.rootId);
    } else if (ev.type === 'install') {
      CH.install = ev.install;
      renderInstallState();
      toast(ev.install.installed ? 'Max was added to Planning Department. It is reading the channel…' : 'Max was removed from the team.');
    } else if (ev.type === 'reset') {
      loadChannel(true);
    } else if (ev.type === 'bot_error') {
      toast(ev.message, true);
    } else if (ev.type === 'file') {
      loadChannel();
    } else if (ev.type === 'admin' || ev.type === 'subscriptions' || ev.type === 'notification_log') {
      if (ev.type === 'subscriptions' && ev.reason) toast(`Subscriptions removed: ${ev.reason}`);
      refreshAdmin();
    }
  }

  function showTyping(rootId) {
    const el = $(`.post[data-id="${CSS.escape(rootId || '')}"] .typing`);
    if (!el) return;
    el.hidden = false;
    clearTimeout(typingTimers[rootId]);
    typingTimers[rootId] = setTimeout(() => stopTyping(rootId), 60000);
  }
  function stopTyping(rootId) {
    clearTimeout(typingTimers[rootId]);
    const el = $(`.post[data-id="${CSS.escape(rootId || '')}"] .typing`);
    if (el) el.hidden = true;
  }

  function connectChannel() {
    const es = new EventSource('/api/channel/events');
    es.onmessage = (msg) => onChannelEvent(JSON.parse(msg.data));
    es.onerror = () => { /* EventSource reconnects by itself */ };
  }

  async function postToChannel(text, rootId) {
    text = (text || '').trim();
    if (!text) return false;
    try {
      await api('/api/channel/post', { text, rootId: rootId || null });
      return true;
    } catch (e) {
      toast(e.message, true);
      return false;
    }
  }

  function openReplyBox(rootId) {
    const post = $(`.post[data-id="${CSS.escape(rootId)}"]`);
    if (!post) return;
    let box = post.querySelector('.reply-box');
    if (!box) {
      box = document.createElement('div');
      box.className = 'reply-box';
      box.innerHTML = `<input type="text" placeholder="Reply… (type @ to mention Max)"><button class="btn primary">Send</button>`;
      post.querySelector('.reply-actions').appendChild(box);
      const input = box.querySelector('input');
      const send = async () => { if (await postToChannel(input.value, rootId)) input.value = ''; };
      box.querySelector('button').addEventListener('click', send);
      input.addEventListener('keydown', (e) => { if (e.key === 'Enter' && $('#mentionPop').hidden) { e.preventDefault(); send(); } });
      attachMentions(input);
    }
    box.querySelector('input').focus();
  }

  // ---- @mention suggestions (like the Teams compose box) ----
  let mentionTarget = null, mentionSel = 0;
  function attachMentions(el) {
    el.addEventListener('input', () => updateMentionPop(el));
    el.addEventListener('keydown', (e) => {
      const pop = $('#mentionPop');
      if (pop.hidden) return;
      const items = $$('button', pop);
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        mentionSel = (mentionSel + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
        items.forEach((b, i) => b.classList.toggle('sel', i === mentionSel));
      } else if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        items[mentionSel]?.click();
      } else if (e.key === 'Escape') {
        pop.hidden = true;
      }
    });
    el.addEventListener('blur', () => setTimeout(() => { $('#mentionPop').hidden = true; }, 150));
  }

  function updateMentionPop(el) {
    const pop = $('#mentionPop');
    const upto = el.value.slice(0, el.selectionStart);
    const m = upto.match(/(^|\s)@([\w ]{0,20})$/);
    if (!m) { pop.hidden = true; return; }
    const q = m[2].toLowerCase();
    const items = MENTIONABLE().filter((p) => p.name.toLowerCase().startsWith(q) || p.name.toLowerCase().includes(q));
    if (!items.length) { pop.hidden = true; return; }
    mentionTarget = el;
    mentionSel = 0;
    pop.innerHTML = items.map((p, i) => `<button type="button" class="${i === 0 ? 'sel' : ''}" data-name="${esc(p.name)}">
      ${pavatar(p.id, true)}<span><div>${esc(p.name)}</div><div class="sub">${esc(p.sub || '')}</div></span></button>`).join('');
    $$('button', pop).forEach((b) => b.addEventListener('mousedown', (e) => {
      e.preventDefault();
      const before = mentionTarget.value.slice(0, mentionTarget.selectionStart).replace(/@([\w ]{0,20})$/, `@${b.dataset.name} `);
      const after = mentionTarget.value.slice(mentionTarget.selectionStart);
      mentionTarget.value = before + after;
      mentionTarget.selectionStart = mentionTarget.selectionEnd = before.length;
      pop.hidden = true;
      mentionTarget.focus();
    }));
    const r = el.getBoundingClientRect();
    pop.hidden = false;
    pop.style.left = `${Math.max(8, r.left)}px`;
    pop.style.top = `${Math.max(8, r.top - pop.offsetHeight - 6)}px`;
  }

  // ---- Apps: add / remove Max (consent screen with RSC permissions) ----
  function openAppModal() {
    const app = CH.app;
    const inst = CH.install.installed;
    $('#appIcon').innerHTML = CLOUD;
    if (!app) {
      $('#appName').textContent = 'No apps uploaded';
      $('#appMeta').textContent = '';
      $('#appDesc').innerHTML = 'Register Max first: run <code>.venv\\Scripts\\python simulations\\teams\\register_app.py</code> and restart rmeet-ai.';
      $('#appPerms').innerHTML = '';
      $('#permTitle').hidden = true;
      $('#appAddBtn').hidden = true;
      $('#appRemoveBtn').hidden = true;
      $('#appNote').textContent = '';
    } else {
      $('#appName').textContent = app.fullName;
      $('#appMeta').textContent = `Built for your org · version ${app.version} · app id ${app.id.slice(0, 8)}…`;
      $('#appDesc').textContent = app.description;
      $('#permTitle').hidden = false;
      $('#permTitle').textContent = inst ? 'Granted in this team:' : 'This app will be able to (in this team only):';
      $('#appPerms').innerHTML = app.rsc.map((p) => `<li>${esc(PERM_TEXT[p] || p)}<code>${esc(p)}</code></li>`).join('');
      $('#appNote').textContent = 'Resource-specific consent: the team owner approves these for this team only, no tenant-wide admin consent needed.';
      $('#appAddBtn').hidden = inst;
      $('#appRemoveBtn').hidden = !inst;
    }
    openModal('#appModal');
  }

  async function setInstalled(add) {
    try {
      await api('/api/channel/install', { action: add ? 'add' : 'remove' });
      closeModals();
    } catch (e) {
      toast(e.message, true);
    }
  }

  function renderFiles() {
    const files = (CH.files || []).slice().sort((a, b) => a.name.localeCompare(b.name));
    $('#files').innerHTML = `<div class="frow head"><div>Name</div><div>Modified by</div><div>Modified</div></div>` +
      files.map((f) => `<div class="frow" data-path="${esc(f.path)}" data-name="${esc(f.name)}">
        <div class="fname">${ficon(f.name)}<span>${esc(f.name)}</span>${f.version > 1 ? `<span class="fver">v${f.version}</span>` : ''}</div>
        <div class="fauthor">${esc(member(f.author).name)}</div><div class="fdate">${fmtDate(f.time)}</div></div>`).join('');
  }

  async function uploadFile(file) {
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) { toast('Files up to 10 MB in the simulator.', true); return; }
    const data = await new Promise((res, rej) => {
      const r = new FileReader();
      r.onload = () => res(String(r.result).split(',')[1] || '');
      r.onerror = rej;
      r.readAsDataURL(file);
    });
    try {
      const out = await api('/api/channel/upload', { name: file.name, data });
      toast(`${out.change === 'updated' ? 'Updated' : 'Uploaded'} ${out.name} in the channel files.`);
    } catch (e) {
      toast(e.message, true);
    }
  }

  // ---- Admin center (Entra admin consent + Teams admin settings + Graph subscriptions) ----
  const ADMIN_TEXT = {
    'Calendars.Read': 'Read calendars in all mailboxes (to find the team\'s Teams meetings)',
    'OnlineMeetings.Read.All': 'Read online meeting details',
    'OnlineMeetingTranscript.Read.All': 'Read all transcripts of online meetings',
  };
  let adminOpen = false;

  async function openAdmin() {
    adminOpen = true;
    openModal('#adminModal');
    await refreshAdmin();
  }

  async function refreshAdmin() {
    if (!adminOpen || $('#adminModal').hidden) { adminOpen = false; return; }
    let d;
    try { d = await api('/api/admin'); } catch (e) { $('#adminBody').innerHTML = `<p>${esc(e.message)}</p>`; return; }
    const a = d.admin;
    const consented = (d.requiredPermissions || []).every((p) => a.consented.includes(p)) && d.requiredPermissions.length;
    const pill = (on, yes = 'On', no = 'Off') => `<span class="pill ${on ? 'on' : 'off'}">${on ? yes : no}</span>`;
    $('#adminBody').innerHTML = `
      <h3>Microsoft Entra ID · Enterprise app "${esc(d.appName || 'Max')}" · API permissions</h3>
      <div class="admin-row"><div class="ar-text"><b>Tenant-wide Microsoft Graph application permissions</b>
        ${(d.requiredPermissions || []).map((p) => `<div>${esc(ADMIN_TEXT[p] || p)} <code>${esc(p)}</code></div>`).join('') || '<div class="muted">No app registered</div>'}
        <div class="muted small">Team-level permissions (channel messages, files, members) are granted by the team owner when adding the app (RSC).</div></div>
        ${pill(consented, 'Granted', 'Not granted')}
        <button class="btn ${consented ? '' : 'primary'}" data-admin="consent" data-val="${consented ? 0 : 1}">${consented ? 'Revoke' : 'Grant admin consent for Kestrel Home Goods'}</button></div>

      <h3>Teams admin · meetings</h3>
      <div class="admin-row"><div class="ar-text"><b>Application access policy</b>
        <code>New-CsApplicationAccessPolicy -Identity Max-policy -AppIds "${esc((CH.app || {}).id || '')}"; Grant-CsApplicationAccessPolicy -PolicyName Max-policy -Global</code>
        <div class="muted small">Required for apps to read online meetings and transcripts with application permissions.</div></div>
        ${pill(a.accessPolicy, 'Assigned', 'Not assigned')}
        <button class="btn" data-admin="accessPolicy" data-val="${a.accessPolicy ? 0 : 1}">${a.accessPolicy ? 'Remove' : 'Assign globally'}</button></div>
      <div class="admin-row"><div class="ar-text"><b>Graph API access to transcripts</b>
        <div class="muted small">Tenant switch, off by default. When off, every transcript API call returns 403 GraphAccessToTranscriptsDisabled.</div></div>
        ${pill(a.transcriptApiAccess)}
        <button class="btn" data-admin="transcriptApiAccess" data-val="${a.transcriptApiAccess ? 0 : 1}">${a.transcriptApiAccess ? 'Turn off' : 'Turn on'}</button></div>

      <h3>Microsoft Graph · change notification subscriptions</h3>
      <table class="admin-table"><tr><th>Resource</th><th>Changes</th><th>Expires in</th></tr>
        ${(d.subscriptions || []).map((s) => `<tr><td><code>${esc(s.resource)}</code></td><td>${esc(s.changeType)}</td><td>${Math.floor(s.minutesLeft / 60)} h ${s.minutesLeft % 60} min</td></tr>`).join('') || '<tr><td colspan="3" class="muted">No subscriptions yet</td></tr>'}
      </table>
      <div style="margin-top:8px"><button class="btn" data-admin="removeSubs">Simulate "subscriptionRemoved"</button>
        <span class="muted small">Graph removes the subscriptions and sends lifecycle events; Max should resubscribe and resync.</span></div>

      <h3>Recent notifications delivered to Max</h3>
      <table class="admin-table"><tr><th>Time</th><th>What</th><th>Max answered</th></tr>
        ${(d.log || []).slice().reverse().map((l) => `<tr><td>${esc(l.time)}</td><td>${esc(l.what)}</td><td class="${/^2/.test(l.status) ? 'st-ok' : 'st-bad'}">${esc(l.status)}</td></tr>`).join('') || '<tr><td colspan="3" class="muted">Nothing delivered yet</td></tr>'}
      </table>`;
  }

  async function adminAction(kind, val) {
    try {
      if (kind === 'removeSubs') {
        const r = await api('/api/admin/remove-subscriptions', {});
        toast(`Removed ${r.removed} subscription(s). Max was notified.`);
      } else {
        await api('/api/admin', { [kind]: val === '1' });
      }
      refreshAdmin();
    } catch (e) {
      toast(e.message, true);
    }
  }

  function renderMeetingsTab() {
    const past = W.meetings.map((m) => {
      const d = new Date(m.date + 'T10:00:00');
      return `<div class="mitem">
        <div class="mdate"><b>${d.getDate()}</b><span>${d.toLocaleString('en-US', { month: 'short' })}</span></div>
        <div class="minfo"><div>${esc(m.title)}</div><div>Planning sync · transcript and minutes</div></div>
        <div class="mbtns"><button class="btn" data-meeting="${esc(m.id)}" data-view="minutes">Minutes</button>
        <button class="btn" data-meeting="${esc(m.id)}" data-view="transcript">Transcript</button></div></div>`;
    }).join('');
    $('#mlist').innerHTML = `<div class="mitem upcoming">
        <div class="mdate"><b>20</b><span>Nov</span></div>
        <div class="minfo"><div>${esc(W.meeting.title)}</div><div>Today 10:00 · with Max (AI)</div></div>
        <div class="mbtns"><button class="btn primary" data-join>Join</button></div></div>` + past;
  }

  function switchTab(name) {
    $$('.tab').forEach((t) => t.classList.toggle('active', t.dataset.tab === name));
    $$('.pane').forEach((p) => p.classList.toggle('active', p.id === `pane-${name}`));
  }

  // ------------------------------------------------------------ viewers
  function openModal(id) { $(id).hidden = false; }
  function closeModals() { $$('.modal').forEach((m) => { m.hidden = true; }); }

  async function openDoc(path, name) {
    $('#viewerTitle').textContent = name;
    $('#viewerTabs').innerHTML = '';
    const isDrive = path.startsWith('drive:');
    $('#viewerOpen').href = isDrive ? `/api/drive-file?item=${encodeURIComponent(path.slice(6))}` : `/world/${path}`;
    $('#viewerOpen').hidden = false;
    $('#viewerBody').innerHTML = '<p class="muted">Loading…</p>';
    openModal('#viewer');
    try {
      const d = await api(isDrive ? `/api/drive-doc?item=${encodeURIComponent(path.slice(6))}`
        : `/api/doc?path=${encodeURIComponent(path)}`);
      $('#viewerBody').innerHTML = extOf(name) === 'md' ? md(d.text)
        : `<p class="muted">Text preview. Use “Open file” for the original ${extOf(name).toUpperCase()}.</p><pre>${esc(d.text)}</pre>`;
    } catch (e) {
      $('#viewerBody').innerHTML = `<p>${esc(e.message)}</p>`;
    }
  }

  async function openPastMeeting(id, view) {
    const m = W.meetings.find((x) => x.id === id);
    $('#viewerTitle').textContent = m.title;
    $('#viewerOpen').hidden = true;
    const load = async (which) => {
      $$('#viewerTabs button').forEach((b) => b.classList.toggle('primary', b.dataset.v === which));
      $('#viewerBody').innerHTML = '<p class="muted">Loading…</p>';
      const d = await api(`/api/doc?path=${encodeURIComponent(m[which])}`);
      $('#viewerBody').innerHTML = md(d.text);
    };
    $('#viewerTabs').innerHTML = '<button class="btn" data-v="minutes">Minutes</button><button class="btn" data-v="transcript">Transcript</button>';
    $$('#viewerTabs button').forEach((b) => b.addEventListener('click', () => load(b.dataset.v)));
    openModal('#viewer');
    load(view);
  }

  // ------------------------------------------------------------ prejoin
  function openPrejoin() {
    if (meetingStatus === 'live' || meetingStatus === 'summarizing') {
      showMeeting();
      return;
    }
    $('#pjTitle').textContent = `${W.meeting.title} · Planning Department`;
    $('#lastNotesBtn').hidden = !(meetingStatus === 'ended' && notes);
    const warn = [];
    if (!W.models.qwenReady) warn.push('Qwen is not configured (TW_API_KEY / TW_BASE_URL). The colleagues and Max cannot talk.');
    if (!W.models.geminiReady) warn.push('Gemini is not configured, so the mic won\'t work. You can still type.');
    if (!CH.install.installed) warn.push('Max isn\'t in this team yet, so it won\'t join. Close this and click "Add Max" in the channel first.');
    $('#pjWarn').hidden = !warn.length;
    $('#pjWarn').innerHTML = warn.map(esc).join('<br>');
    openModal('#prejoin');
  }

  // ------------------------------------------------------------ meeting audio
  let media = 'voice';
  let audioCtx = null, maxPlayAt = 0, currentClip = null;
  function ensureAudio() {
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    if (audioCtx.state === 'suspended') audioCtx.resume();
  }
  function playClip(url) {
    if (currentClip) { currentClip.pause(); currentClip = null; }
    const a = new Audio(url);
    currentClip = a;
    a.play().catch(() => toast('Click anywhere on the page to allow audio playback.'));
  }
  // Max's voice arrives as 200 ms PCM16k chunks straight from the call: schedule them back to back.
  function playMaxChunk(b64) {
    ensureAudio();
    const bin = atob(b64);
    const n = bin.length / 2;
    const buf = audioCtx.createBuffer(1, n, 16000);
    const ch = buf.getChannelData(0);
    for (let i = 0; i < n; i++) {
      let v = bin.charCodeAt(2 * i) | (bin.charCodeAt(2 * i + 1) << 8);
      if (v >= 0x8000) v -= 0x10000;
      ch[i] = v / 32768;
    }
    const src = audioCtx.createBufferSource();
    src.buffer = buf;
    src.connect(audioCtx.destination);
    const at = Math.max(audioCtx.currentTime + 0.05, maxPlayAt);
    src.start(at);
    maxPlayAt = at + buf.duration;
  }
  // Fallback when Gemini TTS is unavailable: the browser's own voice (agreed as backup).
  function browserSpeak(text, who) {
    if (!('speechSynthesis' in window)) return;
    const u = new SpeechSynthesisUtterance(text);
    const vs = speechSynthesis.getVoices().filter((v) => v.lang.startsWith('en'));
    if (vs.length) u.voice = vs[['karthi', 'prince', 'daniel', 'jacob', 'max'].indexOf(who) % vs.length] || vs[0];
    speechSynthesis.speak(u);
  }

  async function openVoices() {
    openModal('#voicesModal');
    $('#voicesBody').innerHTML = '<p class="muted">Loading…</p>';
    let v;
    try { v = await api('/api/voices'); } catch (e) { $('#voicesBody').innerHTML = `<p>${esc(e.message)}</p>`; return; }
    const lines = {
      karthi: "Morning everyone. Let's close the 220K gap first.",
      prince: 'To be precise, draft v2 is at 11,720K, so we still need 220K.',
      daniel: "Honestly, the Riverside pilot would fix most of our overtime.",
      jacob: 'Fresh Home Spring could add about 4.5 percent on Home Essentials!',
      max: "Per the 20 October meeting, LiftLine's lead time was 14 weeks.",
    };
    const people = [...ORDER.filter((id) => id !== 'max').map((id) => ({ id, name: member(id).name, voice: v.assigned[id] })),
      { id: 'max', name: 'Max (AI)', voice: v.max }];
    $('#voicesBody').innerHTML = `<p class="muted">Model: ${esc(v.model)}. Voices are set in <code>team.yaml</code> (people) and
      <code>max/.env</code> MAX_VOICE (Max).</p>` +
      people.map((p) => `<div class="voice-row"><div class="vr-name">${esc(p.name)}</div>
        <div class="vr-voice">${esc(p.voice)} · ${esc(v.candidates[p.voice] || '')}</div>
        <button class="btn" data-sample="${esc(p.voice)}" data-line="${esc(lines[p.id])}">▶ Play</button></div>`).join('') +
      `<h3 style="margin-top:18px">Try other voices</h3><div class="voice-grid">` +
      Object.entries(v.candidates).map(([name, desc]) => `<button class="btn" data-sample="${esc(name)}"
        data-line="Hi, I'm ${esc(name)}. This is how I sound in your meeting.">▶ ${esc(name)} <span class="muted">· ${esc(desc)}</span></button>`).join('') + '</div>';
  }
  async function playSample(btn) {
    btn.disabled = true;
    const label = btn.innerHTML;
    btn.innerHTML = '⏳ Generating…';
    try {
      const r = await api('/api/voices/sample', { voice: btn.dataset.sample, text: btn.dataset.line });
      playClip(r.url);
    } catch (e) {
      toast(e.message, true);
    } finally {
      btn.disabled = false;
      btn.innerHTML = label;
    }
  }

  async function join() {
    const mode = $('input[name="mode"]:checked').value;
    $('#joinBtn').disabled = true;
    ensureAudio();                                   // user gesture: unlock audio playback
    try {
      resetMeetingUI();
      await api('/api/meeting/start', { mode, media, speed: mode === 'autopilot' && media === 'text' ? speed : 1 });
      closeModals();
      showMeeting();
    } catch (e) {
      toast(e.message, true);
    } finally {
      $('#joinBtn').disabled = false;
    }
  }

  // ------------------------------------------------------------ meeting UI
  function buildGrid() {
    const grid = $('#grid');
    grid.innerHTML = '';
    ORDER.forEach((id) => {
      const m = member(id);
      const tile = document.createElement('div');
      tile.className = 'tile';
      tile.dataset.id = id;
      tile.style.setProperty('--c', id === 'karthi' ? '#FFB27A' : m.colour);
      tile.style.setProperty('--bg-c', tagColour(id));
      // Only Max has an avatar; people appear with their camera off (initial letter).
      const face = id === 'max' ? '<div class="av"></div>' : `<div class="initial">${esc(m.name.charAt(0).toUpperCase())}</div>`;
      tile.innerHTML = `${face}
        <div class="tag"><svg viewBox="0 0 24 24"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></svg>
        ${esc(id === 'max' ? 'Max' : m.name)}${id === 'karthi' ? ' (You)' : ''}${id === 'max' ? ' <span class="ai">AI</span>' : ''}</div>`;
      grid.appendChild(tile);
      if (id === 'max') {
        avatars.max = CloudAvatar.create(tile.querySelector('.av'), { background: 'meeting', colour: m.colour });
        avatars.max.setState('idle');
      }
    });
  }

  const tileOf = (id) => $(`.tile[data-id="${id}"]`);

  function showMeeting() {
    closeModals();
    $('#meeting').hidden = false;
    $('#mTitle').textContent = W.meeting.title;
    if (!Object.keys(avatars).length) buildGrid();
  }

  function hideMeeting() {
    $('#meeting').hidden = true;
    closeModals();
  }

  function resetMeetingUI() {
    $('#tlist').innerHTML = '';
    $('#clist').innerHTML = '';
    $('#caption').hidden = true;
    notes = null; scoreResult = null; notesPosted = false; t0 = null; pendingTurn = null; maxThinking = false; lastT = 0;
    $('#turn').hidden = true;
    $('#recBanner').hidden = true;
    maxPlayAt = 0;
    $('#mStep').textContent = '';
    $('#mTimer').textContent = '00:00';
    ORDER.forEach((id) => { if (avatars[id]) avatars[id].setState('idle'); });
    $$('.tile').forEach((t) => t.classList.remove('speaking', 'yourturn'));
    setComposerEnabled(true);
    $('#leaveBtn').textContent = 'Leave';
  }

  function setStatus(text) { $('#mStatus').textContent = text || ''; }

  function setComposerEnabled(on) {
    $('#sayInput').disabled = !on;
    $('#sayBtn').disabled = !on;
    $('#micBtn').disabled = !on;
  }

  function startTimer(serverT) {
    t0 = Date.now() - (serverT || 0) * 1000;
    clearInterval(timerId);
    timerId = setInterval(() => {
      const s = Math.max(0, Math.floor((Date.now() - t0) / 1000));
      $('#mTimer').textContent = `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
    }, 500);
  }

  function addTranscript(ev) {
    const m = member(ev.speaker);
    const div = document.createElement('div');
    div.className = `tline ${ev.speaker === 'max' ? 'max' : ''}`;
    const mm = Math.floor(ev.t / 60), ss = Math.floor(ev.t % 60);
    div.innerHTML = `<span class="tdot" style="background:${ev.speaker === 'karthi' ? '#FFB27A' : m.colour}"></span>
      <div><div class="tmeta"><b>${esc(ev.speaker === 'max' ? 'Max (AI)' : m.name)}</b>${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}</div>
      <div class="ttext">${esc(ev.text)}</div></div>`;
    const list = $('#tlist');
    const atBottom = list.parentElement.scrollHeight - list.parentElement.scrollTop - list.parentElement.clientHeight < 60;
    list.appendChild(div);
    if (atBottom) list.parentElement.scrollTop = list.parentElement.scrollHeight;
  }

  function addChat(ev, withNotesButton = false) {
    const div = document.createElement('div');
    if (ev.speaker === 'system') {
      div.className = 'cmsg system';
      div.textContent = ev.text;
    } else {
      div.className = 'cmsg';
      div.innerHTML = `<b>${esc(ev.speaker === 'max' ? 'Max (AI)' : member(ev.speaker).name)}</b>
        <div class="cbubble">${esc(ev.text)}${withNotesButton ? '<br><button class="btn primary" data-notes>View notes</button>' : ''}</div>`;
    }
    $('#clist').appendChild(div);
    $('#clist').parentElement.scrollTop = $('#clist').parentElement.scrollHeight;
  }

  function lookToward(listener, speaker) {
    const a = tileOf(listener), b = tileOf(speaker);
    if (!a || !b) return 'idle';
    const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
    const dx = (rb.left + rb.width / 2) - (ra.left + ra.width / 2);
    const dy = (rb.top + rb.height / 2) - (ra.top + ra.height / 2);
    if (Math.abs(dx) >= Math.abs(dy)) return dx < 0 ? 'lookLeft' : 'lookRight';
    return dy < 0 ? 'lookUp' : 'lookDown';
  }

  function mood(id, state, ms) {
    if (!avatars[id]) return;   // only Max has an animated avatar
    clearTimeout(moodTimers[id]);
    avatars[id].setState(state);
    if (ms) moodTimers[id] = setTimeout(() => avatars[id].setState('idle'), ms);
  }

  function playUtterance(ev) {
    const token = ++speechToken;
    const sp = ev.speaker;
    const dur = Math.max(800, ev.duration * 1000);
    $$('.tile').forEach((t) => t.classList.toggle('speaking', t.dataset.id === sp));
    if (sp === 'max') maxThinking = false;

    ORDER.forEach((id) => {
      if (id === sp) mood(id, 'speaking');
      else if (id === 'max' && maxThinking) { /* keep thinking */ }
      else mood(id, lookToward(id, sp));
    });
    if (sp !== 'max' && /\bmax\b/i.test(ev.text)) mood('max', 'surprised');   // Max hears its name

    // audio: the speaker's real voice clip (also streamed to Max through the call)
    if (ev.audio) playClip(ev.audio);
    else if (ev.browserVoice) browserSpeak(ev.text, sp);

    // caption typing
    $('#caption').hidden = false;
    $('#capName').textContent = (sp === 'max' ? 'Max' : member(sp).name) + ':';
    $('#capName').style.color = sp === 'karthi' ? '#FFB27A' : member(sp).colour;
    const words = ev.text.split(' ');
    let i = 0;
    const per = (dur * 0.85) / Math.max(1, words.length);
    const typeTick = () => {
      if (token !== speechToken) return;
      i++;
      $('#capText').textContent = words.slice(0, i).join(' ');
      if (i < words.length) setTimeout(typeTick, per);
    };
    typeTick();
    setStatus(`${sp === 'max' ? 'Max' : member(sp).name} is speaking…`);

    setTimeout(() => {
      if (token !== speechToken) return;
      tileOf(sp)?.classList.remove('speaking');
      ORDER.forEach((id) => {
        if (id === 'max' && maxThinking) return;
        if (id === sp) mood(id, ev.emotion && ev.emotion !== 'idle' ? ev.emotion : 'idle', 1800);
        else mood(id, 'idle');
      });
      setStatus('');
    }, dur);
  }

  function showTurn(ev) {
    pendingTurn = ev;
    $('#turn').hidden = false;
    $('#turnGoal').textContent = ev.goal;
    $('#suggestBtn').textContent = `💡 ${ev.suggestion}`;
    $('#suggestBtn').hidden = !ev.suggestion;
    tileOf('karthi')?.classList.add('yourturn');
    setStatus('The meeting is waiting for you.');
    $('#sayInput').focus();
  }

  function hideTurn() {
    pendingTurn = null;
    $('#turn').hidden = true;
    tileOf('karthi')?.classList.remove('yourturn');
  }

  // ------------------------------------------------------------ notes
  function showNotes() {
    if (!notes) { toast('Max has not written the notes yet.'); return; }
    let html = '';
    if (scoreResult) {
      html += `<div class="notes-score"><div class="big">${scoreResult.percent}%</div>
        <div><b>Max scored ${scoreResult.score} / ${scoreResult.out_of}</b><div class="muted">compared with the answer key for this meeting (autopilot)</div></div></div>`;
    }
    if (notesPosted) html += '<p class="muted">📌 Max posted these notes in the meeting thread (Planning Department › General).</p>';
    if (typeof notes === 'string') {
      html += `<div class="md"><div class="post-text md">${mdLite(notes)}</div>`;
    } else html += `<div class="md"><h2>Summary</h2><p>${esc(notes.summary || '')}</p>
      <h2>Decisions</h2><ul>${(notes.decisions || []).map((d) => `<li>${esc(typeof d === 'string' ? d : JSON.stringify(d))}</li>`).join('') || '<li>None recorded</li>'}</ul>
      <h2>Action items</h2><table><tr><th>Owner</th><th>Task</th><th>Due</th></tr>
      ${(notes.action_items || []).map((a) => `<tr><td>${esc(a.owner)}</td><td>${esc(a.task)}</td><td>${esc(a.due || '')}</td></tr>`).join('')}</table>
      <h2>Risks</h2><ul>${(notes.risks || []).map((r) => `<li>${esc(r)}</li>`).join('') || '<li>None recorded</li>'}</ul>
      ${notes.final_total_k ? `<p><b>Final H1 total:</b> ${Number(notes.final_total_k).toLocaleString()}K</p>` : ''}`;
    if (scoreResult) {
      html += `<h2>Score details</h2><table class="score-table"><tr><th>Section</th><th>Expected</th><th>Points</th></tr>` +
        scoreResult.items.map((it) => `<tr><td>${esc(it.section)}</td><td>${esc(it.item)}${it.answer ? `<div class="answer">Max said: “${esc(it.answer)}”</div>` : ''}</td>
          <td class="pts ${it.points === it.max ? 'ok' : 'no'}">${it.points === it.max ? '✓' : '✗'} ${it.points}/${it.max}</td></tr>`).join('') + '</table>';
    }
    html += '</div>';
    $('#notesBody').innerHTML = html;
    openModal('#notes');
  }

  // ------------------------------------------------------------ events
  let lastT = 0;
  const fmtClock = (s) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(Math.floor(s % 60)).padStart(2, '0')}`;

  function handle(ev, replay = false) {
    if (typeof ev.t === 'number') lastT = Math.max(lastT, ev.t);
    switch (ev.type) {
      case 'state':
        if (ev.status === 'live' && (replay || meetingStatus !== 'live')) {
          if (!replay && meetingStatus === 'ended') resetMeetingUI();
          $('#mMode').textContent = (ev.mode === 'autopilot' ? `Autopilot ${ev.speed}×` : 'Live · you host')
            + (ev.media === 'text' ? ' · ⚡ text' : ' · 🔊 voice');
          startTimer(ev.t);
          setComposerEnabled(true);
        }
        meetingStatus = ev.status;
        if (ev.status === 'summarizing') {
          setStatus('Max is writing the meeting notes…');
          hideTurn();
          if (avatars.max) mood('max', 'thinking');
        }
        if (ev.status === 'ended') {
          clearInterval(timerId);
          $('#mTimer').textContent = fmtClock(lastT);
          setComposerEnabled(false);
          hideTurn();
          $('#leaveBtn').textContent = 'Back to channel';
          setStatus('Meeting ended.');
          $('#caption').hidden = true;
          if (avatars.max) mood('max', notes ? 'happy' : 'confused', 2500);
          if (!replay && notes && !$('#meeting').hidden) showNotes();
        }
        renderMeetingCard();
        break;
      case 'beat':
        $('#mStep').textContent = `Step ${ev.index} of ${ev.total}`;
        break;
      case 'status':
        if (replay) break;
        if (ev.who === 'max' && ev.state === 'thinking') {
          maxThinking = true;
          setTimeout(() => { if (maxThinking) mood('max', 'thinking'); }, 500);
          setStatus('Max is thinking…');
        } else if (ev.state === 'preparing') {
          setStatus(`${first(ev.who)} is about to speak…`);
        }
        break;
      case 'utterance':
        addTranscript(ev);
        if (!replay) playUtterance(ev);
        break;
      case 'max_audio':
        if (!replay) playMaxChunk(ev.pcm);
        break;
      case 'max_speaking':
        if (replay) break;
        if (ev.on) {
          maxThinking = false;
          $$('.tile').forEach((t) => t.classList.toggle('speaking', t.dataset.id === 'max'));
          mood('max', 'speaking');
          ORDER.forEach((id) => { if (id !== 'max') mood(id, lookToward(id, 'max')); });
          setStatus('Max is speaking…');
        } else {
          tileOf('max')?.classList.remove('speaking');
          mood('max', 'happy', 1500);
          setStatus('');
        }
        break;
      case 'recording':
        $('#recBanner').hidden = ev.status !== 'recording';
        break;
      case 'call':
        if (!replay && ev.state === 'established') setStatus('Max joined the call.');
        break;
      case 'your_turn':
        if (replay) pendingTurn = ev; else showTurn(ev);
        break;
      case 'your_turn_done':
        if (replay) pendingTurn = null; else hideTurn();
        break;
      case 'chat':
        addChat(ev);
        break;
      case 'summary':
        notes = ev.notes;
        notesPosted = !!ev.posted;
        addChat({ speaker: 'max', text: 'Here are the meeting notes: summary, decisions, action items and risks.' }, true);
        break;
      case 'score':
        scoreResult = ev.result;
        break;
      case 'error':
        if (!replay) toast(ev.message, true);
        break;
      default:
        break;
    }
  }

  function connect() {
    const onMessage = (ev) => {
      if (ev.type === 'replay') {
        if (!Object.keys(avatars).length && W) buildGrid();
        resetMeetingUI();
        meetingStatus = W.meetingState.status === 'lobby' ? 'lobby' : meetingStatus;
        ev.events.forEach((e) => handle(e, true));
        if (pendingTurn) showTurn(pendingTurn);
        renderMeetingCard();
      } else {
        handle(ev);
      }
    };
    // ?snapshot = load history once, no live stream (used for headless screenshots)
    if (new URLSearchParams(location.search).has('snapshot')) {
      api('/api/history').then((d) => {
        onMessage({ type: 'replay', events: d.events });
        if (location.hash === '#meeting' && meetingStatus !== 'lobby') showMeeting();
        if (location.hash === '#notes' && notes) { showMeeting(); showNotes(); }
      });
      return;
    }
    const es = new EventSource('/api/events');
    es.onmessage = (msg) => onMessage(JSON.parse(msg.data));
  }

  // ------------------------------------------------------------ talking
  async function say(text) {
    text = (text || '').trim();
    if (!text) return;
    try {
      await api('/api/meeting/say', { text });
      $('#sayInput').value = '';
      hideTurn();
    } catch (e) {
      toast(e.message, true);
    }
  }

  let rec = null, recBusy = false;
  async function toggleMic() {
    if (recBusy) return;
    if (!rec) {
      try {
        rec = await MicRecorder.start((lvl) => {
          $('#micBtn').style.setProperty('--lvl', lvl.toFixed(3));
          tileOf('karthi')?.querySelector('.initial')?.style.setProperty('--lvl', lvl.toFixed(3));
        });
      } catch (_) {
        toast('Microphone access was blocked. Allow the mic in your browser, or type instead.', true);
        return;
      }
      $('#micBtn').classList.add('rec');
      tileOf('karthi')?.classList.add('recording');
      setStatus('Recording… click the mic again when you finish.');
      return;
    }
    recBusy = true;
    const r = rec; rec = null;
    $('#micBtn').classList.remove('rec');
    $('#micBtn').disabled = true;
    tileOf('karthi')?.classList.remove('recording');
    try {
      const { wavBase64, seconds } = await r.stop();
      if (seconds < 0.4) { setStatus('Too short. Try again.'); return; }
      setStatus('Sending your voice into the call…');
      // Your real voice goes into the call (Max hears the audio); the room caption is transcribed.
      await api('/api/meeting/say', { audio: wavBase64 });
      $('#sayInput').value = '';
      hideTurn();
      setStatus('');
    } catch (e) {
      toast(e.message, true);
    } finally {
      recBusy = false;
      $('#micBtn').disabled = meetingStatus === 'ended';
    }
  }

  // ------------------------------------------------------------ wiring
  function wire() {
    document.addEventListener('click', (e) => {
      const t = e.target.closest('button, .frow, .file-chip');
      if (!t) {
        if (e.target.classList.contains('modal')) closeModals();
        return;
      }
      if (t.matches('[data-close]')) closeModals();
      else if (t.matches('[data-join]')) openPrejoin();
      else if (t.matches('[data-notes]')) showNotes();
      else if (t.matches('.tab')) switchTab(t.dataset.tab);
      else if (t.matches('[data-meeting]')) openPastMeeting(t.dataset.meeting, t.dataset.view);
      else if (t.dataset.path) openDoc(t.dataset.path, t.dataset.name);
    });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeModals(); });

    $('#meetNowBtn').addEventListener('click', openPrejoin);
    // channel: compose, reply, apps
    const np = $('#newPost');
    const sendNew = async () => { if (await postToChannel(np.value, null)) { np.value = ''; np.style.height = ''; } };
    $('#newPostBtn').addEventListener('click', sendNew);
    np.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey && $('#mentionPop').hidden) { e.preventDefault(); sendNew(); }
    });
    np.addEventListener('input', () => { np.style.height = 'auto'; np.style.height = `${Math.min(160, np.scrollHeight)}px`; });
    attachMentions(np);
    document.addEventListener('click', (e) => {
      const r = e.target.closest('[data-reply]');
      if (r) openReplyBox(r.dataset.reply);
      if (e.target.closest('[data-open-app]')) openAppModal();
    });
    $('#appsBtn').addEventListener('click', openAppModal);
    $('#adminBtn').addEventListener('click', openAdmin);
    $('#adminBody').addEventListener('click', (e) => {
      const b = e.target.closest('[data-admin]');
      if (b) adminAction(b.dataset.admin, b.dataset.val);
    });
    $('#uploadInput').addEventListener('change', (e) => { uploadFile(e.target.files[0]); e.target.value = ''; });
    $('#appAddBtn').addEventListener('click', () => setInstalled(true));
    $('#appRemoveBtn').addEventListener('click', () => setInstalled(false));
    $('#resetChannelBtn').addEventListener('click', async () => {
      try { await api('/api/channel/reset', {}); toast('Channel reset to the seeded world. Max was removed.'); }
      catch (e) { toast(e.message, true); }
    });
    $('#joinBtn').addEventListener('click', join);
    $$('#mediaSeg button').forEach((b) => b.addEventListener('click', () => {
      media = b.dataset.media;
      $$('#mediaSeg button').forEach((x) => x.classList.toggle('active', x === b));
      $('#speedRow').hidden = media === 'voice';
      $('#mediaHint').textContent = media === 'voice'
        ? 'Everyone speaks with their own Gemini voice. Max hears the audio through the call and answers out loud.'
        : 'Fast and free of audio: Max listens to a live transcript and answers in the meeting chat.';
    }));
    $('#speedRow').hidden = true;
    $('#voicesBtn').addEventListener('click', openVoices);
    $('#voicesBody').addEventListener('click', (e) => {
      const b = e.target.closest('[data-sample]');
      if (b) { ensureAudio(); playSample(b); }
    });
    $$('#speedSeg button').forEach((b) => b.addEventListener('click', () => {
      speed = Number(b.dataset.speed);
      $$('#speedSeg button').forEach((x) => x.classList.toggle('active', x === b));
    }));

    $('#sayBtn').addEventListener('click', () => say($('#sayInput').value));
    $('#sayInput').addEventListener('keydown', (e) => { if (e.key === 'Enter') say($('#sayInput').value); });
    $('#suggestBtn').addEventListener('click', () => { if (pendingTurn) say(pendingTurn.suggestion); });
    $('#micBtn').addEventListener('click', toggleMic);

    $('#toggleSide').addEventListener('click', () => {
      $('.m-body').classList.toggle('no-side');
      $('#toggleSide').classList.toggle('on', !$('.m-body').classList.contains('no-side'));
    });
    $$('.side-tab').forEach((b) => b.addEventListener('click', () => {
      $$('.side-tab').forEach((x) => x.classList.toggle('active', x === b));
      $$('.side-pane').forEach((p) => p.classList.toggle('active', p.id === `side-${b.dataset.side}`));
    }));

    $('#leaveBtn').addEventListener('click', async () => {
      if (meetingStatus === 'live') {
        $('#leaveBtn').textContent = 'Ending…';
        try { await api('/api/meeting/stop', {}); } catch (e) { toast(e.message, true); }
      } else {
        hideMeeting();
      }
    });
    $('#backToChannel').addEventListener('click', hideMeeting);
    $('#lastNotesBtn').addEventListener('click', () => { showMeeting(); showNotes(); });
  }

  async function init() {
    wire();
    try {
      W = await api('/api/world');
    } catch (e) {
      toast(`Could not load the team: ${e.message}`, true);
      return;
    }
    meetingStatus = W.meetingState.status;
    renderModels();
    renderMeetingCard();
    await loadChannel(true);
    if (!new URLSearchParams(location.search).has('snapshot')) connectChannel();
    renderFiles();
    renderMeetingsTab();
    buildGrid();
    connect();
    // Deep link: /#meeting rejoins a running/finished meeting directly
    if (location.hash === '#meeting' && meetingStatus !== 'lobby') showMeeting();
  }

  init();
})();
