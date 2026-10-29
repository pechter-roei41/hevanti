// Hevanti (הבנתי) - the "ask the AI" box, shared by the app, the floating window and the player - (c) 2026 Roei Pechter. MIT License, see LICENSE.txt
// A course may have a project of its own in each AI (its link is saved on the course page): the buttons then open
// THAT project, on a third of the screen - where the AI already reads the course by itself.
// Three buttons, the same for every AI: a click copies the question together with what was said in the lecture
// and opens that AI's site in a new tab - there one pastes (Ctrl+V) and sends. No account or key passes through
// Hevanti. An AI app that is connected to Hevanti ("חיבור AI" on the home screen) needs no copying at all:
// one asks it straight in its own window, and it reads the lecture by itself.
"use strict";
(function () {
  const AIS = [
    {id: "chatgpt", name: "ChatGPT", url: "https://chatgpt.com/", app: "ChatGPT למחשב"},
    {id: "gemini", name: "Gemini", url: "https://gemini.google.com/app", app: "Gemini (agy)"},
    {id: "claude", name: "Claude", url: "https://claude.ai/new", app: "Claude למחשב"},
  ];
  const KEY = "bzm.ai";
  const css = `
.askp{display:grid;gap:8px}
.askp .head{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}
.askp .head b{font-size:18px}
.askp .head small{color:var(--muted);font-size:13px}
.askp textarea{font:inherit;font-size:15px;color:var(--fg);background:var(--bg);border:1px solid var(--line);border-radius:10px;padding:8px 12px;resize:vertical;min-height:2.9em;width:100%;box-sizing:border-box}
.askp textarea:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
.askp .ais{display:flex;gap:6px;flex-wrap:wrap}
.askp .ais button{border:1.5px solid var(--accent);background:transparent;color:var(--accent);border-radius:10px;padding:5px 13px;font:inherit;font-size:14px;font-weight:600;cursor:pointer;white-space:nowrap}
.askp .ais button:hover{background:var(--accent-soft)}
.askp .ais button.last{background:var(--accent);color:var(--accent-ink)}
.askp .hint{color:var(--muted);font-size:13px;line-height:1.5;margin:0}
.askp .conn{background:var(--accent-soft);color:var(--fg);border-radius:10px;padding:7px 11px;font-size:14px;line-height:1.5;margin:0}
.askp .conn b{color:var(--accent)}
.askp .ais button.here{background:var(--accent);color:var(--accent-ink);border-color:var(--accent);font-weight:800}
.askp .ais button.here.stop{background:transparent;color:var(--accent)}
.askp .chips2{display:flex;gap:6px;flex-wrap:wrap}
.askp .chips2 button{border:1px solid var(--line);background:var(--bg);color:var(--fg);border-radius:999px;padding:2px 11px;font:inherit;font-size:13px;cursor:pointer}
.askp .chips2 button:hover{border-color:var(--accent)}
.askp .conv{display:grid;gap:8px;max-height:min(55vh,560px);overflow-y:auto}
.askp .conv:empty,.askp .convbar[hidden]{display:none}
.askp .qa{background:var(--bg);border:1px solid var(--line);border-radius:10px;padding:8px 12px}
.askp .qa .q{font-weight:700;margin:0 0 4px;color:var(--accent);font-size:14px}
.askp .qa .a{line-height:1.65;font-size:calc(15px * var(--tx, 1))}
.askp .qa .a .h{font-weight:800;margin-top:6px}
.askp .qa .a .li{padding-inline-start:6px}
.askp .qa .a .sp{height:.5em}
.askp .qa.err .a{color:var(--rec)}
.askp .convbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.askp .convbar button{border:0;background:none;color:var(--muted);text-decoration:underline;cursor:pointer;font:inherit;font-size:13px;padding:0}
.askp .plan{background:var(--accent-soft);color:var(--fg);border-radius:10px;padding:8px 11px;font-size:14px;line-height:1.5;display:grid;gap:6px}
.askp .plan .btns{display:flex;gap:6px;flex-wrap:wrap}
.askp .plan button{border:1.5px solid var(--accent);background:transparent;color:var(--accent);border-radius:10px;padding:4px 12px;font:inherit;font-size:14px;font-weight:600;cursor:pointer}
.askp .plan button:hover{background:var(--accent);color:var(--accent-ink)}
.askp .ais button.here.alt{background:transparent;color:var(--accent);font-weight:600}
.askp .alt-box{margin-top:6px;display:grid;gap:6px;font-size:14px;line-height:1.5;color:var(--fg)}
.askp .conv{gap:12px;padding-block:4px}
.askp .qa{display:grid;gap:6px;background:none;border:0;padding:0}
.askp .qa .q{justify-self:start;max-width:88%;margin:0;padding:7px 13px;border-radius:16px;background:var(--accent);color:var(--accent-ink);font-weight:600;font-size:calc(14.5px * var(--tx, 1));line-height:1.5}
.askp .qa .a{justify-self:end;max-width:96%;padding:8px 13px;border-radius:16px;background:var(--bg);border:1px solid var(--line)}
.askp .qa.err .a{border-color:var(--rec)}
`;
  // builtin: answers inside Hevanti with the student's free Gemini key (set from Hevanti's state)
  // plan: "paid" = the student has a paid ChatGPT / Claude / Gemini plan - questions and whole-lecture tasks go to that
  // AI's app (no quota); "free" = answers inside Hevanti, with the free Gemini quota; "" = not asked yet (asked once)
  const AI = {connected: {}, apps: {}, courseFn: null, builtin: false, plan: "", planKnown: false};
  // the default way to ask: inside Hevanti (free key) - unless the student pays for an AI of their own
  const hereDefault = () => AI.builtin && AI.plan !== "paid";
  const DEF_Q = "תסביר בפשטות את מה שנאמר בדקות האחרונות";
  // an answer as a few simple blocks: "# heading", "- item", **bold** - always as text (never HTML)
  function renderAnswer(doc, box, text) {
    box.replaceChildren();
    for (let line of String(text).split("\n")) {
      const p = doc.createElement("div"); p.dir = "auto";
      if (/^#{1,4}\s/.test(line)) { line = line.replace(/^#{1,4}\s*/, ""); p.className = "h"; }
      else if (/^\s*[-*•]\s+/.test(line)) { line = "• " + line.replace(/^\s*[-*•]\s+/, ""); p.className = "li"; }
      if (!line.trim()) p.className = "sp";
      for (const part of line.split(/(\*\*[^*]+\*\*)/)) {
        if (/^\*\*[^*]+\*\*$/.test(part)) { const b = doc.createElement("b"); b.textContent = part.slice(2, -2); p.appendChild(b); }
        else if (part) p.appendChild(doc.createTextNode(part.replace(/(^|[\s(])\*([^*\s][^*]*?)\*(?=$|[\s.,:;!?)])/g, "$1$2")));   // *italic* -> plain
      }
      box.appendChild(p);
    }
  }   // apps: the AI apps installed on this computer (from Hevanti)
  // the project links of the course the page is about now: {claude: "https://claude.ai/project/...", ...}
  async function courseLinks() {
    const c = AI.courseFn && AI.courseFn();
    if (!c) return {};
    try {
      const r = await fetch("/api/course?c=" + encodeURIComponent(c), {cache: "no-store", signal: AbortSignal.timeout(3000)});
      if (!r.ok) return {};
      const d = await r.json();
      return (d.ai && d.ai.links) || {};
    } catch (e) { return {}; }
  }
  // Ask Hevanti (the local server) to open the installed app - the browser itself cannot start programs
  async function openApp(a) {
    try {
      const r = await fetch("/api/cmd", {method: "POST", headers: {"Content-Type": "application/json", "X-BZM": "1"},
        body: JSON.stringify({action: "open_ai_app", app: a.id}), signal: AbortSignal.timeout(4000)}).then(r => r.json());
      return !!r.ok;
    } catch (e) { return false; }
  }
  function setApps(info) { AI.apps = info || {}; }
  const boxes = [];
  const aiWins = {}, aiUrls = {};   // the small window opened for each AI - reused, so the conversation there goes on
  // Open the AI's site in a window on a third of the screen (not a tab), so the lecture stays in view.
  // If that window is still open, only bring it forward: navigating it would start a new chat - unless another
  // course's project is wanted now.
  function openAi(a, from, url) {
    url = url || a.url;
    const old = aiWins[a.id];
    if (old && !old.closed) {
      if (aiUrls[a.id] !== url) { try { old.location.href = url; aiUrls[a.id] = url; } catch (e) {} }
      try { old.focus(); } catch (e) {}
      return {w: old, reused: aiUrls[a.id] === url && url === a.url};
    }
    const S = (from || window).screen || window.screen;
    // a third of the screen, full height, at the side: the lecture keeps the other two thirds
    const width = Math.max(420, Math.round((S.availWidth || 1440) / 3)), height = Math.max(400, (S.availHeight || 860) - 8);
    const feats = `popup=yes,width=${width},height=${height},left=${S.availLeft || 0},top=${S.availTop || 0}`;
    let w = null;
    // from the main page first; a click inside the floating window may only allow its own window.open
    for (const src of from && from !== window ? [window, from] : [window]) {
      try { w = src.open(url, "hevanti-" + a.id, feats); } catch (e) { w = null; }
      if (w) break;
    }
    if (w) { try { w.opener = null; } catch (e) {} aiWins[a.id] = w; aiUrls[a.id] = url; }
    return {w, reused: false};
  }
  function getLast() { try { return localStorage.getItem(KEY) || ""; } catch (e) { return ""; } }
  function setLast(id) { try { localStorage.setItem(KEY, id); } catch (e) {} }
  async function copyText(t, win) {
    const W = win || window;
    try { await W.navigator.clipboard.writeText(t); return true; }
    catch (e) {
      const d = W.document, ta = d.createElement("textarea"); ta.value = t; ta.style.position = "fixed"; ta.style.opacity = "0";
      d.body.appendChild(ta); ta.select(); let ok = false;
      try { ok = d.execCommand("copy"); } catch (e2) {}
      ta.remove(); return ok;
    }
  }
  // the AI apps connected to Hevanti: {claude: true, chatgpt: false, gemini: false}
  function setConnected(info) {
    AI.connected = info || {};
    for (const b of boxes) b();
  }
  function connectedNames() { return AIS.filter(a => AI.connected[a.id]).map(a => a.app); }
  function addCss(doc) {
    if (!doc.getElementById("askp-css")) {
      const st = doc.createElement("style"); st.id = "askp-css"; st.textContent = css; doc.head.appendChild(st);
    }
  }
  // opts: context(question) -> the text for an AI site; toast(text); hasImage() -> true when there is a
  //       screenshot/slide the person may want to add; win: the window the box lives in (the floating window)
  function mount(box, opts) {
    const doc = box.ownerDocument || document;
    addCss(doc);
    box.classList.add("askp");
    box.replaceChildren();
    const mk = (tag, cls, text) => { const e = doc.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
    const head = mk("div", "head");
    head.append(mk("b", "", opts.title || "שאלה ל-AI"), mk("small", "", opts.sub || "עם מה שנאמר בהרצאה"));
    const conn = mk("p", "conn"); conn.hidden = true;
    // asked once, in every box, until it is answered
    const planBox = mk("div", "plan"); planBox.hidden = true;
    planBox.append(mk("span", "", "יש לך מנוי בתשלום ל-ChatGPT, Claude או Gemini? (שאלה חד-פעמית)"),
      mk("span", "hint", "אם כן, שאלות והרצאות שלמות ילכו ישר לאפליקציה שלך, בלי מכסה. אם לא, הבנתי תענה כאן במכסה החינמית."));
    const planBtns = mk("div", "btns");
    for (const [val, label] of [["paid", "כן, יש לי מנוי"], ["free", "לא, חינם"]]) {
      const pb = mk("button", "", label); pb.type = "button";
      pb.addEventListener("click", () => savePlan(val));
      planBtns.appendChild(pb);
    }
    planBox.appendChild(planBtns);
    const ta = mk("textarea"); ta.rows = opts.rows || 2; ta.dir = "auto";
    ta.placeholder = opts.placeholder || "מה לא ברור?";
    ta.setAttribute("aria-label", "השאלה");
    const row = mk("div", "ais"); row.setAttribute("role", "group"); row.setAttribute("aria-label", "לאן לשלוח");
    const COPY_HINT = "הלחיצה מעתיקה את השאלה עם מה שנאמר ופותחת את האפליקציה (אם היא מותקנת) או את האתר בשליש המסך - שם Ctrl+V ושליחה.";
    const hint = mk("p", "hint", COPY_HINT);
    const buttons = {};
    // ---- the answer inside Hevanti (built-in, free Gemini key) ----
    const here = mk("button", "here", "תשובה כאן"); here.type = "button";
    here.title = "Gemini עונה כאן, בתוך הבנתי, עם מה שנאמר" + (opts.hasImage ? " והשקופית שעל המסך" : "") + ". Ctrl+Enter";
    const chips = mk("div", "chips2"); chips.setAttribute("role", "group"); chips.setAttribute("aria-label", "שאלות מוכנות");
    for (const c of opts.chips || ["תסביר בפשטות את מה שנאמר עכשיו", "תן דוגמה", "מה כתוב בשקופית?", "למה זה חשוב?"]) {
      const b = mk("button", "", c); b.type = "button";
      b.addEventListener("click", () => { if (hereDefault()) askHere(c); else { ta.value = c; ta.focus(); } });
      chips.appendChild(b);
    }
    const conv = mk("div", "conv"); conv.setAttribute("aria-live", "polite");
    const convbar = mk("div", "convbar"); convbar.hidden = true;
    const newBtn = mk("button", "", "שיחה חדשה"); newBtn.type = "button";
    newBtn.title = "Gemini שוכח את השאלות הקודמות בתיבה הזו (התשובות נשמרות בתיקיית ההרצאה)";
    newBtn.addEventListener("click", () => { hist.length = 0; conv.replaceChildren(); convbar.hidden = true; });
    convbar.append(newBtn, mk("span", "hint", "התשובות נשמרות בתיקיית ההרצאה, ב\"שאלות ותשובות.md\"."));
    const hist = [];
    let busy = false, ctl = null;
    function setBusy(on) {
      busy = on; here.textContent = on ? "■ עצירה" : "תשובה כאן"; here.classList.toggle("stop", on);
    }
    // The free quota is used up: the same question, with what was said, goes on in the student's own AI app
    // (the last one used first) - a click copies it and opens that AI, like the three buttons above.
    function offerElsewhere(qa, q, extra, wait) {
      const when = wait >= 600 ? "המכסה החינמית של היום נגמרה." : wait ? "המכסה החינמית נגמרה לרגע (עוד כ-" + wait + " שניות)." : "";
      const bx = mk("div", "alt-box"), rw = mk("div", "ais"), last = getLast();
      bx.append(mk("span", "", (when ? when + " " : "") + "להמשיך עכשיו באפליקציית AI אחרת, עם אותה שאלה ואותו הקשר:"));
      for (const a of [...AIS].sort((x, y) => (y.id === last) - (x.id === last))) {
        const b = mk("button", a.id === last ? "last" : "", a.name); b.type = "button";
        b.addEventListener("click", () => sendQ(a, q, extra));
        rw.appendChild(b);
      }
      bx.appendChild(rw); qa.appendChild(bx);
    }
    // ask Gemini through Hevanti; the answer appears here as it is written
    async function askHere(q, extra) {
      extra = extra || {};
      if (busy) { opts.toast("עוד עונה על השאלה הקודמת."); return; }
      q = String(q || "").trim();
      const shown = extra.title || q || "תסביר בפשטות את מה שנאמר עכשיו";
      let context = "";
      try { context = extra.context ? await extra.context() : await opts.context(q || "תסביר בפשטות את מה שנאמר בדקות האחרונות"); }
      catch (e) { context = q; }
      const qa = mk("div", "qa"), ae = mk("div", "a", "חושב..."); qa.append(mk("p", "q", shown), ae);
      conv.appendChild(qa); convbar.hidden = false; conv.scrollTop = conv.scrollHeight;
      const val = f => { try { return (f && f()) || ""; } catch (e) { return ""; } };
      const body = {context, question: shown, history: hist.slice(-6), task: extra.task || "",
        where: val(opts.where), f: val(opts.lecture), img: val(opts.image), n: val(opts.shotName), at: val(opts.at)};
      setBusy(true); ctl = new AbortController();
      let text = "";
      try {
        const r = await fetch("/api/ask", {method: "POST", headers: {"Content-Type": "application/json", "X-BZM": "1"},
          body: JSON.stringify(body), signal: ctl.signal});
        if (!r.ok || !r.body) {
          let d = {}; try { d = await r.json(); } catch (x) {}
          const er = new Error(d.error || "לא הצלחתי לקבל תשובה."); er.quota = !!d.quota; er.wait = d.wait || 0; throw er;
        }
        const rd = r.body.getReader(), dec = new TextDecoder();
        for (;;) {
          const {done, value} = await rd.read(); if (done) break;
          text += dec.decode(value, {stream: true}); renderAnswer(doc, ae, text); conv.scrollTop = conv.scrollHeight;
        }
        text += dec.decode(); renderAnswer(doc, ae, text || "(לא התקבלה תשובה)");
        if (text && !text.includes("\n\n⚠ ")) { hist.push({q: shown, a: text}); if (extra.onDone) extra.onDone(text); }
      } catch (e) {
        if (e.name === "AbortError") renderAnswer(doc, ae, (text ? text + "\n" : "") + "(נעצר)");
        else {
          qa.classList.add("err"); ae.textContent = e.message || "לא הצלחתי לקבל תשובה.";
          if (e.quota) offerElsewhere(qa, q || DEF_Q, extra, e.wait);   // the free quota is used up
        }
      } finally { setBusy(false); ctl = null; }
    }
    here.addEventListener("click", () => {
      if (busy) { if (ctl) ctl.abort(); return; }
      const q = ta.value.trim(); ta.value = ""; askHere(q);
    });
    function refresh() {
      here.hidden = !AI.builtin;
      here.classList.toggle("alt", AI.builtin && !hereDefault());   // a paid plan: the AI apps first, this one second
      planBox.hidden = !(AI.planKnown && !AI.plan);
      hint.textContent = hereDefault() ? "\"תשובה כאן\": Gemini עונה בתוך הבנתי, עם מה שנאמר" + (opts.hasImage ? " והשקופית" : "") +
        ". הכפתורים האחרים מעתיקים את השאלה ל-AI אחר." : COPY_HINT + (AI.builtin ? ' "תשובה כאן" עונה במכסה החינמית.' : "");
      const names = connectedNames();
      conn.hidden = !names.length || opts.noConnHint;
      conn.replaceChildren();
      if (names.length) {
        conn.append(mk("b", "", names.join(" ו-") + (names.length > 1 ? " מחוברים" : " מחובר") + " להבנתי: "),
          "אפשר פשוט לשאול " + (names.length > 1 ? "אותם" : "אותו") + " בחלון " + (names.length > 1 ? "שלהם" : "שלו") +
          " (למשל \"" + (opts.example || "מה הוא אמר עכשיו?") + "\"), בלי להעתיק.");
      }
      const l = getLast();
      for (const a of AIS) buttons[a.id].classList.toggle("last", a.id === l);
    }
    boxes.push(refresh);
    async function sendQ(a, q, extra) {   // true when the question was copied (and the AI opened)
      let text = "";
      try { text = extra && extra.context ? await extra.context() : await opts.context(q); } catch (e) { text = q; }   // (may read the slides' text first)
      const ok = await copyText(text, opts.win);
      if (!ok) { opts.toast("לא הצלחתי להעתיק. לנסות שוב."); return false; }
      setLast(a.id); refresh();
      // (not the "noopener" feature: with it window.open always returns null, and a blocked popup looks the same)
      const img = opts.hasImage && opts.hasImage() ? " צריך גם את המסך? \"העתקת " + (opts.imageName || "צילום המסך") + "\" ולהדביק שוב." : "";
      // the course's own project when it has one; else the app when it is installed, otherwise the website
      const link = (await courseLinks())[a.id] || "";
      const appFirst = AI.apps[a.id] && (!link || (a.id === "claude" && AI.connected.claude));
      if (link && !appFirst) {
        const {w} = openAi(a, opts.win, link);
        opts.toast(w === null ? "הועתק. לפתוח את הפרויקט של הקורס ב-" + a.name + " ולהדביק (Ctrl+V)."
          : "נפתח הפרויקט של הקורס ב-" + a.name + " בשליש המסך. השאלה הועתקה (Ctrl+V), או פשוט לשאול שם.");
        return true;
      }
      if (appFirst && await openApp(a)) {
        opts.toast("הועתק ונפתחה האפליקציה של " + a.name + ". להדביק (Ctrl+V) ולשלוח." +
          (AI.connected[a.id] ? " היא מחוברת להבנתי, אז אפשר גם פשוט לשאול שם" + (link ? ", בפרויקט של הקורס." : ".") : "") + img);
        return true;
      }
      const {w, reused} = openAi(a, opts.win);
      opts.toast((w === null ? "הועתק. לפתוח את " + a.name + " ולהדביק (Ctrl+V)."
        : reused ? "הועתק. להדביק (Ctrl+V) בחלון של " + a.name + " - השיחה שם ממשיכה."
        : "הועתק ונפתח " + a.name + " בשליש המסך. להדביק (Ctrl+V) ולשלוח.") + img);
      return true;
    }
    async function send(a) { const q = ta.value.trim(); if (await sendQ(a, q)) ta.value = ""; }
    for (const a of AIS) {
      const bt = mk("button", "", a.name); bt.type = "button"; bt.dataset.ai = a.id;
      bt.title = "מעתיק את השאלה עם ההקשר ופותח את " + a.name + " (האפליקציה אם היא מותקנת, אחרת האתר)";
      bt.addEventListener("click", () => send(a));
      buttons[a.id] = bt; row.appendChild(bt);
    }
    ta.addEventListener("keydown", e => {
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        if (hereDefault() && !e.shiftKey) { const q = ta.value.trim(); ta.value = ""; askHere(q); }
        else send(AIS.find(a => a.id === getLast()) || AIS[0]);
      }
    });
    row.prepend(here);
    refresh();
    // like a chat: the conversation first (it grows downward), the box to write in under it
    box.append(head, planBox, conn, conv, convbar, ta, row, chips, hint);
    return {focus: () => ta.focus(), textarea: ta, refresh, askHere, builtin: hereDefault};
  }
  // open an AI for the course page's "פתיחה בשליש": the course's project link, the connected app, or the site
  async function openFor(id, link) {
    const a = AIS.find(x => x.id === id);
    if (!a) return;
    if (AI.apps[id] && (!link || (id === "claude" && AI.connected.claude)) && await openApp(a)) return;
    openAi(a, window, link || a.url);
  }
  function setCourseFn(fn) { AI.courseFn = fn; }
  // the plan is kept by Hevanti (the same in every window): "paid", "free" or "" (not asked yet)
  function setPlan(p) {
    p = p === "paid" || p === "free" ? p : "";
    if (p !== AI.plan || !AI.planKnown) { AI.plan = p; AI.planKnown = true; for (const b of boxes) b(); }
  }
  async function savePlan(plan) {
    try {
      const r = await fetch("/api/cmd", {method: "POST", headers: {"Content-Type": "application/json", "X-BZM": "1"},
        body: JSON.stringify({action: "math_set", plan}), signal: AbortSignal.timeout(4000)}).then(r => r.json());
      if (r && r.ok) setPlan((r.math && r.math.plan) || plan);
    } catch (e) {}
  }
  function setBuiltin(on) {
    on = !!on;
    if (on !== AI.builtin) { AI.builtin = on; for (const b of boxes) b(); }
  }
  window.BZMAsk = {mount, AIS, copyText, setConnected, setApps, addCss, openFor, setCourseFn, setBuiltin, setPlan};
})();
