// Hevanti (הבנתי) - the "ask the AI" box, shared by the app, the floating window and the player - (c) 2026 Roei Pechter. MIT License, see LICENSE.txt
// Three buttons, the same for every AI: a click copies the question together with what was said in the lecture
// and opens that AI's site in a new tab - there one pastes (Ctrl+V) and sends. No account or key passes through
// Hevanti. An AI app that is connected to Hevanti ("חיבור AI" on the home screen) needs no copying at all:
// one asks it straight in its own window, and it reads the lecture by itself.
"use strict";
(function () {
  const AIS = [
    {id: "chatgpt", name: "ChatGPT", url: "https://chatgpt.com/", app: "ChatGPT למחשב"},
    {id: "gemini", name: "Gemini", url: "https://gemini.google.com/app", app: "Gemini"},
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
`;
  const AI = {connected: {}};
  const boxes = [];
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
    const ta = mk("textarea"); ta.rows = opts.rows || 2; ta.dir = "auto";
    ta.placeholder = opts.placeholder || "מה לא ברור?";
    ta.setAttribute("aria-label", "השאלה");
    const row = mk("div", "ais"); row.setAttribute("role", "group"); row.setAttribute("aria-label", "לאן לשלוח");
    const hint = mk("p", "hint", "הלחיצה מעתיקה את השאלה עם מה שנאמר ופותחת את האתר - שם Ctrl+V ושליחה.");
    const buttons = {};
    function refresh() {
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
    async function send(a) {
      const q = ta.value.trim();
      const ok = await copyText(opts.context(q), opts.win);
      if (!ok) { opts.toast("לא הצלחתי להעתיק. לנסות שוב."); return; }
      setLast(a.id); refresh();
      // (not the "noopener" feature: with it window.open always returns null, and a blocked popup looks the same)
      let w = null;
      try { w = (opts.win || window).open(a.url, "_blank"); if (w) w.opener = null; } catch (e) { w = null; }
      const img = opts.hasImage && opts.hasImage() ? " צריך גם את המסך? \"העתקת " + (opts.imageName || "צילום המסך") + "\" ולהדביק שוב." : "";
      opts.toast((w === null ? "הועתק. לפתוח את " + a.name + " ולהדביק (Ctrl+V)." : "הועתק ונפתח " + a.name + ". להדביק (Ctrl+V) ולשלוח.") + img);
      ta.value = "";
    }
    for (const a of AIS) {
      const bt = mk("button", "", a.name); bt.type = "button"; bt.dataset.ai = a.id;
      bt.title = "מעתיק את השאלה עם ההקשר ופותח את " + a.name;
      bt.addEventListener("click", () => send(a));
      buttons[a.id] = bt; row.appendChild(bt);
    }
    ta.addEventListener("keydown", e => {
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); send(AIS.find(a => a.id === getLast()) || AIS[0]); }
    });
    refresh();
    box.append(head, conn, ta, row, hint);
    return {focus: () => ta.focus(), textarea: ta, refresh};
  }
  window.BZMAsk = {mount, AIS, copyText, setConnected, addCss};
})();
