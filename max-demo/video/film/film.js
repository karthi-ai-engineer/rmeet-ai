/* Max film v3: deterministic timeline. renderAt(t) sets every visual from the time t (seconds) only, so the
   frame-by-frame render (render.mjs) is exact and repeatable. Max is the REAL avatar (bot-avatar/avatar.js), stepped
   by the film clock. Preview: open index.html (space = play/pause, ?t=30 to jump). People: Karthi M, Prince Alex, Daniel. */
(() => {
  'use strict';
  const FPS = 30;
  const params = new URLSearchParams(location.search);
  const RENDER = params.has('render');

  // ---------------------------------------------------------------- easing + helpers
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const lerp = (a, b, p) => a + (b - a) * p;
  const E = {
    outExpo: (p) => (p >= 1 ? 1 : 1 - Math.pow(2, -10 * p)),
    outCubic: (p) => 1 - Math.pow(1 - p, 3),
    inOutCubic: (p) => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2),
  };
  const prog = (t, a, d) => clamp((t - a) / d);
  const tw = (t, a, d, ease = E.outExpo) => ease(prog(t, a, d));
  const spring = (t, a, k = 1) => { const x = (t - a) * k; if (x <= 0) return 0; return 1 - Math.exp(-x * 7.5) * Math.cos(x * 13); };
  const vis = (t, a, b, fi = 0.35, fo = 0.35) => (t < a || t > b ? 0 : Math.min(tw(t, a, fi, E.outCubic), 1 - tw(t, b - fo, fo, E.inOutCubic)));
  const hash = (n) => { const s = Math.sin(n * 127.1 + 311.7) * 43758.5453; return s - Math.floor(s); };

  // ---------------------------------------------------------------- voice lengths (video/assets/vo/durations.json)
  const DUR = { n_hook1: 2.31, n_hook2: 2.22, n_meet: 3.46, k_who: 3.52, m_who: 4.06, k_book: 4.04, m_card: 3.94, n_yes: 3.08,
    m_booked: 3.23, k_mail: 2.91, p_cc: 3.01, m_refuse: 3.57, k_wrap: 1.97, m_recap: 5.45, d_fix: 2.11, m_gotit: 1.09,
    n_chan: 2.75, n_tag: 2.35 };

  // ---------------------------------------------------------------- the timeline (seconds)
  const T = {
    hook1: 0.5, dim: 2.9, hook2: 3.1, ended: 3.6, black1: 5.5,
    relight: 6.0, circles: 6.3, swap: 7.15, meet: 6.6, rec: 8.0,
    who: 12.4, think1: 16.0, mwho: 16.8,
    book: 21.2, scan: 25.3, card: 27.2, mcard: 27.5, pIn: 31.0, pClick: 32.1, kIn: 32.6, kClick: 33.5, done: 33.7, yes: 33.9,
    mail: 37.3, mailCard: 40.3, mIn: 40.7, mClick: 41.5, sent: 41.7,
    cc: 42.6, squint: 45.7, refuse: 46.1,
    wrap: 49.9, draft: 52.0, recap: 52.2, fix: 57.9, strike: 60.1, gotit: 60.3, end: 62.4,
    chan: 62.9, notes: 63.4, tasks: 64.0,
    nchan: 63.3, i1: 67.0, i2: 73.0, i3: 79.2, i4: 86.2,
    audit: 91.8, words: 92.7,
    finale: 95.8, tag: 96.2, tag2: 97.4, lock: 99.2, out: 101.8, END: 102.4,
  };
  const VO = [
    ['n_hook1', T.hook1], ['n_hook2', T.hook2], ['n_meet', T.meet], ['k_who', T.who], ['m_who', T.mwho],
    ['k_book', T.book], ['m_card', T.mcard], ['n_yes', T.yes], ['k_mail', T.mail], ['p_cc', T.cc], ['m_refuse', T.refuse],
    ['k_wrap', T.wrap], ['m_recap', T.recap], ['d_fix', T.fix], ['m_gotit', T.gotit], ['n_chan', T.nchan], ['n_tag', T.tag],
  ];
  const voAt = (k) => VO.find((x) => x[0] === k)[1];
  const speaking = (key, t) => t >= voAt(key) && t <= voAt(key) + DUR[key];
  const MAX_LINES = ['m_who', 'm_card', 'm_refuse', 'm_recap', 'm_gotit'];
  const PEOPLE_LINES = { karthi: ['k_who', 'k_book', 'k_mail', 'k_wrap'], prince: ['p_cc'], daniel: ['d_fix'] };
  // the live chat: who types what, and when things happen (seconds from each interaction's start)
  const CHAT = [
    { id: 'f1', who: 'prince', at: T.i1, typed: '@Max what does the Northgate offer save us?', typeDur: 1.6, dots: 0.3, reply: 1.1 },
    { id: 'f2', who: 'prince', at: T.i2, typed: 'I need till Friday for the budget v3.', typeDur: 1.2, dots: 0.3, reply: 1.0, click: 2.5 },
    { id: 'f3', who: 'karthi', at: T.i3, typed: '@Max book 30 min with Prince tomorrow at 11', typeDur: 1.4, dots: 0.3, reply: 0.6, card: 2.8, click: 4.0 },
  ].map((c) => ({ ...c, send: c.at + c.typeDur + 0.1 }));
  const BRIEF_AT = T.i4 + 0.9;
  const SFX = [
    [3.6, 'hangup', 0.8], [6.35, 'pop', 0.3], [6.5, 'pop', 0.3], [6.65, 'pop', 0.3], [6.8, 'pop', 0.3], [6.95, 'pop', 0.3],
    [7.2, 'join', 0.8], [8.0, 'tick', 0.45], [8.6, 'blip', 0.3], [9.2, 'blip', 0.3], [9.8, 'blip', 0.3],
    [12.3, 'whoosh', 0.4], [15.9, 'swish', 0.35], [21.1, 'whoosh', 0.4], [25.3, 'card', 0.5], [26.9, 'confirm', 0.45],
    [T.card, 'card', 0.7], [T.pClick, 'click', 0.8], [T.pClick + 0.15, 'deny', 0.55], [T.kClick, 'click', 0.9], [T.done, 'confirm', 0.75],
    [37.2, 'whoosh', 0.4], [T.mailCard, 'card', 0.7], [T.mClick, 'click', 0.85], [T.sent, 'confirm', 0.6],
    [42.5, 'whoosh', 0.4], [T.squint, 'deny', 0.6], [49.8, 'whoosh', 0.4], [T.draft, 'card', 0.7], [57.8, 'whoosh', 0.4],
    [T.strike, 'tick', 0.7], [T.end, 'hangup', 0.7], [62.9, 'swish', 0.4], [T.notes, 'card', 0.6], [T.tasks, 'tick', 0.55],
    [T.tasks + 0.3, 'tick', 0.55], [T.tasks + 0.6, 'tick', 0.55],
    ...CHAT.flatMap((c) => [
      ...Array.from({ length: c.typed.length }, (_, k) => [c.at + (k / c.typed.length) * c.typeDur, 'key', 0.22]),
      [c.send, 'send', 0.5], [c.send + c.reply, c.card ? 'card' : 'pop', 0.55],
      ...(c.card ? [[c.send + c.reply + 0.4, 'blip', 0.3], [c.send + c.reply + 1.2, 'blip', 0.3], [c.send + c.reply + 1.9, 'confirm', 0.4], [c.send + c.card, 'card', 0.6]] : []),
      ...(c.click ? [[c.send + c.click, 'click', 0.85], [c.send + c.click + 0.2, 'confirm', 0.6]] : []),
    ]),
    [T.i4, 'swish', 0.4], [BRIEF_AT, 'chime', 0.6],
    [92.0, 'tick', 0.3], [92.2, 'tick', 0.3], [92.4, 'tick', 0.3], [92.6, 'tick', 0.3],
    [T.words, 'hit', 0.7], [T.words + 0.6, 'hit', 0.7], [T.words + 1.2, 'hit', 0.8], [T.lock, 'logo', 0.8],
  ];
  window.FILM = { fps: FPS, duration: T.END, vo: VO.map(([k, t]) => ({ key: k, t })), sfx: SFX.map(([t, type, gain]) => ({ t, type, gain })) };

  // ---------------------------------------------------------------- icons
  const CLOUD = (id = '') => `<svg viewBox="0 0 40 40" ${id}><g fill="#FF6B00"><circle cx="20" cy="22" r="11"/><circle cx="11" cy="24" r="7"/><circle cx="29" cy="24" r="7"/><circle cx="15" cy="15" r="7"/><circle cx="25" cy="13" r="8"/></g><g class="eyes" fill="#fff"><rect x="15.5" y="18" width="3" height="6" rx="1.5"/><rect x="22" y="18" width="3" height="6" rx="1.5"/></g></svg>`;
  const I = {
    mic: '<svg viewBox="0 0 24 24"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></svg>',
    cam: '<svg viewBox="0 0 24 24"><rect x="3" y="6" width="13" height="12" rx="2"/><path d="M16 10l5-3v10l-5-3"/></svg>',
    share: '<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="13" rx="2"/><path d="M12 14V8M9 10.5L12 7.5l3 3M8 21h8"/></svg>',
    chat: '<svg viewBox="0 0 24 24"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/></svg>',
    phone: '<svg viewBox="0 0 24 24"><path d="M3 12c4-4 14-4 18 0l-2 3-4-1v-3c-2-.6-4-.6-6 0v3l-4 1z"/></svg>',
    teams: '<svg viewBox="0 0 24 24"><circle cx="9" cy="8" r="3.2"/><path d="M3.5 19a5.5 5.5 0 0 1 11 0"/><circle cx="17" cy="9" r="2.5"/><path d="M15.5 14.2A4.5 4.5 0 0 1 21 18.5"/></svg>',
    cal: '<svg viewBox="0 0 24 24"><rect x="3.5" y="5" width="17" height="15" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/></svg>',
    bell: '<svg viewBox="0 0 24 24"><path d="M6 8a6 6 0 1 1 12 0c0 7 3 8 3 8H3s3-1 3-8"/><path d="M10 20a2 2 0 0 0 4 0"/></svg>',
    shield: '<svg viewBox="0 0 24 24" fill="none" stroke="#4F46E5" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l7 3v5c0 4.5-3 8.5-7 10-4-1.5-7-5.5-7-10V6z"/><path d="M9 12l2 2 4-4"/></svg>',
    check: '<svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>',
  };
  const ARROW = '<svg viewBox="0 0 24 24"><path d="M4 2.5l15 9.2-6.6 1.5 3.8 7.3-3 1.5-3.8-7.3L4 19.5z" fill="#fff" stroke="#0A0C12" stroke-width="1.3" stroke-linejoin="round"/></svg>';
  const calI = (c, s = 20) => I.cal.replace('<svg', `<svg width="${s}" height="${s}" fill="none" stroke="${c}" stroke-width="1.8"`);

  // ---------------------------------------------------------------- the stage
  const stage = document.getElementById('stage');
  const words = (s) => s.split(/(\s+)/).map((w) => (/^\s+$/.test(w) ? w : `<span class="w">${w}</span>`)).join('');
  const people = { karthi: ['Karthi M', 'KM', 'var(--karthi)'], prince: ['Prince Alex', 'PA', 'var(--prince)'], daniel: ['Daniel', 'D', 'var(--daniel)'] };
  const tile = (id, x, y) => `<div class="tile" id="tile-${id}" style="left:${x}px;top:${y}px;--c:${people[id][2]}"><div class="glow"></div>
      <div class="av">${people[id][1]}</div><div class="ring"></div><div class="name">${I.mic}${people[id][0]}</div>
      <div class="wave">${'<b></b>'.repeat(5)}</div></div>`;
  const tl = (who, time, text, max = false) => `<div class="tline${max ? ' max' : ''}" style="--c:${max ? 'var(--max)' : people[who][2]}"><i></i><div><div class="who"><b>${max ? 'Max (AI)' : people[who][0]}</b>${time}</div><div class="tx">${text}</div></div></div>`;
  const lavatar = (who) => (who === 'max' ? `<div class="pav max">${CLOUD()}</div>` : `<div class="pav" style="background:${people[who][2]}">${people[who][1]}</div>`);
  const lpost = (who, role, time, html, reply = '') => `<div class="lpost"><div class="post-main">${lavatar(who)}<div style="flex:1">
      <div class="pmeta"><b>${who === 'max' ? 'Max' : people[who][0]}</b>${who === 'max' ? '<span class="bot-tag">BOT</span>' : `<span class="role">${role}</span>`}<time>${time}</time></div>
      <div class="ptext">${html}</div></div></div>${reply ? `<div class="replies"><div class="reply bot">${lavatar('max')}<div style="flex:1">
      <div class="pmeta"><b>Max</b><span class="bot-tag">BOT</span><time>${time}</time></div><div class="mreply">${reply}</div></div></div></div>` : ''}</div>`;
  const chatPost = (id, who, role, time, text, reply) => `<div class="post" id="${id}"><div class="post-main">${lavatar(who)}<div style="flex:1">
      <div class="pmeta"><b>${people[who][0]}</b><span class="role">${role}</span><time>${time}</time></div><div class="ptext">${text}</div></div></div>
      <div class="replies" id="${id}R"><div class="reply bot">${lavatar('max')}<div style="flex:1"><div class="pmeta"><b>Max</b><span class="bot-tag">BOT</span><time>${time.replace(/^\w+ /, '')}</time></div>
        <div class="tdots" id="${id}D"><b></b><b></b><b></b><span>Max is typing…</span></div><div class="rcontent" id="${id}C">${reply}</div></div></div></div></div>`;

  stage.innerHTML = `
  <div class="layer bg-dark" id="bgDark"></div>
  <div class="layer bg-light" id="bgLight"></div>
  <div class="layer warm" id="warm"></div>

  <div class="layer" id="callL"><div class="cam" id="callCam">
    <div class="win call-win" id="callWin">
      <div class="call-top"><span class="rec-dot" id="recDot"></span><span>Riverside pilot sync</span><span class="timer" id="timer">12:04</span>
        <span class="sp"></span><span class="demo-tag">Demo scenario</span></div>
      <div class="recbar" id="recbar"><i></i>Recording and transcription have started · <span>Max (AI) is taking notes</span></div>
      <div class="grid">
        ${tile('karthi', 0, 0)}${tile('prince', 626, 0)}${tile('daniel', 0, 348)}
        <div class="tile" id="tile-max" style="left:626px;top:348px;--c:#FF6B00"><div class="glow"></div>
          <div class="joining" id="joining">Max is joining…</div>
          <div class="cloud" id="maxCloud">${CLOUD('id="cloudSvg"')}</div>
          <div class="av-host" id="avHost"></div><div class="ring"></div>
          <div class="name" id="maxName">Max <span class="ai">AI</span></div></div>
      </div>
      <div class="scan" id="scan"><div class="sh"><span>Checking 3 calendars · Tue 24 Nov</span><span class="dots"><b></b><b></b><b></b></span></div>
        <div class="hours"><div></div><div><span>9:00</span><span>10:00</span><span>11:00</span><span>12:00</span></div></div>
        <div class="row"><div>Karthi M</div><div class="bar"><div class="busy soft" style="left:0;width:16.6%"></div></div></div>
        <div class="row"><div>Prince Alex</div><div class="bar"><div class="busy soft" style="left:66.6%;width:33.4%"></div></div></div>
        <div class="row"><div>Daniel</div><div class="bar"><div class="busy" style="left:33.3%;width:16.7%"></div></div></div>
        <div class="free" id="scanFree" style="left:calc(130px + 24px + (100% - 178px) * .5);width:calc((100% - 178px) * .166);top:78px;height:130px"></div>
        <div class="line" id="scanLine" style="top:76px;height:134px"></div>
        <div class="res" id="scanRes">✓ Tue 10:30 · everyone is free (Daniel is busy at 10:00)</div></div>
      <div class="caption-bar" id="capbar"><b>Max (AI)</b><span id="capText"></span></div>
      <div class="side">
        <div class="side-tabs"><div id="tabT" class="on">Transcript</div><div id="tabC">Chat</div></div>
        <div class="side-body">
          <div class="pane" id="paneT"><div id="tlist">
            ${tl('karthi', '12:01', 'Vector confirmed the Riverside quote.')}${tl('prince', '12:02', 'Then the pilot fits the H1 budget.')}
            ${tl('daniel', '12:02', 'Install can start in May.')}${tl('karthi', '12:03', 'Max, who said LiftLine was 40K cheaper?')}
            ${tl('max', '12:03', 'You did, Karthi. In our October 20th meeting.', true)}${tl('karthi', '12:04', 'Max, book a follow-up on Tuesday with Prince and Daniel.')}
          </div></div>
          <div class="pane" id="paneC"><div id="clist">
            <div class="msg max" id="cBook"><div class="who">Max (AI)</div>
              <div class="acard" id="acBook"><div class="hd" id="bookHd">${calI('#A5B4FC')}<span>Teams meeting for approval</span></div>
                <div class="facts"><div><span>Title</span><em>Riverside follow-up</em></div><div><span>When</span><em>Tue 24 Nov · 10:30–11:00</em></div>
                  <div><span>Attendees</span><em>Karthi M, Prince Alex, Daniel</em></div></div>
                <div class="note">💡 Daniel is busy at 10:00, so 10:30 is the first time all three are free.</div>
                <div class="btns" id="bookBtns"><div class="btn pri" id="btnBook">Approve</div><div class="btn">Change</div><div class="btn red">Cancel</div></div>
                <div class="done" id="bookDone">✓ Invites sent · Teams link created</div>
                <div class="who-ap">Only Karthi or the team owner can approve.</div></div></div>
            <div class="msg max" id="cMail"><div class="who">Max (AI)</div>
              <div class="acard mail" id="acMail"><div class="hd" id="mailHd"><span>✉ Email for approval</span></div>
                <div class="facts"><div><span>To</span><em>Elena Park (CFO)</em></div><div><span>Subject</span><em>H1 budget draft v2</em></div>
                  <div><span>Attached</span><em><span class="att"><span class="xl">XLS</span>04_Budget_Draft_v2.xlsx · 7 KB</span></em></div></div>
                <div class="btns" id="mailBtns"><div class="btn pri" id="btnMail">Approve</div><div class="btn">Change</div><div class="btn red">Cancel</div></div>
                <div class="done" id="mailDone">✓ Sent to Elena · approved by Karthi M</div></div></div>
            <div class="msg max" id="cDraft"><div class="who">Max (AI)</div><div class="acard draft">
              <div class="hd">📋 Before we finish: draft notes</div>
              <h5>Decisions</h5><ul><li>Go with Vector for the Riverside pilot (200K)</li><li>Follow-up on Tue 24 Nov, 10:30</li></ul>
              <h5>Action items</h5><ul><li>Daniel: confirm the Vector quote · <span class="old" id="oldDate">Thu 26 Nov</span> <span class="new" id="newDate">Fri 27 Nov</span></li>
                <li>Prince Alex: budget v3 · Wed 25 Nov</li><li>Karthi M: final budget to Elena · Fri 28 Nov</li></ul></div></div>
          </div></div>
        </div>
      </div>
      <div class="call-bar"><div class="cbtn">${I.mic}</div><div class="cbtn">${I.cam}</div><div class="cbtn">${I.share}</div><div class="cbtn">${I.chat}</div><div class="cbtn leave">${I.phone}</div></div>
      <div class="ended-pill" id="endedPill"><i></i>Call ended</div>
      <div class="toast" id="joinToast"><span class="d"></span>Max (AI) joined the call</div>
    </div>
  </div></div>

  <div class="layer" id="chanL"><div class="cam" id="chanCam">
    <div class="win app-win">
      <div class="rail"><div class="logo">${CLOUD()}</div><div class="ri">${I.bell}</div><div class="ri">${I.chat}</div><div class="ri on">${I.teams}</div><div class="ri">${I.cal}</div></div>
      <div class="app-head"><div class="team-ic">PD</div><div><h3>General</h3><p>Planning Department · Kestrel Home Goods</p></div>
        <div class="tabs"><span class="on">Posts</span><span>Files</span><span>Meetings</span></div><span class="sp"></span><span class="demo-tag">Demo scenario</span></div>
      <div class="app-body">
        <div class="feedvp" id="feedvp"><div class="feed" id="feed">
          <div class="post" id="fMeet"><div class="post-main"><div class="pav" style="background:var(--karthi)">KM</div><div style="flex:1">
            <div class="pmeta"><b>Karthi M</b><span class="role">Planning Manager</span><time>Mon 12:00 PM</time></div>
            <div class="ptext">Riverside pilot sync</div><div class="mchip">${calI('#4F46E5', 18)} Riverside pilot sync · <span>Ended · notes below</span></div></div></div>
            <div class="replies"><div class="reply bot" id="notesReply">${lavatar('max')}<div style="flex:1">
              <div class="pmeta"><b>Max</b><span class="bot-tag">BOT</span><time>12:11 PM</time></div>
              <div class="ptext notes"><h4>📝 Meeting notes: Riverside pilot sync</h4>
                <h5>Decisions</h5><div>Go with Vector for the Riverside pilot (<b>200K</b>) · Follow-up booked for Tue 24 Nov, 10:30 · Budget draft emailed to Elena</div>
                <h5>Action items</h5><ul>
                  <li><span class="chk" id="chk0">${I.check}</span>Daniel: confirm the Vector quote · Fri 27 Nov<span class="task-tag" id="tt0">Task saved · reminder set</span></li>
                  <li><span class="chk" id="chk1">${I.check}</span>Prince Alex: budget v3 · Wed 25 Nov<span class="task-tag" id="tt1">Task saved · reminder set</span></li>
                  <li><span class="chk" id="chk2">${I.check}</span>Karthi M: send the final budget to Elena · Fri 28 Nov<span class="task-tag" id="tt2">Task saved · reminder set</span></li></ul>
                <div class="foot-note">I read these back before the end of the meeting; Daniel's correction is included.</div></div></div></div></div></div>
          ${chatPost('f1', 'prince', 'Finance', 'Mon 2:40 PM', '<span class="mention">@Max</span> what does the Northgate offer save us?',
            `<div class="ptext">A <b>3.5% rate cut</b>, saving <b>105K in H1</b>, per the Northgate offer (19 Nov).</div>
             <div class="fchip" id="f1chip"><span class="ficon md">MD</span>11_Northgate_Rate_Offer.md</div>`)}
          ${chatPost('f2', 'prince', 'Finance', 'Mon 3:05 PM', 'I need till Friday for the budget v3.',
            `<div class="ptext">You have an open task due Wed 25 Nov. Move it?</div>
             <div class="lcard" id="f2card"><div class="hd" id="f2hd">🗓 Move this deadline?</div><div class="facts"><span>Task</span><em>Budget v3</em><span>Owner</span><em>Prince Alex</em>
               <span>Due</span><em>Wed 25 Nov <span class="arrow">→</span> <b>Fri 27 Nov</b></em></div>
               <div class="btns" id="f2btns"><div class="lbtn pri" id="f2approve">Approve</div><div class="lbtn">Change</div><div class="lbtn red">Cancel</div></div>
               <div class="ldone" id="f2done">✓ Deadline moved to Fri 27 Nov · reminder updated</div></div>`)}
          ${chatPost('f3', 'karthi', 'Planning Manager', 'Mon 4:12 PM', '<span class="mention">@Max</span> book 30 min with Prince tomorrow at 11',
            `<div class="stack"><div class="lscan" id="f3scan"><div class="sh">Checking 2 calendars · Tue 24 Nov <span class="dots"><b></b><b></b><b></b></span></div>
                <div class="hours"><div></div><div><span>9:00</span><span>10:00</span><span>11:00</span><span>12:00</span><span>13:00</span></div></div>
                <div class="row"><div>Karthi M</div><div class="bar"><div class="busy soft" style="left:0;width:12.5%"></div><div class="busy soft" style="left:37.5%;width:12.5%"></div></div></div>
                <div class="row"><div>Prince Alex</div><div class="bar"><div class="busy" id="f3busy" style="left:50%;width:25%"></div></div></div>
                <div class="free" id="f3free"></div><div class="line" id="f3line"></div>
                <div class="res" id="f3res">✓ 12:00 · both free (Prince is busy 11:00–12:00)</div></div>
              <div class="lcard" id="f3card"><div class="hd" id="f3hd">📅 Teams meeting for approval</div><div class="facts"><span>When</span><em>Tue 24 Nov · 12:00–12:30</em><span>Attendees</span><em>Karthi M, Prince Alex</em></div>
                <div class="note">💡 You asked for 11:00, but Prince Alex is busy 11:00–12:00 (Budget v3 prep). This is the nearest time everyone is free.</div>
                <div class="btns" id="f3btns"><div class="lbtn pri" id="f3approve">Approve</div><div class="lbtn">Change</div><div class="lbtn red">Cancel</div></div>
                <div class="ldone" id="f3done">✓ Booked · invites sent · Teams link created</div></div></div>`)}
          <div class="divider" id="fDiv"><span>Tuesday 24 Nov · 10:15 AM</span></div>
          <div class="post" id="fBrief"><div class="post-main">${lavatar('max')}<div style="flex:1">
            <div class="pmeta"><b>Max</b><span class="bot-tag">BOT</span><time>Tue 10:15 AM</time></div>
            <div class="ptext"><b>🗒️ Meeting brief: Riverside follow-up</b> · starts in 15 minutes · 10:30<br>With: <span class="mention">@Karthi M</span> <span class="mention">@Prince Alex</span> <span class="mention">@Daniel</span>
              <div class="bsec"><b>Last time</b> · Go with Vector for the Riverside pilot (200K) · Action items from then: 1 of 3 done</div>
              <div class="bsec"><b>Open action items</b> · Daniel: confirm the Vector quote (due Fri 27 Nov) · Prince Alex: budget v3 (due Fri 27 Nov)</div>
              <div class="bsec"><b>New since last time</b> · Vector_Riverside_Quote_signed.pdf (Daniel)</div></div></div></div></div>
        </div></div>
        <div class="compose2"><div class="pav" id="cAv">PA</div>
          <div class="cbox" id="cbox"><span id="cText"></span><span class="caret" id="caret"></span><span class="ph" id="cPh">Start a post. Type @ to mention someone or Max</span></div>
          <div class="lbtn pri" id="cPost">Post</div></div>
      </div>
    </div>
  </div></div>

  <div class="layer" id="auditL">
    <div class="audit" id="auditCard">
      <div class="ah">${I.shield}<div><b>Activity · every request Max worked on</b><br><span>Who asked, what ran, who approved, what it cost</span></div></div>
      <table><tr><th>When</th><th>Asked by</th><th>Request</th><th>Result</th><th>Approved by</th><th>Cost</th></tr>
        <tr class="ar"><td class="mono">12:03</td><td>Karthi M</td><td>Who said LiftLine was 40K cheaper?</td><td><span class="pill info">answered · 20 Oct transcript</span></td><td>–</td><td class="mono">$0.001</td></tr>
        <tr class="ar"><td class="mono">12:04</td><td>Karthi M</td><td>Book a follow-up on Tuesday</td><td><span class="pill ok">meeting booked</span></td><td>Karthi M</td><td class="mono">$0.002</td></tr>
        <tr class="ar"><td class="mono">12:06</td><td>Karthi M</td><td>Send Elena the budget draft</td><td><span class="pill ok">email sent</span></td><td>Karthi M</td><td class="mono">$0.002</td></tr>
        <tr class="ar"><td class="mono">12:07</td><td>Prince Alex</td><td>Copy tom@gmail.com</td><td><span class="pill bad">refused · outside company</span></td><td>–</td><td class="mono">$0.001</td></tr>
        <tr class="ar"><td class="mono">12:10</td><td>Max</td><td>End-of-meeting check</td><td><span class="pill ok">notes · 3 tasks</span></td><td>–</td><td class="mono">$0.001</td></tr>
      </table>
    </div>
  </div>

  <div class="layer" id="kinBack"><div class="kin-back"></div></div>
  <div class="kin" id="kin"><div class="spk" id="kinSpk"><i></i><span></span></div><div class="txt" id="kinTxt"></div></div>

  <div class="layer" id="scrimL"><div class="scrim" id="scrim"></div></div>
  <div class="statement" id="st"><div class="l1" id="stL1"></div><div class="l2" id="stL2"></div></div>

  <div class="layer" id="finalL"><div class="halo" id="halo"></div>
    <div class="final" id="tagWrap"><div class="tagline" id="tagline">${words('Max does the work.')}<br><span class="yes">${words('You give the yes.')}</span></div></div>
    <div class="final" id="lockWrap"><div class="lockup"><div class="lg">${CLOUD('id="lockCloud"')}</div><h1>Max</h1><p>Your AI teammate for Microsoft Teams calls</p><small>Demo scenario · built on Microsoft Teams</small></div></div>
  </div>

  <div class="ncur" id="curP" style="--c:var(--prince)">${ARROW}<span class="tag">Prince Alex</span></div>
  <div class="ncur" id="curK" style="--c:#475467">${ARROW}<span class="tag">Karthi M</span></div>
  <div class="ripple" id="ripple"></div>
  <div class="refused" id="refused">⛔ Only Karthi M can approve this.</div>
  <canvas class="layer grain" id="grain" width="1920" height="1080"></canvas>
  <div class="layer vignette" id="vig"></div>
  <div class="black" id="black"></div>`;

  const $ = (id) => document.getElementById(id);
  const S = (el, o) => { for (const k in o) el.style[k] = o[k]; };
  const op = (el, v) => { el.style.opacity = v.toFixed(4); el.style.visibility = v <= 0.001 ? 'hidden' : 'visible'; };
  const posOf = (el) => { let x = 0, y = 0, n = el; while (n && n !== stage) { x += n.offsetLeft; y += n.offsetTop; n = n.offsetParent; } return { x, y, w: el.offsetWidth, h: el.offsetHeight }; };

  // ---------------------------------------------------------------- the real Max avatar, stepped by the film clock
  const realRAF = window.requestAnimationFrame.bind(window);
  const AV = { inst: null, q: [], t: 0, cur: null };
  window.requestAnimationFrame = (cb) => { AV.q.push(cb); return 1; };       // avatar.js schedules itself through this
  let seed = 7;
  Math.random = () => { seed = (seed * 1664525 + 1013904223) % 4294967296; return seed / 4294967296; };   // deterministic blinks
  const AVS = [[0, 'idle'], [T.swap, 'happy'], [8.3, 'idle'], [8.6, 'lookLeft'], [9.2, 'lookUp'], [9.8, 'lookLeft'], [10.6, 'idle'],
    [T.who, 'listening'], [T.think1, 'thinking'], [T.mwho, 'speaking'], [T.mwho + DUR.m_who + 0.1, 'happy'], [21.0, 'idle'],
    [T.book, 'listening'], [T.scan, 'thinking'], [T.mcard, 'speaking'], [T.mcard + DUR.m_card, 'idle'], [T.pClick + 0.1, 'lookUp'],
    [T.done, 'happy'], [35.0, 'idle'], [T.mail, 'listening'], [T.mail + DUR.k_mail, 'thinking'], [T.mailCard + 0.4, 'idle'],
    [T.sent, 'happy'], [42.4, 'idle'], [T.cc, 'listening'], [T.squint, 'squint'], [T.refuse, 'speaking'], [T.refuse + DUR.m_refuse, 'idle'],
    [T.wrap, 'listening'], [T.recap, 'speaking'], [T.recap + DUR.m_recap, 'idle'], [T.fix, 'listening'], [T.fix + DUR.d_fix, 'thinking'],
    [T.gotit, 'speaking'], [T.gotit + DUR.m_gotit, 'happy'], [T.end, 'idle']];
  const avState = (t) => { let s = 'idle'; for (const [a, st] of AVS) { if (t >= a) s = st; else break; } return s; };
  const personTalking = (t) => Object.values(PEOPLE_LINES).flat().some((k) => speaking(k, t));
  function avCreate() {
    const host = $('avHost'); host.innerHTML = ''; AV.q = []; seed = 7;
    const pn = performance.now; performance.now = () => 0;
    AV.inst = CloudAvatar.create(host, { background: 'meeting', colour: '#FF6B00' });
    performance.now = pn;
    AV.t = 0; AV.cur = null;
  }
  function avTo(t) {
    if (!AV.inst || t < AV.t - 1e-6) { if (AV.inst) AV.inst.destroy(); avCreate(); }
    while (AV.t < t - 1e-9) {
      AV.t = Math.min(t, AV.t + 1 / 60);
      const st = avState(AV.t);
      if (st !== AV.cur) { AV.inst.setState(st); AV.cur = st; }
      AV.inst.setLevel(personTalking(AV.t) ? 0.45 + 0.4 * Math.abs(Math.sin(AV.t * 9)) : 0);
      const q = AV.q.splice(0); q.forEach((cb) => cb(AV.t * 1000));
    }
  }

  // ---------------------------------------------------------------- statements
  const STATEMENTS = [
    { a: 0.4, b: 3.0, l1: 'Every decision is made in a meeting…', theme: 'dark' },
    { a: 3.0, b: 5.45, l1: '…and lost when the call ends.', theme: 'dark' },
    { a: 6.5, b: 9.4, l1: 'Meet Max.', l2: 'Your AI teammate, in every Teams call.', theme: 'dark' },
    { a: 9.6, b: 12.2, l1: 'It listens. It knows who said what.', theme: 'dark' },
    { a: 17.2, b: 20.9, l1: 'It remembers every meeting.', theme: 'dark' },
    { a: 27.7, b: 31.3, l1: 'It acts in the call.', theme: 'dark' },
    { a: 33.8, b: 37.0, l1: 'Nothing happens until the right person says yes.', theme: 'dark' },
    { a: 40.4, b: 42.5, l1: 'Emails, with the right file.', theme: 'dark' },
    { a: 46.2, b: 49.6, l1: 'Guardrails, built in.', theme: 'dark' },
    { a: 60.1, b: 62.2, l1: 'Checked before it\'s final.', theme: 'dark' },
    { a: 63.6, b: 66.6, l1: 'Notes and tasks, before you\'ve left the call.', theme: 'light' },
    { a: CHAT[0].send + 0.4, b: CHAT[1].at - 0.2, l1: 'Ask anything. Get the source.', theme: 'light' },
    { a: CHAT[1].send + 0.4, b: CHAT[2].at - 0.2, l1: 'It notices slipping deadlines.', theme: 'light' },
    { a: CHAT[2].send + 0.4, b: T.i4 - 0.2, l1: 'It books around everyone\'s calendar.', theme: 'light' },
    { a: BRIEF_AT + 0.2, b: T.audit - 0.2, l1: 'It briefs you before every meeting.', theme: 'light' },
  ];
  const stEl = $('st');
  let stCur = null;
  function statement(t) {
    const s = STATEMENTS.find((x) => t >= x.a && t <= x.b);
    if (s !== stCur) {
      stCur = s;
      if (s) { $('stL1').innerHTML = words(s.l1); $('stL2').innerHTML = s.l2 ? words(s.l2) : ''; stEl.className = `statement ${s.theme}`; }
    }
    if (!s) { op(stEl, 0); op($('scrimL'), 0); return; }
    op(stEl, 1); stEl.style.top = '926px';
    const fade = 1 - tw(t, s.b - 0.35, 0.35, E.inOutCubic);
    stEl.querySelectorAll('.w').forEach((w, i) => {
      const p = tw(t, s.a + i * 0.06, 0.55);
      S(w, { opacity: (p * fade).toFixed(3), transform: `translateY(${(1 - p) * 22}px)`, filter: `blur(${(1 - p) * 6}px)` });
    });
    op($('scrimL'), vis(t, s.a - 0.1, s.b + 0.2, 0.4, 0.4));
    $('scrim').className = `scrim ${s.theme === 'light' ? 'light' : ''}`;
  }

  // ---------------------------------------------------------------- kinetic speech (speech -> big type -> transcript)
  const KIN = [
    { key: 'k_who', who: 'karthi', text: 'Max, who said LiftLine was 40K cheaper?' },
    { key: 'k_book', who: 'karthi', text: 'Max, book a follow-up on Tuesday with Prince and Daniel.' },
    { key: 'k_mail', who: 'karthi', text: 'Max, send Elena the budget draft.' },
    { key: 'p_cc', who: 'prince', text: '…and copy tom@gmail.com.' },
    { key: 'k_wrap', who: 'karthi', text: 'OK, let\'s wrap up.' },
    { key: 'd_fix', who: 'daniel', text: 'Max, my date is the 27th.' },
  ].map((k) => ({ ...k, a: voAt(k.key), fly: voAt(k.key) + DUR[k.key] + 0.05 }));
  let kinCur = null;
  function kinetic(t) {
    const k = KIN.find((x) => t >= x.a - 0.15 && t <= x.fly + 0.5);
    if (k !== kinCur) {
      kinCur = k;
      if (k) {
        $('kinTxt').innerHTML = words(k.text);
        $('kinTxt').style.fontSize = k.text.length > 42 ? '74px' : '92px';
        $('kinSpk').style.setProperty('--c', people[k.who][2]);
        $('kinSpk').querySelector('span').textContent = people[k.who][0];
      }
    }
    const kin = $('kin');
    if (!k) { op(kin, 0); op($('kinBack'), 0); return; }
    const ws = kin.querySelectorAll('.w');
    const span = DUR[k.key] * 0.8;
    ws.forEach((w, i) => {
      const p = tw(t, k.a + (i / ws.length) * span, 0.42);
      S(w, { opacity: p.toFixed(3), transform: `translateY(${(1 - p) * 34}px)`, filter: `blur(${(1 - p) * 8}px)` });
    });
    const fly = tw(t, k.fly, 0.5, E.inOutCubic);
    S(kin, { top: '330px', transform: `translate(${fly * 560}px, ${fly * -60}px) scale(${1 - fly * 0.82})` });
    op(kin, 1 - tw(t, k.fly + 0.25, 0.25));
    op($('kinBack'), Math.min(tw(t, k.a - 0.15, 0.35, E.outCubic), 1 - tw(t, k.fly, 0.45)));
    op($('kinSpk'), 1 - fly);
  }

  // ---------------------------------------------------------------- camera
  let BTN = { book: { x: 1500, y: 440 }, mail: { x: 1500, y: 440 } };
  let SCROLL = { mail: 0, draft: 0 };
  const CALL_MOVES = [
    [0, 0.01, 960, 520, 1.0], [0.2, 5.0, 960, 500, 1.04],
    [6.0, 0.01, 960, 540, 1.0], [6.2, 3.3, 1000, 560, 1.04],
    [9.6, 1.0, 1450, 470, 1.28], [12.1, 0.8, 960, 520, 1.0],
    [16.4, 1.0, 1000, 640, 1.22], [20.9, 0.8, 960, 520, 1.0],
    [27.1, 1.0, 1500, 420, 1.42], [30.9, 1.1, 'book', null, 1.75], [34.6, 0.8, 1500, 430, 1.42],
    [37.1, 0.7, 960, 520, 1.0], [40.1, 0.8, 1500, 430, 1.42], [42.4, 0.7, 960, 520, 1.0],
    [45.8, 0.8, 1000, 640, 1.22], [49.7, 0.7, 960, 520, 1.0], [51.9, 0.8, 1500, 430, 1.42],
    [57.7, 0.6, 1120, 560, 1.1], [60.0, 0.6, 1500, 470, 1.42],
  ];
  function camAt(moves, t) {
    let c = { x: 960, y: 540, z: 1 };
    for (const [a, d, fx, fy, z] of moves) {
      if (t < a) break;
      const tx = fx === 'book' ? BTN.book.x : fx, ty = fx === 'book' ? BTN.book.y - 30 : fy;
      const p = E.inOutCubic(prog(t, a, d));
      c = { x: lerp(c.x, tx, p), y: lerp(c.y, ty, p), z: lerp(c.z, z, p) };
    }
    return c;
  }
  const camCss = (c, extra = '') => `translate(960px, 540px) scale(${c.z.toFixed(5)}) translate(${(-c.x).toFixed(2)}px, ${(-c.y).toFixed(2)}px) ${extra}`;
  const chatScroll = (t) => (t < T.mailCard - 0.4 ? 0 : t < T.draft - 0.4 ? tw(t, T.mailCard - 0.5, 0.6, E.inOutCubic) * SCROLL.mail
    : lerp(SCROLL.mail, SCROLL.draft, tw(t, T.draft - 0.5, 0.6, E.inOutCubic)));

  // ---------------------------------------------------------------- grain (deterministic)
  const g = $('grain').getContext('2d');
  const noise = [];
  for (let n = 0; n < 6; n++) {
    const c = document.createElement('canvas'); c.width = 256; c.height = 256;
    const cx = c.getContext('2d'), img = cx.createImageData(256, 256);
    for (let i = 0; i < img.data.length; i += 4) { const v = Math.floor(hash(i * 0.37 + n * 991) * 255); img.data[i] = img.data[i + 1] = img.data[i + 2] = v; img.data[i + 3] = 255; }
    cx.putImageData(img, 0, 0); noise.push(g.createPattern(c, 'repeat'));
  }
  const grain = (t) => { g.fillStyle = noise[Math.floor(t * FPS) % noise.length]; g.fillRect(0, 0, 1920, 1080); };

  // ---------------------------------------------------------------- the call
  const hookTalk = { karthi: [[0.5, 1.7], [8.5, 9.1]], prince: [[1.7, 2.6], [9.1, 9.7]], daniel: [[2.4, 2.9], [9.7, 10.4]] };
  function talkLevel(id, t) {
    const on = (hookTalk[id] || []).some(([a, b]) => t >= a && t <= b) || (PEOPLE_LINES[id] || []).some((k) => speaking(k, t));
    return on ? 0.55 + 0.45 * Math.abs(Math.sin(t * 9 + id.length)) : 0;
  }
  const CAPS = { m_who: 'You did, Karthi. In our October 20th meeting.', m_card: 'I\'ve put the invite in the chat, for Karthi to approve.',
    m_refuse: 'I can\'t. That address is outside the company.', m_recap: 'Before we finish: two decisions, three action items. Anything to correct?', m_gotit: 'Got it.' };
  function call(t) {
    const L = $('callL');
    const shown = t < T.black1 + 0.6 || (t >= T.relight && t < T.chan + 0.5);
    if (!shown) { op(L, 0); return; }
    const o = t < T.black1 + 0.6 ? Math.min(tw(t, 0, 0.9, E.outCubic), 1 - tw(t, T.black1, 0.5, E.inOutCubic))
      : Math.min(tw(t, T.relight, 0.6, E.outCubic), 1 - tw(t, T.end + 0.3, 0.6, E.inOutCubic));
    op(L, o);
    const endP = tw(t, T.end + 0.2, 0.8, E.inOutCubic);
    $('callCam').style.transform = camCss(camAt(CALL_MOVES, t), endP ? `translate(${-endP * 140}px, 0) scale(${1 - endP * 0.06})` : '');
    $('callWin').style.filter = endP ? `blur(${endP * 6}px)` : 'none';

    ['karthi', 'prince', 'daniel'].forEach((id, i) => {
      const el = $(`tile-${id}`);
      const dim = t < T.relight ? tw(t, T.dim + i * 0.3, 0.5) : 0;
      el.style.filter = `brightness(${1 - dim * 0.75}) saturate(${1 - dim})`;
      const lv = talkLevel(id, t);
      op(el.querySelector('.ring'), lv ? 0.95 : 0);
      op(el.querySelector('.glow'), lv ? 0.1 : 0);
      el.querySelectorAll('.wave b').forEach((b, j) => { b.style.height = `${6 + (lv ? 22 * Math.abs(Math.sin(t * (7 + j * 1.7) + j)) : 0)}px`; });
      op(el.querySelector('.wave'), lv ? 1 : 0);
    });
    op($('endedPill'), t < T.relight ? vis(t, T.ended, T.black1 + 0.5, 0.4, 0.1) : 0);
    op($('recDot'), t < T.relight ? 1 - tw(t, T.ended, 0.3) : 1);

    // Max: empty tile -> circles assemble -> the real avatar takes over
    const maxTile = $('tile-max'), present = t >= T.relight;
    op(maxTile, present ? 1 : 0);
    maxTile.classList.toggle('empty', t < T.swap);
    op($('joining'), present ? vis(t, T.relight + 0.2, T.circles + 0.5, 0.3, 0.3) : 0);
    const from = [[-60, 40], [-90, -50], [80, -70], [-40, -90], [90, 30]];
    $('cloudSvg').querySelectorAll('g:first-child circle').forEach((c, i) => {
      const p = spring(t, T.circles + i * 0.15, 1);
      c.setAttribute('transform', `translate(${((1 - p) * from[i][0]).toFixed(2)} ${((1 - p) * from[i][1]).toFixed(2)})`);
      c.style.opacity = clamp((t - (T.circles + i * 0.15)) * 4).toFixed(3);
    });
    $('cloudSvg').querySelector('.eyes').style.opacity = t > T.circles + 0.7 ? '1' : '0';
    const swap = tw(t, T.swap, 0.25, E.outCubic);
    op($('maxCloud'), present ? 1 - swap : 0);
    op($('avHost'), present ? swap : 0);
    op($('maxName'), t >= T.swap ? 1 : 0);
    op($('joinToast'), vis(t, T.swap + 0.1, T.swap + 2.4, 0.35, 0.4));
    const maxTalk = MAX_LINES.some((k) => speaking(k, t));
    op(maxTile.querySelector('.ring'), maxTalk ? 0.95 : 0);
    op(maxTile.querySelector('.glow'), maxTalk ? 0.16 : 0);

    // recording banner + transcript
    op($('recbar'), t >= T.rec ? 1 : 0);
    $('recbar').style.transform = `translateY(${(1 - tw(t, T.rec, 0.5)) * -40}px)`;
    const lineAt = [8.6, 9.2, 9.8, KIN[0].fly + 0.35, T.mwho + 0.4, KIN[1].fly + 0.35];
    let n = 0;
    [...$('tlist').children].forEach((ln, i) => {
      const p = tw(t, lineAt[i], 0.45); if (t >= lineAt[i]) n = i + 1;
      S(ln, { opacity: (t >= T.rec ? p : 0).toFixed(3), transform: `translateY(${(1 - p) * 14}px)` });
    });
    $('tlist').style.transform = `translateY(${-Math.max(0, n - 5) * 70}px)`;

    // live captions of what Max says
    const line = MAX_LINES.find((k) => t >= voAt(k) - 0.1 && t <= voAt(k) + DUR[k] + 0.7);
    op($('capbar'), line ? vis(t, voAt(line) - 0.1, voAt(line) + DUR[line] + 0.7, 0.25, 0.35) : 0);
    if (line) { const full = CAPS[line]; $('capText').textContent = full.slice(0, Math.max(0, Math.floor(full.length * clamp((t - voAt(line) - 0.1) / (DUR[line] * 0.8))))); }

    // calendar scan
    op($('scan'), vis(t, T.scan, T.card + 0.5, 0.35, 0.4));
    $('scan').style.transform = `translateY(${(1 - tw(t, T.scan, 0.5)) * 24}px) scale(${1.1 + 0.05 * tw(t, T.scan, 0.5)})`;
    const sw = prog(t, T.scan + 0.3, 1.3);
    $('scanLine').style.left = `calc(154px + (100% - 178px) * ${sw.toFixed(4)})`;
    op($('scanLine'), sw > 0 && sw < 1 ? 1 : 0);
    op($('scanFree'), clamp((t - (T.scan + 1.6)) * 4)); op($('scanRes'), clamp((t - (T.scan + 1.7)) * 4));
    $('scan').querySelectorAll('.dots b').forEach((b, i) => { b.style.opacity = (0.3 + 0.7 * Math.abs(Math.sin((t - i * 0.18) * 5))).toFixed(2); });

    // chat tab, cards, clicks
    const chat = t >= T.card - 0.2;
    $('tabT').className = chat ? '' : 'on'; $('tabC').className = chat ? 'on' : '';
    op($('paneT'), chat ? 0 : 1); op($('paneC'), chat ? 1 : 0);
    const item = (id, a) => { const p = tw(t, a, 0.55); S($(id), { opacity: p.toFixed(3), transform: `translateY(${(1 - p) * 26}px)` }); };
    item('cBook', T.card); item('cMail', T.mailCard); item('cDraft', T.draft);
    const bd = t >= T.done, md = t >= T.sent;
    $('bookHd').lastChild.textContent = bd ? '✓ Done · approved by Karthi M' : 'Teams meeting for approval';
    $('acBook').classList.toggle('ok', bd); $('bookBtns').style.display = bd ? 'none' : 'flex'; $('bookDone').style.display = bd ? 'block' : 'none';
    $('mailHd').lastChild.textContent = md ? '✓ Sent · approved by Karthi M' : '✉ Email for approval';
    $('acMail').classList.toggle('ok', md); $('mailBtns').style.display = md ? 'none' : 'flex'; $('mailDone').style.display = md ? 'block' : 'none';
    const press = (c) => (t >= c - 0.08 && t < c + 0.12 ? 'scale(0.94)' : 'none');
    $('btnBook').style.transform = t < T.pClick + 0.5 ? press(T.pClick) : press(T.kClick);
    $('btnMail').style.transform = press(T.mClick);
    const top = posOf($('cBook')).y;                                     // live: cards shrink once approved
    SCROLL = { mail: Math.max(0, posOf($('cMail')).y - top - 8), draft: Math.max(0, posOf($('cDraft')).y - top - 8) };
    const ctr = (el) => { const p = posOf(el); return { x: p.x + p.w / 2, y: p.y + p.h / 2 }; };
    if ($('bookBtns').style.display !== 'none') BTN.book = ctr($('btnBook'));
    if ($('mailBtns').style.display !== 'none') BTN.mail = ctr($('btnMail'));
    $('clist').style.transform = `translateY(${-chatScroll(t)}px)`;
    const sp = tw(t, T.strike, 0.4);
    $('oldDate').style.textDecorationColor = `rgba(240,68,56,${sp})`;
    $('oldDate').style.color = sp > 0 ? '#8D96A6' : '#C9CED8';
    S($('newDate'), { opacity: clamp((t - T.strike - 0.15) * 4).toFixed(3), display: 'inline-block', transform: `scale(${0.85 + spring(t, T.strike + 0.15) * 0.15})` });
    const secs = 4 * 60 + Math.floor(Math.max(0, t - T.relight)) + 3;
    $('timer').textContent = `${String(Math.floor(secs / 60) + 8).padStart(2, '0')}:${String(secs % 60).padStart(2, '0')}`;
  }

  // ---------------------------------------------------------------- named cursors (who clicks Approve)
  function screenPos(t, b) { const z = camAt(CALL_MOVES, t), y = b.y - chatScroll(t); return { x: 960 + (b.x - z.x) * z.z, y: 540 + (y - z.y) * z.z }; }
  function cursors(t) {
    const P = $('curP'), K = $('curK'), r = $('ripple'), rf = $('refused');
    const move = (el, a, click, b, fromX, fromY, outAt) => {
      if (t < a || t > outAt + 0.5) { op(el, 0); return; }
      const s = screenPos(t, b), p = tw(t, a, click - a - 0.1, E.inOutCubic);
      const x = lerp(fromX, s.x, p), y = lerp(fromY, s.y, p), pr = t >= click - 0.08 && t < click + 0.12 ? 0.86 : 1;
      S(el, { transform: `translate(${x - 6}px, ${y - 4}px) scale(${pr})` });
      op(el, Math.min(tw(t, a, 0.25), 1 - tw(t, outAt, 0.4)));
    };
    move(P, T.pIn, T.pClick, BTN.book, 1760, 980, T.pClick + 0.9);
    move(K, T.kIn, T.kClick, BTN.book, 380, 1040, T.kClick + 0.7);
    if (t >= T.mIn && t < T.sent + 1.2) move(K, T.mIn, T.mClick, BTN.mail, 420, 1040, T.mClick + 0.7);
    const rip = [T.pClick, T.kClick, T.mClick].find((c) => t >= c && t < c + 0.55);
    if (rip) { const s = screenPos(t, rip === T.mClick ? BTN.mail : BTN.book), q = prog(t, rip, 0.55); S(r, { left: `${s.x}px`, top: `${s.y}px`, transform: `scale(${0.3 + q * 1.4})` }); op(r, (1 - q) * 0.9); } else op(r, 0);
    const rv = vis(t, T.pClick + 0.15, T.kClick + 0.1, 0.25, 0.3);
    if (rv > 0) { const s = screenPos(t, BTN.book); S(rf, { left: `${s.x - 120}px`, top: `${s.y + 44}px`, transform: `scale(${0.9 + 0.1 * spring(t, T.pClick + 0.15)})` }); }
    op(rf, rv);
  }

  // ---------------------------------------------------------------- after the call
  // ---------------------------------------------------------------- after the call: a live chat in the channel
  let FEED_SCROLL = 0;
  const CHAN_CAM = { x: 1000, y: 610, z: 1.16 };
  const chanEnter = (t) => (1 - tw(t, T.chan, 1.0)) * 80;
  const chanScreen = (el, t) => { const p = posOf(el); return { x: 960 + (p.x + p.w / 2 - CHAN_CAM.x) * CHAN_CAM.z, y: 540 + (p.y + p.h / 2 - FEED_SCROLL + chanEnter(t) - CHAN_CAM.y) * CHAN_CAM.z }; };
  const grow = (el, p) => { if (p >= 1) { el.style.maxHeight = 'none'; } else { el.style.maxHeight = `${(el.scrollHeight * p).toFixed(1)}px`; } op(el, p > 0 ? Math.min(1, p * 1.6) : 0); };
  function channel(t) {
    const L = $('chanL');
    if (t < T.chan || t > T.audit + 0.4) { op(L, 0); return; }
    op(L, Math.min(tw(t, T.chan, 0.7, E.outCubic), 1 - tw(t, T.audit - 0.2, 0.4)));
    $('chanCam').style.transform = camCss(CHAN_CAM, `translateY(${chanEnter(t)}px)`);
    const nr = tw(t, T.notes, 0.6);
    S($('notesReply'), { opacity: nr.toFixed(3), transform: `translateY(${(1 - nr) * 24}px)` });
    [0, 1, 2].forEach((i) => {
      const a = T.tasks + i * 0.3, on = t >= a;
      $(`chk${i}`).classList.toggle('on', on);
      $(`chk${i}`).style.transform = `scale(${on ? 0.8 + spring(t, a) * 0.2 : 1})`;
      S($(`tt${i}`), { opacity: clamp((t - a - 0.1) * 4).toFixed(3) });
    });
    // the message box: who is typing what
    const typing = CHAT.find((c) => t >= c.at - 0.4 && t < c.send + 0.05);
    const who = typing ? typing.who : (CHAT.filter((c) => t >= c.send).pop() || CHAT[0]).who;
    $('cAv').textContent = people[who][1]; $('cAv').style.background = people[who][2];
    let txt = '';
    if (typing) txt = typing.typed.slice(0, Math.floor(typing.typed.length * clamp((t - typing.at) / typing.typeDur)));
    const esc = (x) => x.replace(/&/g, '&amp;').replace(/</g, '&lt;');
    $('cText').innerHTML = esc(txt).replace(/@Max/, '<span class="mention">@Max</span>');
    op($('cPh'), txt ? 0 : 1); $('cPh').style.display = txt ? 'none' : 'inline';
    op($('caret'), typing && Math.floor(t * 2.2) % 2 === 0 ? 1 : typing ? 0.25 : 0);
    const sendNow = CHAT.find((c) => t >= c.send - 0.12 && t < c.send + 0.1);
    $('cPost').style.transform = sendNow ? 'scale(0.93)' : 'none';
    $('cbox').classList.toggle('focus', !!typing);
    // posts and Max's replies grow in (so the feed scrolls smoothly, like a real chat)
    CHAT.forEach((c) => {
      grow($(c.id), tw(t, c.send, 0.45, E.outCubic));
      const R = $(`${c.id}R`), D = $(`${c.id}D`), C = $(`${c.id}C`);
      const dotsOn = t >= c.send + c.dots && t < c.send + c.reply;
      const replied = t >= c.send + c.reply;
      D.style.display = dotsOn ? 'flex' : 'none';
      C.style.display = replied ? 'block' : 'none';
      D.querySelectorAll('b').forEach((b, i) => { b.style.opacity = (0.3 + 0.7 * Math.abs(Math.sin((t - i * 0.18) * 5))).toFixed(2); });
      if (t < c.send + c.dots) { R.style.maxHeight = '0px'; op(R, 0); }
      else if (!replied) { R.style.maxHeight = `${R.scrollHeight}px`; op(R, tw(t, c.send + c.dots, 0.25)); }
      else grow(R, tw(t, c.send + c.reply, 0.5, E.outCubic));
      C.querySelectorAll('.ptext').forEach((pt) => { pt.style.opacity = tw(t, c.send + c.reply, 0.5).toFixed(3); });
    });
    // f1: the source file glows
    const g1 = CHAT[0].send + CHAT[0].reply + 0.9;
    $('f1chip').style.boxShadow = t >= g1 ? `0 0 0 ${(3 * vis(t, g1, g1 + 1.6, 0.3, 0.8)).toFixed(2)}px rgba(79,70,229,.35)` : 'none';
    // f2: the deadline card, then Karthi approves
    const c2 = CHAT[1], d2 = t >= c2.send + c2.click + 0.2;
    $('f2btns').style.display = d2 ? 'none' : 'flex'; $('f2done').style.display = d2 ? 'block' : 'none';
    $('f2hd').textContent = d2 ? '✓ Deadline moved · approved by Karthi M' : '🗓 Move this deadline?';
    $('f2card').classList.toggle('ok', d2);
    $('f2approve').style.transform = t >= c2.send + c2.click - 0.08 && t < c2.send + c2.click + 0.12 ? 'scale(0.94)' : 'none';
    // f3: Max checks both calendars, then the card
    const c3 = CHAT[2], s0 = c3.send + c3.reply, cardOn = t >= c3.send + c3.card - 0.25;
    op($('f3scan'), Math.min(tw(t, s0, 0.3), 1 - tw(t, c3.send + c3.card - 0.3, 0.3)));
    const sw = prog(t, s0 + 0.2, 1.4);
    $('f3line').style.left = `calc(150px + (100% - 174px) * ${sw.toFixed(4)})`;
    op($('f3line'), sw > 0 && sw < 1 ? 1 : 0);
    $('f3busy').style.boxShadow = t >= s0 + 0.9 ? `0 0 0 ${(3 * vis(t, s0 + 0.9, s0 + 2.2, 0.2, 0.4)).toFixed(2)}px rgba(240,68,56,.45)` : 'none';
    op($('f3free'), clamp((t - (s0 + 1.6)) * 4)); op($('f3res'), clamp((t - (s0 + 1.75)) * 4));
    $('f3scan').querySelectorAll('.dots b').forEach((b, i) => { b.style.opacity = (0.3 + 0.7 * Math.abs(Math.sin((t - i * 0.18) * 5))).toFixed(2); });
    const cp = tw(t, c3.send + c3.card - 0.3, 0.5);                       // crossfade: scan out, card in
    S($('f3card'), { opacity: (cardOn ? cp : 0).toFixed(3), transform: `translateY(${(1 - cp) * 18}px)` });
    const d3 = t >= c3.send + c3.click + 0.2;
    $('f3btns').style.display = d3 ? 'none' : 'flex'; $('f3done').style.display = d3 ? 'block' : 'none';
    $('f3hd').textContent = d3 ? '✓ Booked · approved by Karthi M' : '📅 Teams meeting for approval';
    $('f3card').classList.toggle('ok', d3);
    $('f3approve').style.transform = t >= c3.send + c3.click - 0.08 && t < c3.send + c3.click + 0.12 ? 'scale(0.94)' : 'none';
    // next morning: the brief
    grow($('fDiv'), tw(t, T.i4, 0.4, E.outCubic));
    grow($('fBrief'), tw(t, BRIEF_AT, 0.55, E.outCubic));
    // keep the newest message in view (bottom-anchored, like Teams)
    const vp = $('feedvp').offsetHeight, h = $('feed').offsetHeight;
    FEED_SCROLL = Math.max(0, h - vp + 18);
    $('feed').style.transform = `translateY(${-FEED_SCROLL}px)`;
    // Karthi's cursor approves the cards
    const K = $('curK'), r = $('ripple');
    const clickAt = (c, btn, from) => {
      const a = c.send + c.click - 1.0, click = c.send + c.click;
      if (t < a || t > click + 0.6) return false;
      const sp = chanScreen($(btn), t), p = tw(t, a, 0.9, E.inOutCubic);
      S(K, { transform: `translate(${lerp(from[0], sp.x, p) - 6}px, ${lerp(from[1], sp.y, p) - 4}px) scale(${t >= click - 0.08 && t < click + 0.12 ? 0.86 : 1})` });
      op(K, Math.min(tw(t, a, 0.25), 1 - tw(t, click + 0.3, 0.3)));
      if (t >= click && t < click + 0.55) { const q = prog(t, click, 0.55); S(r, { left: `${sp.x}px`, top: `${sp.y}px`, transform: `scale(${0.3 + q * 1.4})` }); op(r, (1 - q) * 0.9); }
      return true;
    };
    clickAt(c2, 'f2approve', [1500, 1040]) || clickAt(c3, 'f3approve', [1500, 1040]);
  }
  function audit(t) {
    const L = $('auditL');
    if (t < T.audit || t > T.finale + 0.3) { op(L, 0); return; }
    op(L, Math.min(tw(t, T.audit, 0.45, E.outCubic), 1 - tw(t, T.finale - 0.2, 0.4)));
    const c = tw(t, T.audit, 0.7);
    S($('auditCard'), { opacity: c.toFixed(3), transform: `translateY(${(1 - c) * 40}px)` });
    document.querySelectorAll('#auditCard .ar').forEach((r, i) => { const p = tw(t, T.audit + 0.2 + i * 0.2, 0.45); S(r, { opacity: p.toFixed(3), transform: `translateY(${(1 - p) * 12}px)` }); });
    L.style.transform = `scale(${1 + prog(t, T.audit, 4.0) * 0.025})`;
  }
  const W3 = ['Sourced.', 'Approved.', 'Logged.'];
  function threeWords(t) {
    const el = $('st');
    if (t < T.words || t > T.finale) return false;
    if (stCur !== 'w3') { stCur = 'w3'; $('stL1').innerHTML = W3.map((w) => `<span class="w">${w}</span>`).join('   '); $('stL2').innerHTML = ''; el.className = 'statement light'; }
    op(el, 1); el.style.top = '880px';
    el.querySelectorAll('.w').forEach((w, i) => {
      const p = spring(t, T.words + i * 0.6, 0.9), fade = 1 - tw(t, T.finale - 0.4, 0.35);
      S(w, { opacity: (clamp((t - T.words - i * 0.6) * 5) * fade).toFixed(3), transform: `scale(${0.7 + p * 0.3})` });
      w.style.color = i === 1 ? 'var(--indigo)' : 'var(--text)';
    });
    op($('scrimL'), vis(t, T.words - 0.2, T.finale, 0.4, 0.3)); $('scrim').className = 'scrim light';
    return true;
  }
  function finale(t) {
    const L = $('finalL');
    if (t < T.finale) { op(L, 0); return; }
    op(L, tw(t, T.finale, 0.6, E.outCubic));
    op($('tagWrap'), 1 - tw(t, T.lock - 0.5, 0.5, E.inOutCubic));
    $('tagline').querySelectorAll('.w').forEach((w, i) => {
      const p = tw(t, (i < 4 ? T.tag : T.tag2) + (i % 4) * 0.12, 0.7);
      S(w, { opacity: p.toFixed(3), transform: `translateY(${(1 - p) * 40}px)`, filter: `blur(${(1 - p) * 10}px)` });
    });
    const lk = tw(t, T.lock, 0.9);
    op($('lockWrap'), lk); $('lockWrap').style.transform = `scale(${0.94 + lk * 0.06})`;
    const from = [[0, 30], [-50, 10], [50, 10], [-30, -40], [30, -45]];
    $('lockCloud').querySelectorAll('g:first-child circle').forEach((c, i) => { const p = spring(t, T.lock + i * 0.08, 1.1); c.setAttribute('transform', `translate(${((1 - p) * from[i][0]).toFixed(2)} ${((1 - p) * from[i][1]).toFixed(2)})`); });
    op($('halo'), 0.6 + 0.4 * tw(t, T.lock, 1.4));
    $('halo').style.transform = `scale(${0.85 + 0.15 * tw(t, T.finale, 6)})`;
  }

  // ---------------------------------------------------------------- frame
  function renderAt(t) {
    t = clamp(t, 0, T.END);
    const light = t >= T.chan + 0.2 && t < T.finale;
    op($('bgLight'), light ? 1 : 0); op($('bgDark'), light ? 0 : 1); op($('vig'), light ? 0.25 : 1);
    const maxTalk = MAX_LINES.some((k) => speaking(k, t));
    $('warm').style.setProperty('--wx', '62%'); $('warm').style.setProperty('--wy', '68%');
    op($('warm'), maxTalk && t < T.end ? 0.9 : 0);
    avTo(t);
    call(t); cursors(t); channel(t); audit(t); finale(t); kinetic(t);
    if (!threeWords(t)) statement(t);
    grain(t); $('grain').style.opacity = light ? '0.035' : '0.07';
    const b1 = t >= T.black1 && t < T.relight + 0.4 ? Math.min(tw(t, T.black1, 0.4), 1 - tw(t, T.relight, 0.5)) : 0;
    op($('black'), Math.max(1 - tw(t, 0, 0.6), b1, tw(t, T.out, T.END - T.out, E.inOutCubic)));
  }

  // ---------------------------------------------------------------- boot
  function measure() {
    const bb = posOf($('btnBook')), mb = posOf($('btnMail'));
    BTN = { book: { x: bb.x + bb.w / 2, y: bb.y + bb.h / 2 }, mail: { x: mb.x + mb.w / 2, y: mb.y + mb.h / 2 } };
    const top = posOf($('cBook')).y;
    SCROLL = { mail: Math.max(0, posOf($('cMail')).y - top), draft: Math.max(0, posOf($('cDraft')).y - top) };
  }
  function fit() {
    if (RENDER) { stage.style.transform = 'none'; return; }
    stage.style.transform = `scale(${Math.min(innerWidth / 1920, (innerHeight - 44) / 1080)})`;
  }
  window.renderAt = renderAt;
  document.fonts.ready.then(() => {
    measure(); fit(); renderAt(0);
    window.FILM_READY = true;
    if (RENDER) return;
    const ctl = document.createElement('div');
    ctl.className = 'ctl';
    ctl.innerHTML = `<button id="pp">Play</button><span id="tc">0.0s</span><input id="scrub" type="range" min="0" max="${T.END}" step="0.033" value="0"><span>space: play/pause · ←/→: 1 s</span>`;
    document.body.appendChild(ctl);
    const audio = new Audio('../out/mix.wav');
    let playing = false, t0 = 0, start = 0;
    const tick = () => {
      if (!playing) return;
      const t = start + (performance.now() - t0) / 1000;
      if (t >= T.END) { playing = false; $('pp').textContent = 'Play'; return; }
      renderAt(t); $('scrub').value = t; $('tc').textContent = `${t.toFixed(1)}s`;
      realRAF(tick);
    };
    const play = () => {
      playing = !playing; $('pp').textContent = playing ? 'Pause' : 'Play';
      if (playing) { start = +$('scrub').value; t0 = performance.now(); audio.currentTime = start; audio.play().catch(() => {}); realRAF(tick); } else audio.pause();
    };
    $('pp').onclick = play;
    $('scrub').oninput = (e) => { const t = +e.target.value; renderAt(t); $('tc').textContent = `${t.toFixed(1)}s`; if (playing) { start = t; t0 = performance.now(); audio.currentTime = t; } };
    addEventListener('keydown', (e) => {
      if (e.code === 'Space') { e.preventDefault(); play(); }
      if (e.code === 'ArrowRight' || e.code === 'ArrowLeft') { const t = clamp(+$('scrub').value + (e.code === 'ArrowRight' ? 1 : -1), 0, T.END); $('scrub').value = t; renderAt(t); $('tc').textContent = `${t.toFixed(1)}s`; }
    });
    const jump = parseFloat(params.get('t'));
    if (!Number.isNaN(jump)) { $('scrub').value = jump; renderAt(jump); }
    addEventListener('resize', fit);
  });
})();
