// Hevanti (הבנתי) - the "ask the AI" box, shared by the app and the player - (c) 2026 Roei Pechter. MIT License, see LICENSE.txt
// A click copies the question together with what was said in the lecture, then opens the chosen AI site in a
// new tab: there one pastes (Ctrl+V) and sends. No account, key or login passes through the tool.
// "הבנתי עונה" answers inside the box with the student's own OpenAI key (the app sends it to OpenAI directly).
// "Claude במחשב" copies only a short note: Claude for desktop reads now_watching.txt in the tool's folder by itself.
"use strict";
(function () {
  const AIS = [
    {id: "chatgpt", name: "ChatGPT", url: "https://chatgpt.com/"},
    {id: "gemini", name: "Gemini", url: "https://gemini.google.com/app"},
    {id: "claude", name: "Claude", url: "https://claude.ai/new"},
    {id: "local", name: "Claude במחשב", url: ""},
  ];
  const KEY = "bzm.ai";
  const css = `
.askp{display:grid;gap:8px}
.askp .head{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}
.askp .head b{font-size:18px}
.askp .head small{color:var(--muted);font-size:13px}
.askp textarea{font:inherit;font-size:15px;color:var(--fg);background:var(--bg);border:1px solid var(--line);border-radius:10px;padding:8px 12px;resize:vertical;min-height:2.9em;width:100%}
.askp textarea:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
.askp .ais{display:flex;gap:6px;flex-wrap:wrap}
.askp .ais button{border:1.5px solid var(--accent);background:transparent;color:var(--accent);border-radius:10px;padding:5px 13px;font:inherit;font-size:14px;font-weight:600;cursor:pointer;white-space:nowrap}
.askp .ais button:hover{background:var(--accent-soft)}
.askp .ais button.last{background:var(--accent);color:var(--accent-ink)}
.askp .ais button.local{border-style:dashed}
.askp .hint{color:var(--muted);font-size:13px;line-height:1.5;margin:0}
.askp details{font-size:13px;color:var(--muted)}
.askp details summary{cursor:pointer;width:max-content;max-width:100%}
.askp details p{margin:4px 0 0}
.askp .ais button.mine{background:var(--accent);color:var(--accent-ink);border-color:var(--accent)}
.askp .ais button.mine:hover{filter:brightness(1.08);background:var(--accent)}
.askp .ais button[disabled]{opacity:.6;cursor:progress}
.askp .withimg{display:flex;gap:6px;align-items:center;font-size:14px;color:var(--muted)}
.askp .answer{background:var(--bg);border:1px solid var(--line);border-radius:12px;padding:12px 14px;display:grid;gap:8px}
.askp .answer .turn{display:grid;gap:6px}
.askp .answer .q{font-weight:700;color:var(--muted);font-size:15px}
.askp .answer .a{line-height:1.65}
.askp .answer .a p{margin:0 0 6px}
.askp .answer .a ul{margin:0 0 6px;padding-inline-start:20px}
.askp .answer .a .f{display:block;direction:ltr;text-align:center;font-family:Cambria Math,Cambria,serif;font-size:17px;margin:4px 0}
.askp .answer .tools{display:flex;gap:6px;flex-wrap:wrap;align-items:center;font-size:14px;color:var(--muted)}
.askp .answer .tools button{border:1.5px solid var(--line);background:var(--surface);border-radius:10px;padding:3px 10px;cursor:pointer;font:inherit;font-size:14px}
.askp .thinking{color:var(--muted);font-style:italic}
`;
  const AI = {available: false, on: false};
  const boxes = [];
  // the answer as text with light formatting: paragraphs, "- " lists, **bold**, a formula alone on its line
  function render(el, text) {
    el.replaceChildren();
    let list = null;
    for (const raw of String(text || "").split("\n")) {
      const line = raw.trimEnd();
      if (!line.trim()) { list = null; continue; }
      const m = line.match(/^\s*[-•*]\s+(.*)$/);
      const box = m ? document.createElement("li") : document.createElement("p");
      const body = m ? m[1] : line.replace(/^#+\s*/, "");
      if (!m && /^#/.test(line)) box.style.fontWeight = "700";
      if (!m && /^[\sA-Za-z0-9=+\-*/^().,·²³½√∑∫πθωαβΔ_]+$/.test(body) && /=/.test(body) && body.length < 80) box.className = "f";
      body.split(/(\*\*[^*]+\*\*)/).forEach(part => {
        if (/^\*\*[^*]+\*\*$/.test(part)) { const b = document.createElement("b"); b.textContent = part.slice(2, -2); box.appendChild(b); }
        else if (part) box.appendChild(document.createTextNode(part));
      });
      box.dir = "auto";
      if (m) { if (!list) { list = document.createElement("ul"); el.appendChild(list); } list.appendChild(box); }
      else { list = null; el.appendChild(box); }
    }
  }
  function getLast() { try { return localStorage.getItem(KEY) || ""; } catch (e) { return ""; } }
  function setLast(id) { try { localStorage.setItem(KEY, id); } catch (e) {} }
  async function copyText(t) {
    try { await navigator.clipboard.writeText(t); return true; }
    catch (e) {
      const ta = document.createElement("textarea"); ta.value = t; ta.style.position = "fixed"; ta.style.opacity = "0";
      document.body.appendChild(ta); ta.select(); let ok = false;
      try { ok = document.execCommand("copy"); } catch (e2) {}
      ta.remove(); return ok;
    }
  }
  // opts: context(question) -> the text for an AI site; local(question) -> the short note for Claude for desktop;
  //       toast(text); hasImage() -> true when there is a screenshot/slide the person may want to add
  function setAI(info) {
    AI.available = !!(info && info.available); AI.on = !!(info && info.on);
    for (const b of boxes) b();
  }
  function mount(box, opts) {
    if (!document.getElementById("askp-css")) {
      const st = document.createElement("style"); st.id = "askp-css"; st.textContent = css; document.head.appendChild(st);
    }
    box.classList.add("askp");
    box.innerHTML = "";
    const head = document.createElement("div"); head.className = "head";
    const b = document.createElement("b"); b.textContent = opts.title || "שאלה ל-AI";
    const sm = document.createElement("small"); sm.textContent = opts.sub || "עם מה שנאמר בהרצאה";
    head.append(b, sm);
    const ta = document.createElement("textarea"); ta.rows = 2; ta.dir = "auto";
    ta.placeholder = opts.placeholder || "מה לא ברור? (אפשר גם להשאיר ריק ולכתוב שם)";
    ta.setAttribute("aria-label", "השאלה");
    const row = document.createElement("div"); row.className = "ais"; row.setAttribute("role", "group"); row.setAttribute("aria-label", "לאן לשלוח");
    const hint = document.createElement("p"); hint.className = "hint";
    hint.textContent = "\"הבנתי עונה\" עונה כאן. ChatGPT, Gemini ו-Claude: הלחיצה מעתיקה את השאלה ואת ההקשר ופותחת את האתר - שם Ctrl+V ושליחה.";
    const more = document.createElement("details");
    more.innerHTML = "<summary>יש לכם Claude למחשב?</summary><p>אחרי שמחברים אליו פעם אחת את התיקייה &quot;ההרצאות שלי&quot; (במדריך: שאלות ל-AI ← Claude למחשב), " +
      "הוא קורא לבד מה קורה בהרצאה. \"Claude במחשב\" מעתיק רק את השאלה, ומדביקים אותה באפליקציה של Claude. " +
      "אפשר גם פשוט לשאול אותו שם, בלי הכפתור.</p>";
    const buttons = {};
    // built in: "הבנתי עונה" (the answer shows here; follow-up questions keep the conversation)
    const mine = document.createElement("button"); mine.type = "button"; mine.className = "mine"; mine.dataset.ai = "mine";
    mine.textContent = opts.mineLabel || "הבנתי עונה";
    mine.title = "התשובה מופיעה כאן, בלי להעתיק";
    const imgRow = document.createElement("label"); imgRow.className = "withimg"; imgRow.hidden = true;
    const imgBox = document.createElement("input"); imgBox.type = "checkbox"; imgBox.checked = true;
    imgRow.append(imgBox, document.createTextNode(opts.imageLabel || "לצרף את צילום המסך האחרון"));
    const answer = document.createElement("div"); answer.className = "answer"; answer.hidden = true;
    const turns = document.createElement("div"); turns.className = "turn";
    const tools = document.createElement("div"); tools.className = "tools";
    const left = document.createElement("span");
    const copyA = document.createElement("button"); copyA.type = "button"; copyA.textContent = "העתקת התשובה";
    const fresh = document.createElement("button"); fresh.type = "button"; fresh.textContent = "שאלה חדשה (בלי ההמשך)";
    tools.append(copyA, fresh, left);
    answer.append(turns, tools);
    let history = [], busy = false;
    function refresh() {
      mine.hidden = !opts.builtIn || !AI.on;
      imgRow.hidden = mine.hidden || !(opts.hasImage && opts.hasImage()) || !opts.builtIn.image;
      hint.textContent = (mine.hidden ? "" : "\"הבנתי עונה\" עונה כאן (עם מפתח OpenAI שלך). ") +
        "ChatGPT, Gemini ו-Claude: הלחיצה מעתיקה את השאלה ואת ההקשר ופותחת את האתר - שם Ctrl+V ושליחה." +
        (opts.builtIn && !AI.on ? " יש לך מפתח OpenAI? אפשר לחבר אותו במסך הבית (\"הבנתי עונה\" למטה), והתשובות יופיעו כאן." : "");
    }
    boxes.push(refresh);
    copyA.addEventListener("click", async () => {
      const last = history[history.length - 1];
      if (last) opts.toast((await copyText(last.a)) ? "התשובה הועתקה." : "לא הצלחתי להעתיק.");
    });
    fresh.addEventListener("click", () => { history = []; turns.replaceChildren(); answer.hidden = true; ta.focus(); });
    async function askMine() {
      if (busy) return;
      if (!AI.on) { if (opts.openSettings) opts.openSettings(); else opts.toast("צריך לחבר מפתח OpenAI (במסך הבית, \"הבנתי עונה\" למטה)."); return; }
      const q = ta.value.trim();
      const bi = opts.builtIn;
      if (!q && bi.task === "ask") { opts.toast("צריך לכתוב שאלה."); ta.focus(); return; }
      busy = true; mine.disabled = true;
      const t = document.createElement("div"); t.className = "turn";
      const qEl = document.createElement("div"); qEl.className = "q"; qEl.textContent = q || bi.defaultQuestion || ""; qEl.dir = "auto";
      const aEl = document.createElement("div"); aEl.className = "a thinking"; aEl.textContent = "חושב...";
      t.append(qEl, aEl); turns.appendChild(t); answer.hidden = false;
      const payload = Object.assign({task: bi.task || "ask", question: q || bi.defaultQuestion || "", history}, bi.payload ? bi.payload() : {});
      if (!imgRow.hidden && imgBox.checked && bi.image) payload.image = bi.image();
      let out;
      try {
        out = await fetch("/api/ai", {method: "POST", headers: {"Content-Type": "application/json", "X-BZM": "1"}, body: JSON.stringify(payload)}).then(r => r.json());
      } catch (e) { out = {ok: false, error: "האפליקציה לא ענתה. אולי היא נסגרה."}; }
      busy = false; mine.disabled = false;
      aEl.classList.remove("thinking");
      if (out.ok) {
        render(aEl, out.answer + (out.cut ? "\n(התשובה נקטעה כי היא ארוכה. אפשר לכתוב \"תמשיך\".)" : ""));
        history.push({q: payload.question, a: out.answer}); ta.value = "";
        const cost = c => "$" + (c < 0.01 ? c.toFixed(4) : c.toFixed(2));
        left.textContent = (out.cost != null ? "עלה בערך " + cost(out.cost) : (out.tokens ? out.tokens.toLocaleString("he-IL") + " טוקנים" : "")) +
          (out.month_usd != null ? " · החודש: " + cost(out.month_usd) : "");
        AI.month_usd = out.month_usd;
        if (opts.onAnswer) opts.onAnswer(out, payload);
      } else {
        aEl.textContent = out.error || "משהו השתבש. אפשר לנסות שוב.";
        if (out.need_key && opts.openSettings) opts.openSettings();
      }
    }
    mine.addEventListener("click", askMine);
    row.appendChild(mine);
    function mark() { const l = getLast(); for (const a of AIS) buttons[a.id].classList.toggle("last", a.id === l && AI.on !== null); }
    async function send(a) {
      const q = ta.value.trim();
      const text = a.id === "local" ? opts.local(q) : opts.context(q);
      const ok = await copyText(text);
      if (!ok) { opts.toast("לא הצלחתי להעתיק. לנסות שוב."); return; }
      setLast(a.id); mark();
      if (a.id === "local") {
        opts.toast("הועתק. להדביק באפליקציה של Claude (Ctrl+V) ולשלוח.");
      } else {
        // (not the "noopener" feature: with it window.open always returns null, and a blocked popup looks the same)
        let w = null;
        try { w = window.open(a.url, "_blank"); if (w) w.opener = null; } catch (e) { w = null; }
        const img = opts.hasImage && opts.hasImage() ? " צריך גם את המסך? \"העתקת " + (opts.imageName || "צילום המסך") + "\" ולהדביק שוב." : "";
        opts.toast((w === null ? "הועתק. לפתוח את " + a.name + " ולהדביק (Ctrl+V)." : "הועתק ונפתח " + a.name + ". להדביק (Ctrl+V) ולשלוח.") + img);
      }
      ta.value = "";
    }
    for (const a of AIS) {
      const bt = document.createElement("button"); bt.type = "button"; bt.textContent = a.name; bt.dataset.ai = a.id;
      if (a.id === "local") { bt.className = "local"; bt.title = "מעתיק רק את השאלה. Claude למחשב קורא לבד את now_watching.txt"; }
      else bt.title = "מעתיק ופותח את " + a.url;
      bt.addEventListener("click", () => send(a));
      buttons[a.id] = bt; row.appendChild(bt);
    }
    ta.addEventListener("keydown", e => {
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        if (!mine.hidden && AI.on && (getLast() === "mine" || !getLast())) { askMine(); return; }
        const l = AIS.find(a => a.id === getLast()) || AIS[0]; send(l);
      }
    });
    mine.addEventListener("click", () => { setLast("mine"); mark(); });
    mark(); refresh();
    box.append(head, ta, imgRow, row, answer, hint, more);
    return {focus: () => ta.focus(), textarea: ta, refresh, ask: askMine};
  }
  window.BZMAsk = {mount, AIS, copyText, setAI, render};
})();
