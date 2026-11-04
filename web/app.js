/* RAGNAROK — client for the "RAGNAROK Final" interface.
   Plain DOM, no framework: static shell in index.html, small render functions here.
   Server state comes from /api/state; chats are fetched per chat and cached. */
(() => {
  'use strict';

  // ── tiny helpers ─────────────────────────────────────────────────────────
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const shortName = (n) => String(n).replace(/_/g, ' ');
  const TAG = { PDF: 't-pdf', DOCX: 't-doc', TXT: 't-doc', XLSX: 't-xls', XLS: 't-xls', CSV: 't-xls', IMG: 't-img' };
  const tagCls = (fmt) => TAG[fmt] || 't-doc';
  const IMG_EXT = ['png', 'jpg', 'jpeg', 'webp', 'bmp'];
  const fmtOf = (name) => {
    const e = (name.split('.').pop() || '').toLowerCase();
    if (IMG_EXT.includes(e)) return 'IMG';
    return { docx: 'DOCX', txt: 'TXT', xls: 'XLS', xlsx: 'XLSX', csv: 'CSV', pdf: 'PDF' }[e] || (e.toUpperCase().slice(0, 4) || 'FILE');
  };
  const ALLOWED = ['pdf', 'csv', 'xlsx', 'xls', 'docx', 'txt', ...IMG_EXT];
  const plural = (n, w) => `${n} ${w}${n === 1 ? '' : 's'}`;
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } },
  };

  // Session id: per tab, survives reloads. getRandomValues works on plain http too.
  const SID = (() => {
    try { const s = sessionStorage.getItem('rg_sid'); if (s && /^[0-9a-f]{32}$/.test(s)) return s; } catch (e) {}
    const b = new Uint8Array(16); crypto.getRandomValues(b);
    const s = Array.from(b, (x) => x.toString(16).padStart(2, '0')).join('');
    try { sessionStorage.setItem('rg_sid', s); } catch (e) {}
    return s;
  })();

  async function api(path, opts = {}) {
    const res = await fetch(path, { ...opts, headers: { 'X-Session': SID, ...(opts.headers || {}) } });
    if (!res.ok) {
      let msg = `${res.status} ${res.statusText}`;
      try { const j = await res.json(); if (j.detail) msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail); } catch (e) {}
      throw new Error(msg);
    }
    return res;
  }

  /** POST and read a text/event-stream body, calling onEvent(name, data) per event. */
  async function stream(path, body, onEvent) {
    const res = await api(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = '';
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let i;
      while ((i = buf.indexOf('\n\n')) >= 0) {
        const raw = buf.slice(0, i); buf = buf.slice(i + 2);
        let ev = 'message', data = '';
        for (const line of raw.split('\n')) {
          if (line.startsWith('event:')) ev = line.slice(6).trim();
          else if (line.startsWith('data:')) data += line.slice(5).trim();
        }
        if (data) onEvent(ev, JSON.parse(data));
      }
    }
  }

  let toastTimer;
  function toast(msg) {
    const t = $('toast'); t.textContent = msg; t.hidden = false;
    clearTimeout(toastTimer); toastTimer = setTimeout(() => { t.hidden = true; }, 5000);
  }

  // ── state ────────────────────────────────────────────────────────────────
  const S = {
    server: { keysOk: true, docs: [], chats: [], settings: { model: 'gpt-4o', k: 15, fetch_k: 30, lambda: 0.5 }, models: ['gpt-4o', 'gpt-4o-mini'], fixed: { temperature: 0, memory: 5 }, eval: null },
    page: 'chat', active: null, chats: {}, pending: [], indexing: false,
    asking: false, traces: {}, src: null, evalRunning: false, evalProgress: '',
  };

  // ── theme ────────────────────────────────────────────────────────────────
  function paintTheme() {
    const dark = document.documentElement.dataset.t === 'dark';
    $('themeGlyph').textContent = dark ? '☾' : '☀';
  }
  $('themeToggle').onclick = () => {
    const next = document.documentElement.dataset.t === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.t = next; store.set('rg_theme', next); paintTheme();
  };

  // ── citations: [Source 3: file, Page 2] → numbered badges ────────────────
  const CITE_GROUP = /[ \t]*\[([^\[\]]*?Source\s+\d+[^\[\]]*)\]/g;   // eats the space before it: badge sits on the word
  const CITE_NUM = /Source\s+(\d+)/g;
  const MARK_A = '', MARK_B = '';

  /** Returns {html, order}: order[displayNo-1] = 0-based index into sources. */
  function renderAnswer(content, nSources, streaming) {
    let text = content;
    if (streaming) text = text.replace(/\[[^\]\n]{0,240}$/, '');     // hide a half-written citation
    const order = [];
    text = text.replace(CITE_GROUP, (_, inner) => {
      const nums = [];
      for (const m of inner.matchAll(CITE_NUM)) {
        const n = parseInt(m[1], 10);
        if (n >= 1 && n <= nSources) {
          let d = order.indexOf(n - 1);
          if (d < 0) { order.push(n - 1); d = order.length - 1; }
          if (!nums.includes(d + 1)) nums.push(d + 1);
        }
      }
      return nums.length ? MARK_A + nums.join(',') + MARK_B : '';
    });
    let html = window.marked ? marked.parse(text, { gfm: true, breaks: false }) : `<p>${esc(text)}</p>`;
    html = window.DOMPurify ? DOMPurify.sanitize(html) : html;
    html = html.replace(new RegExp(`${MARK_A}([\\d,]+)${MARK_B}`, 'g'), (_, list) =>
      list.split(',').map((d) => `<span class="cite" role="button" tabindex="0" data-d="${d}">${d}</span>`).join(''));
    if (streaming) html = html.replace(/(<\/(p|li|td|h\d)>\s*)$/, '<span class="caret"></span>$1') || html;
    return { html, order };
  }

  // ── fallback highlight (word overlap) if the server's meaning-based one is missing ──
  const STOP = new Set('the and for that with this from are was were has have had not but its their they them which what when where who will would can could should into than then there these those also such been being about after before over under per each other only more most some any all our your his her him she you'.split(' '));
  const words = (s) => (s.toLowerCase().match(/[\p{L}\p{N}][\p{L}\p{N}.,%'-]*/gu) || [])
    .map((w) => w.replace(/[.,'-]+$/, '')).filter((w) => w.length > 2 && !STOP.has(w));

  /** Split passage into [pre, hl, post] around the sentence sharing most words with the claim. */
  function highlight(passage, claim) {
    const want = new Set(words(claim || ''));
    if (!want.size) return null;
    const re = /[^.!?\n]+(?:[.!?]+["”’)]*|\n|$)/g;
    let best = null, bestScore = 0, m;
    while ((m = re.exec(passage)) !== null) {
      if (!m[0].trim()) { if (re.lastIndex === m.index) re.lastIndex++; continue; }
      const ws = words(m[0]);
      if (!ws.length) continue;
      const hit = new Set(ws.filter((w) => want.has(w))).size;
      const score = hit / Math.sqrt(new Set(ws).size);
      if (score > bestScore) { bestScore = score; best = [m.index, m.index + m[0].length]; }
    }
    if (!best || bestScore < 0.5) return null;
    let [a, b] = best;
    while (a < b && /\s/.test(passage[a])) a++;
    while (b > a && /\s/.test(passage[b - 1])) b--;
    return [passage.slice(0, a), passage.slice(a, b), passage.slice(b)];
  }

  // ── sidebar ──────────────────────────────────────────────────────────────
  const CHAT_ICON = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/></svg>';
  const X_ICON = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg>';

  function renderSide() {
    const chats = S.server.chats;
    $('recentSec').hidden = !chats.length;
    $('history').innerHTML = chats.map((c) => {
      const on = c.id === S.active && S.page === 'chat';
      return `<button class="hist${on ? ' on' : ''}" data-chat="${esc(c.id)}">${CHAT_ICON}<span class="ellip">${esc(c.title)}</span></button>`;
    }).join('');

    const docs = S.server.docs;
    $('docsLabel').textContent = `Documents · ${docs.length}`;
    const rows = docs.map((d) => `
      <div class="doc">
        <span class="tag ${tagCls(d.fmt)}">${esc(d.fmt)}</span>
        <div class="doc-body"><div class="doc-name" title="${esc(d.name)}">${esc(shortName(d.name))}</div><div class="doc-meta">${esc(d.meta)}</div></div>
        <button class="doc-x" data-remove="${esc(d.name)}" title="Remove" aria-label="Remove ${esc(d.name)}"${S.indexing ? ' disabled' : ''}>${X_ICON}</button>
      </div>`);
    S.pending.forEach((f, i) => rows.push(`
      <div class="doc">
        <span class="tag ${tagCls(fmtOf(f.name))}">${esc(fmtOf(f.name))}</span>
        <div class="doc-body"><div class="doc-name" title="${esc(f.name)}">${esc(shortName(f.name))}</div><div class="doc-meta pending">${S.indexing ? 'Indexing…' : 'Ready to index'}</div></div>
        <button class="doc-x" data-unpend="${i}" title="Remove" aria-label="Remove ${esc(f.name)}"${S.indexing ? ' disabled' : ''}>${X_ICON}</button>
      </div>`));
    $('docs').innerHTML = rows.join('');

    const ib = $('indexBtn');
    ib.hidden = !S.pending.length;
    ib.disabled = S.indexing;
    ib.textContent = S.indexing ? 'Indexing…' : S.pending.length > 1 ? `Index ${S.pending.length} new files` : 'Index new file';

    document.querySelectorAll('.nav').forEach((n) => n.classList.toggle('on', n.dataset.page === S.page));
  }

  // ── head ─────────────────────────────────────────────────────────────────
  function renderHead() {
    const chat = S.active && S.server.chats.find((c) => c.id === S.active);
    $('headTitle').textContent = S.page === 'eval' ? 'Evaluation' : S.page === 'settings' ? 'Settings' : chat ? chat.title : 'New chat';
    $('scope').hidden = S.page !== 'chat';
    $('scope').textContent = `${S.server.docs.length} documents · ${S.server.settings.model}`;
  }

  // ── chat view ────────────────────────────────────────────────────────────
  const SUGGESTIONS = ['Summarise the key points of each document', 'What dates or deadlines are mentioned?', 'List every total or figure that appears'];

  function renderEmpty() {
    const n = S.server.docs.length;
    if (!S.server.keysOk) {
      $('heroTitle').textContent = 'Add your API keys';
      $('heroSub').innerHTML = 'Create a <code>.env</code> file in the project root with <code>OPENAI_API_KEY</code> and <code>PINECONE_API_KEY</code>, then restart the server.';
      $('emptyCol').hidden = true;
      return;
    }
    $('emptyCol').hidden = false;
    $('heroTitle').textContent = n ? 'What should we look up?' : 'Start with your documents';
    $('heroSub').textContent = n
      ? `I'll answer from your ${plural(n, 'document')} and show where each fact came from.`
      : 'Add PDFs, Word files, spreadsheets or images, then index them. Every answer shows where it came from.';
    $('suggest').innerHTML = n ? SUGGESTIONS.map((q) => `<button class="chip" data-suggest="${esc(q)}">${esc(q)}</button>`).join('') : '';
  }

  function msgHTML(m, idx, chatId) {
    if (m.role === 'user') return `<div class="msg"><div class="user">${esc(m.text)}</div></div>`;
    if (m.role === 'pending') {
      return `<div class="msg"><div class="bot pending"><div class="avatar">R</div><div class="reading">Reading ${plural(S.server.docs.length, 'document')}<span class="dots"><i></i><i></i><i></i></span></div></div></div>`;
    }
    if (m.role === 'error') return `<div class="msg"><div class="bot"><div class="avatar">R</div><div class="bot-body"><div class="err-line">${esc(m.text)}</div></div></div></div>`;

    const sources = m.sources || [];
    const { html, order } = renderAnswer(m.content || '', sources.length, !!m.streaming);
    m._order = order;
    const key = `${chatId}:${idx}`;
    const open = !!S.traces[key];
    const notes = order.map((si, d) => {
      const s = sources[si];
      const on = S.src && S.src.key === key && S.src.d === d + 1;
      return `<button class="note-card${on ? ' on' : ''}" data-note="${d + 1}">
        <span class="num">${d + 1}</span>
        <div class="note-main">
          <div class="note-top"><span class="tag tag-sm ${tagCls(s.fmt)}">${esc(s.fmt)}</span><span class="note-name" title="${esc(s.doc)}">${esc(shortName(s.doc))}</span></div>
          <div class="note-loc">${esc(s.loc)}</div>
        </div></button>`;
    }).join('');
    const t = m.trace;
    const trace = t ? `
      <div class="trace">
        <button class="trace-pill" data-trace="${key}" aria-expanded="${open}"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg>How this was found · ${esc(t.total)}</button>
        ${open ? `<div class="trace-box">
          <div class="trace-q">Searched as <em>“${esc(t.standalone)}”</em></div>
          ${t.steps.map(([node, status, time]) => `<div class="step"><span class="step-ok"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5 9-10"/></svg></span><span class="step-node">${esc(node)}</span><span class="step-status">${esc(status)}</span><span class="step-time">${esc(time)}</span></div>`).join('')}
        </div>` : ''}
      </div>` : '';
    return `<div class="msg" data-key="${key}"><div class="bot"><div class="avatar">R</div><div class="bot-body">
      <div class="answer">${html}</div>
      ${!m.streaming && notes ? `<div class="notes">${notes}</div>` : ''}
      ${trace}
    </div></div></div>`;
  }

  function currentMessages() {
    return (S.active && S.chats[S.active]) ? S.chats[S.active].messages : [];
  }

  function renderThread() {
    const msgs = currentMessages();
    $('thread').innerHTML = msgs.map((m, i) => msgHTML(m, i, S.active)).join('');
  }

  /** Re-render only the streaming message (cheap enough per animation frame). */
  let rafPending = false;
  function renderStreaming() {
    if (rafPending) return;
    rafPending = true;
    requestAnimationFrame(() => {
      rafPending = false;
      const msgs = currentMessages();
      const i = msgs.length - 1;
      const el = $('thread').lastElementChild;
      if (i < 0 || !el) return renderThread();
      const nearBottom = window.innerHeight + window.scrollY >= document.body.scrollHeight - 160;
      el.outerHTML = msgHTML(msgs[i], i, S.active);
      if (nearBottom) window.scrollTo(0, document.body.scrollHeight);
    });
  }

  function renderChat() {
    const hasChat = currentMessages().length > 0;
    $('empty').hidden = hasChat;
    $('threadWrap').hidden = !hasChat;
    if (!hasChat) renderEmpty(); else renderThread();
    document.querySelectorAll('[data-send]').forEach((b) => { b.disabled = S.asking; });
  }

  // ── evaluation view ──────────────────────────────────────────────────────
  function renderEval() {
    const ev = S.server.eval;
    const btn = $('runEval');
    btn.disabled = S.evalRunning;
    btn.textContent = S.evalRunning ? 'Running…' : 'Run evaluation';
    const n = S.server.docs.length;
    $('evalNote').textContent = S.evalRunning ? S.evalProgress
      : !n ? 'Index documents first; questions run against this session’s documents.'
      : ev ? `Last run today, ${ev.ranAt} · ${plural(ev.n, 'question')}` : `Runs against your ${plural(n, 'document')}`;

    $('evalResults').hidden = !ev;
    if (!ev) return;
    $('metrics').innerHTML = ev.means.map((mt) => {
      const v = mt.value;
      const has = typeof v === 'number';
      const [word, cls] = !has ? ['No score', 'v-fair'] : v > 0.8 ? ['Good', 'v-good'] : v > 0.6 ? ['Fair', 'v-fair'] : ['Needs work', 'v-poor'];
      const pct = has ? Math.max(0, Math.min(100, Math.round(v * 100))) : 0;
      return `<div class="metric">
        <div class="metric-top"><div class="metric-label">${esc(mt.label)}</div><div class="verdict ${cls}">${word}</div></div>
        <div class="metric-val">${has ? v.toFixed(2) : '—'}</div>
        <div class="bar"><div style="width:${pct}%"></div></div>
        <div class="metric-hint">${esc(mt.hint)}</div></div>`;
    }).join('');
    const f = (x) => (typeof x === 'number' ? x.toFixed(2) : '—');
    $('evalRows').innerHTML = ev.rows.map((r) => `<div class="qrow"><span>${esc(r.question)}</span>${ev.keys.map((k) => `<span>${f(r.scores[k])}</span>`).join('')}</div>`).join('');
    $('evalCsv').href = `api/eval.csv?sid=${SID}`;
  }

  // ── settings view ────────────────────────────────────────────────────────
  function renderSettings() {
    const st = S.server.settings;
    const row = (label, hint, inner) => `<div class="set-row"><div class="set-text"><div class="set-label">${label}</div><div class="set-hint">${hint}</div></div>${inner}</div>`;
    const stepper = (key, value, canDec, canInc) =>
      `<button class="step-btn" data-dec="${key}" aria-label="Decrease"${canDec ? '' : ' disabled'}>−</button><div class="set-val">${value}</div><button class="step-btn" data-inc="${key}" aria-label="Increase"${canInc ? '' : ' disabled'}>+</button>`;
    $('settings').innerHTML = [
      row('Model', 'Click to switch', `<button class="set-val cycle" id="cycleModel">${esc(st.model)}</button>`),
      row('Passages per answer', 'How many passages the model reads', stepper('k', st.k, st.k > 2, st.k < st.fetch_k)),
      row('Search pool', 'Passages searched before picking', stepper('fetch_k', st.fetch_k, st.fetch_k > st.k, st.fetch_k < 60)),
      row('Variety', 'Higher = closest matches, lower = more varied', stepper('lambda', Number(st.lambda).toFixed(1), st.lambda > 0, st.lambda < 1)),
      row('Temperature', 'Kept at 0 for factual answers', `<div class="set-val fixed">${Number(S.server.fixed.temperature).toFixed(1)}</div>`),
      row('Memory', 'Previous turns used for follow-ups', `<div class="set-val fixed">${S.server.fixed.memory}</div>`),
    ].join('');
    const exp = $('exportBtn');
    const can = !!(S.active && currentMessages().some((m) => m.role === 'bot'));
    exp.setAttribute('aria-disabled', String(!can));
    exp.href = can ? `api/export?chat_id=${encodeURIComponent(S.active)}&sid=${SID}` : '#';
  }

  // ── drawer ───────────────────────────────────────────────────────────────
  function openSource(key, d) {
    const [chatId, idxStr] = key.split(':');
    const m = S.chats[chatId] && S.chats[chatId].messages[+idxStr];
    if (!m || !m._order) return;
    const s = m.sources[m._order[d - 1]];
    if (!s) return;
    S.src = { key, d };

    // The claim: every answer block that cites this number.
    const msgEl = document.querySelector(`.msg[data-key="${CSS.escape(key)}"]`);
    let claim = '';
    if (msgEl) {
      msgEl.querySelectorAll(`.cite[data-d="${d}"]`).forEach((c) => {
        const block = c.closest('p, li, td, h1, h2, h3, h4, blockquote') || c.parentElement;
        claim += ' ' + block.textContent;
      });
    }
    $('srcN').textContent = d;
    $('srcDoc').textContent = s.doc.replace(/_/g, '_​');
    const hl = s.hl && s.hl.text && s.text.includes(s.hl.text) ? s.hl : null;
    $('srcMeta').innerHTML = `<span class="tag tag-md ${tagCls(s.fmt)}">${esc(s.fmt)}</span><span>${esc(s.loc)}</span>`
      + `<span>·</span><span title="How close this passage is in meaning to your question (cosine similarity)">question match ${Number(s.score).toFixed(2)}</span>`
      + (hl ? `<span>·</span><span title="How close the highlighted sentence is in meaning to the claim that cites it (cosine similarity)">claim match ${Number(hl.score).toFixed(2)}</span>` : '');
    const img = $('srcImg');
    img.hidden = !s.isImg;
    if (s.isImg) img.innerHTML = `<img alt="${esc(s.doc)}" src="api/files?name=${encodeURIComponent(s.doc)}&sid=${SID}" onerror="this.parentNode.textContent='Image preview'">`;
    // Preferred: the server's meaning-based pick. Fallback: the sentence sharing the most words.
    let parts, note;
    if (hl) {
      const a = s.text.indexOf(hl.text);
      parts = [s.text.slice(0, a), hl.text, s.text.slice(a + hl.text.length)];
      note = 'Highlighted: the sentence closest in meaning to the claim that cites it.';
    } else {
      parts = highlight(s.text, claim);
      note = parts ? 'Highlighted: the sentence sharing the most words with the claim that cites it.' : 'The whole passage the answer cites.';
    }
    $('srcText').innerHTML = parts
      ? `<span>${esc(parts[0])}</span><mark>${esc(parts[1])}</mark><span>${esc(parts[2])}</span>`
      : `<span>${esc(s.text)}</span>`;
    $('srcNote').textContent = note;
    $('scrim').hidden = false; $('drawer').hidden = false;
    renderThread();
    $('srcClose').focus();
  }
  function closeSource() {
    if (!S.src) return;
    S.src = null; $('scrim').hidden = true; $('drawer').hidden = true; renderThread();
  }

  // ── top-level render ─────────────────────────────────────────────────────
  function render() {
    renderSide(); renderHead();
    $('chatView').hidden = S.page !== 'chat';
    $('evalView').hidden = S.page !== 'eval';
    $('settingsView').hidden = S.page !== 'settings';
    if (S.page === 'chat') renderChat();
    if (S.page === 'eval') renderEval();
    if (S.page === 'settings') renderSettings();
  }

  function setServer(st) { S.server = st; }

  async function refresh() {
    try { setServer(await (await api('api/state')).json()); } catch (e) { toast(e.message); }
    render();
  }

  async function openChat(id) {
    S.page = 'chat'; S.active = id; closeSource();
    if (!S.chats[id]) {
      try {
        const c = await (await api(`api/chats/${encodeURIComponent(id)}`)).json();
        S.chats[id] = { messages: c.messages };
      } catch (e) { toast(e.message); }
    }
    render(); window.scrollTo(0, document.body.scrollHeight);
  }

  // ── ask ──────────────────────────────────────────────────────────────────
  const drafts = [$('draftBig'), $('draftDock')];
  const setDraft = (v) => drafts.forEach((d) => { if (d.value !== v) d.value = v; });
  drafts.forEach((d) => {
    d.addEventListener('input', () => setDraft(d.value));
    d.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(); } });
  });

  async function send(text) {
    const q = (text ?? $('draftBig').value).trim();
    if (!q || S.asking) return;
    if (!S.server.keysOk) return toast('Add your API keys first.');
    if (!S.server.docs.length) return toast(S.pending.length ? 'Index your new files first.' : 'Add and index at least one document first.');

    S.asking = true; setDraft('');
    let chatId = S.active;
    const local = chatId && S.chats[chatId] ? S.chats[chatId] : { messages: [] };
    const tempId = chatId || '__new';
    S.chats[tempId] = local;
    S.active = tempId; S.page = 'chat';
    local.messages.push({ role: 'user', text: q }, { role: 'pending' });
    render(); window.scrollTo(0, document.body.scrollHeight);

    let bot = null;
    try {
      await stream('api/ask', { chat_id: chatId === '__new' ? null : chatId, question: q }, (ev, data) => {
        if (ev === 'chat') {
          if (data.id !== tempId) { delete S.chats[tempId]; S.chats[data.id] = local; }
          S.active = data.id;
          if (!S.server.chats.some((c) => c.id === data.id)) S.server.chats = [{ id: data.id, title: data.title }, ...S.server.chats];
          renderSide(); renderHead();
        } else if (ev === 'sources') {
          bot = { role: 'bot', content: '', sources: data.sources, streaming: true };
        } else if (ev === 'token') {
          if (local.messages[local.messages.length - 1].role === 'pending') { local.messages.pop(); local.messages.push(bot); renderThread(); }
          bot.content += data.t; renderStreaming();
        } else if (ev === 'done') {
          if (local.messages[local.messages.length - 1].role === 'pending') { local.messages.pop(); local.messages.push(bot); }
          bot.streaming = false; bot.trace = data.trace;
          for (const [i, h] of Object.entries(data.highlights || {})) if (bot.sources[+i]) bot.sources[+i].hl = h;
          if (S.src && S.src.key === `${S.active}:${local.messages.length - 1}`) {
            renderThread(); openSource(S.src.key, S.src.d);       // a source opened mid-answer gets its highlight now
          }
        } else if (ev === 'error') {
          throw new Error(data.message);
        }
      });
    } catch (e) {
      // The server drops the unanswered question from history; mirror that here.
      const ms = local.messages;
      while (ms.length && ms[ms.length - 1].role !== 'user') ms.pop();
      if (ms.length) ms.pop();
      ms.push({ role: 'error', text: `Couldn't answer: ${e.message}` });
      setDraft(q);
      // A chat that never got an answer is dropped server-side; drop it from Recent too.
      if (!ms.some((m) => m.role === 'bot')) S.server.chats = S.server.chats.filter((c) => c.id !== S.active);
    } finally {
      S.asking = false; render();
    }
  }

  // ── documents ────────────────────────────────────────────────────────────
  function addFiles(list) {
    const have = new Set([...S.server.docs.map((d) => d.name), ...S.pending.map((f) => f.name)]);
    const skipped = [];
    for (const f of list) {
      const ext = (f.name.split('.').pop() || '').toLowerCase();
      if (!ALLOWED.includes(ext)) { skipped.push(f.name); continue; }
      if (!have.has(f.name)) { S.pending.push(f); have.add(f.name); }
    }
    if (skipped.length) toast(`Not supported: ${skipped.join(', ')}`);
    renderSide();
  }

  async function indexPending() {
    if (S.indexing || !S.pending.length) return;
    if (!S.server.keysOk) return toast('Add your API keys first.');
    S.indexing = true; renderSide();
    const fd = new FormData();
    S.pending.forEach((f) => fd.append('files', f, f.name));
    try {
      setServer(await (await api('api/documents', { method: 'POST', body: fd })).json());
      const n = S.pending.length;
      S.pending = [];
      toast(`Indexed ${plural(n, 'file')}`);
    } catch (e) {
      toast(e.message);
      await refresh();   // some files may have been indexed before the failure
      const done = new Set(S.server.docs.map((d) => d.name));
      S.pending = S.pending.filter((f) => !done.has(f.name));
    } finally {
      S.indexing = false; render();
    }
  }

  async function removeDoc(name) {
    try { setServer(await (await api(`api/documents?name=${encodeURIComponent(name)}`, { method: 'DELETE' })).json()); }
    catch (e) { toast(e.message); }
    render();
  }

  $('fileInput').addEventListener('change', (e) => { addFiles(e.target.files); e.target.value = ''; });
  $('indexBtn').onclick = indexPending;
  const side = $('side'), drop = $('drop');
  ['dragenter', 'dragover'].forEach((t) => side.addEventListener(t, (e) => { if (e.dataTransfer && [...e.dataTransfer.types].includes('Files')) { e.preventDefault(); drop.classList.add('over'); } }));
  ['dragleave', 'drop'].forEach((t) => side.addEventListener(t, (e) => { if (t === 'dragleave' && side.contains(e.relatedTarget)) return; drop.classList.remove('over'); }));
  side.addEventListener('drop', (e) => { if (e.dataTransfer && e.dataTransfer.files.length) { e.preventDefault(); addFiles(e.dataTransfer.files); } });

  // ── evaluation ───────────────────────────────────────────────────────────
  async function runEval() {
    if (S.evalRunning) return;
    const text = $('evalText').value;
    if (!text.trim()) return toast('Add at least one question.');
    if (!S.server.docs.length) return toast('Index at least one document first.');
    S.evalRunning = true; S.evalProgress = 'Starting…'; renderEval();
    const skipped = [];
    try {
      await stream('api/eval', { questions: text }, (ev, data) => {
        if (ev === 'progress') { S.evalProgress = data.text; renderEval(); }
        else if (ev === 'skipped') skipped.push(data.question);
        else if (ev === 'result') S.server.eval = data;
        else if (ev === 'error') throw new Error(data.message);
      });
      if (skipped.length) toast(`Skipped ${plural(skipped.length, 'question')} that failed to answer.`);
    } catch (e) { toast(e.message); }
    finally { S.evalRunning = false; renderEval(); }
  }
  $('runEval').onclick = runEval;

  // ── settings ─────────────────────────────────────────────────────────────
  async function patchSettings(patch) {
    S.server.settings = { ...S.server.settings, ...patch };   // optimistic
    renderSettings(); renderHead();
    try { setServer(await (await api('api/settings', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(patch) })).json()); }
    catch (e) { toast(e.message); await refresh(); return; }
    renderSettings(); renderHead();
  }
  $('settings').addEventListener('click', (e) => {
    const st = S.server.settings;
    const t = e.target.closest('button');
    if (!t || t.disabled) return;
    if (t.id === 'cycleModel') {
      const ms = S.server.models; patchSettings({ model: ms[(ms.indexOf(st.model) + 1) % ms.length] }); return;
    }
    const key = t.dataset.dec || t.dataset.inc;
    if (!key) return;
    const dir = t.dataset.dec ? -1 : 1;
    if (key === 'k') patchSettings({ k: Math.min(st.fetch_k, Math.max(2, st.k + dir)) });
    if (key === 'fetch_k') patchSettings({ fetch_k: Math.min(60, Math.max(st.k, st.fetch_k + dir * 5)) });
    if (key === 'lambda') patchSettings({ lambda: Math.min(1, Math.max(0, Math.round((st.lambda + dir * 0.1) * 10) / 10)) });
  });
  $('clearBtn').onclick = async () => {
    try { setServer(await (await api('api/clear', { method: 'POST' })).json()); } catch (e) { toast(e.message); }
    Object.assign(S, { page: 'chat', active: null, chats: {}, pending: [], traces: {} });
    closeSource(); setDraft(''); render();
  };

  // ── global clicks ────────────────────────────────────────────────────────
  document.addEventListener('click', (e) => {
    const t = e.target;
    const by = (sel) => t.closest(sel);
    let el;
    if ((el = by('[data-add]'))) { $('fileInput').click(); return; }
    if ((el = by('[data-send]'))) { send(); return; }
    if ((el = by('[data-chat]'))) { openChat(el.dataset.chat); return; }
    if ((el = by('[data-remove]'))) { removeDoc(el.dataset.remove); return; }
    if ((el = by('[data-unpend]'))) { S.pending.splice(+el.dataset.unpend, 1); renderSide(); return; }
    if ((el = by('[data-suggest]'))) { setDraft(el.dataset.suggest); $('draftBig').focus(); return; }
    if ((el = by('[data-page]'))) { S.page = el.dataset.page; closeSource(); render(); window.scrollTo(0, 0); return; }
    if ((el = by('[data-trace]'))) { S.traces[el.dataset.trace] = !S.traces[el.dataset.trace]; renderThread(); return; }
    if ((el = by('.cite'))) { const msg = el.closest('.msg'); if (msg) openSource(msg.dataset.key, +el.dataset.d); return; }
    if ((el = by('[data-note]'))) { const msg = el.closest('.msg'); if (msg) openSource(msg.dataset.key, +el.dataset.note); return; }
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeSource();
    if ((e.key === 'Enter' || e.key === ' ') && e.target.classList && e.target.classList.contains('cite')) { e.preventDefault(); e.target.click(); }
  });
  $('newChat').onclick = () => { S.page = 'chat'; S.active = null; closeSource(); render(); $('draftBig').focus(); };
  $('scrim').onclick = closeSource;
  $('srcClose').onclick = closeSource;

  paintTheme();
  refresh();
})();
