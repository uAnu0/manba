/* Result cards for the Manba test console: one compact card per quote / claim / close match, opened like a tab.
   Usage: Cards.render(container, apiResponse, { headers: () => ({...}) }). No dependencies. */
const Cards = (() => {
  const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const TITLES = {
    supported: "Evidence supports this claim", supported_weakly: "Supported only by weak evidence", supported_in_part: "Supported in part",
    contradicted: "Evidence contradicts this claim", mixed: "Evidence on both sides", no_clear_evidence: "No clear evidence found",
    refer_to_scholar: "Ask a scholar", out_of_scope: "Not a religious claim", quote_checked: "Quoted text checked", evidence_only: "Related texts (no verdict)" };
  const SHORT = {
    supported: "Supported", supported_weakly: "Weak evidence only", supported_in_part: "Supported in part", contradicted: "Contradicted",
    mixed: "Both sides", no_clear_evidence: "No clear evidence", refer_to_scholar: "Ask a scholar", out_of_scope: "Not religious", evidence_only: "Related texts only" };
  const CHIP = { supported: "ok", supported_weakly: "warn", supported_in_part: "warn", contradicted: "bad", mixed: "warn", no_clear_evidence: "", refer_to_scholar: "warn", out_of_scope: "", evidence_only: "" };
  const STRENGTH = { quran: ["Quran", "ok"], sahihayn: ["Sahih al-Bukhari / Muslim", "ok"], sahih: ["graded Sahih", "ok"], hasan: ["graded Hasan", "warn"],
    daif: ["graded weak", "bad"], disputed: ["grading disputed", "warn"], ungraded: ["no grading here", "warn"] };
  const GROUPS = { claims: "Claims", quotes: "Quran & hadith quotes", similar: "Close matches", fragments: "Short phrases" };
  const ORDER = ["q_verified", "supported", "supported_in_part", "supported_weakly", "mixed", "contradicted", "no_clear_evidence", "q_variant", "q_partial", "q_baseless",
    "similar", "refer_to_scholar", "evidence_only", "out_of_scope", "q_fragment", "quote_checked"];
  const FRAGMENT_WORDS = 4;  // a verified run this short is a stock phrase, not a quotation: kept apart so it does not inflate "verified"

  // ---------- small pieces of markup ----------
  const strengthChip = s => { const m = STRENGTH[s.strength]; return m ? `<span class="chip ${m[1]}">Level ${s.level} · ${m[0]}</span>` : ""; };
  const gradeChips = s => (s.grades || []).map(g => `<span class="chip">${esc(g.grade)} · ${esc(g.name)}</span>`).join("");
  const whereOf = (s, cls) => [s.book, s.chapter && cls === "quran" ? s.chapter : "", s.number].filter(Boolean).join(" · ");

  function evidenceItem(it, cls) {
    const s = it.source;
    const covers = (it.covers || []).length ? `<div class="small">Supports this part of the claim: <b>${it.covers.map(esc).join(" · ")}</b></div>` : "";
    const says = it.says ? `<div class="small">The judge's note: ${esc(it.says)}</div>` : "";
    const full = it.full_text && it.full_text !== s.matched_text
      ? `<details><summary>Full text${it.classification === "hadith" ? " with chain of narrators" : ""}</summary><div class="ar">${esc(it.full_text)}</div></details>` : "";
    return `<div class="item ${cls}"><div class="meta"><span class="src">${esc(whereOf(s, it.classification))}</span>${strengthChip(s)}${gradeChips(s)}</div><div class="ar">${esc(s.matched_text)}</div>${covers}${says}${full}</div>`;
  }
  const list = (title, items, cls) => items.length ? `<h4>${title} (${items.length})</h4>` + items.map(i => evidenceItem(i, cls)).join("") : "";

  function segmentHtml(sg) {
    const st = { verified: ["Verified", "ok"], semantic_variant: ["Wording differs", "warn"], baseless: ["Not found in the sources", "bad"] }[sg.status] || [sg.status, ""];
    const s = sg.source;
    const diffs = (sg.differences || []).length ? `<ul class="small" dir="rtl">${sg.differences.map(d => `<li>${esc(d)}</li>`).join("")}</ul>` : "";
    return `<div class="item"><div class="meta"><span class="chip ${st[1]}">${st[0]}</span>${s ? strengthChip(s) : ""}${s ? `<span class="src">${esc([s.book, s.number].filter(Boolean).join(" · "))}</span>` : ""}${s ? gradeChips(s) : ""}</div><div class="ar">${esc(sg.segment_text)}</div>${diffs}</div>`;
  }

  function similarHtml(sm) {
    const e = sm.evidence, s = e.source;
    const miss = (sm.missing_words || []).length ? `<div class="small" dir="rtl">كلمات في الجملة ليست في هذا النص: <b>${sm.missing_words.map(esc).join("، ")}</b></div>` : "";
    return `<div class="item related"><div class="meta"><span class="chip warn">Close to a known text, not the same wording</span><span class="src">${esc(whereOf(s, e.classification))}</span>${strengthChip(s)}${gradeChips(s)}</div>`
      + `<div class="small">The sentence shares ${Math.round(sm.shared_share * 100)}% of its distinctive words with this text. Read both: this is a pointer, not a verification.</div>`
      + `<div class="ar">${esc(e.full_text.length > 600 ? s.matched_text : e.full_text)}</div>${miss}</div>`;
  }

  // ---------- entries: one per card ----------
  function entriesOf(data) {
    if (data.items) return data.items.map(it => ({ kind: it.kind, text: it.text, start: it.start, result: it.result, quote: it.quote, similar: it.similar }));
    return [{ kind: "claim", text: data.claim, start: 0, result: data }];
  }

  const quoteStatus = (status, text) => {
    if (status === "verified") {
      if ((text || "").trim().split(/\s+/).length <= FRAGMENT_WORDS) return { key: "q_fragment", label: "Matched phrase", cls: "", attention: false, group: "fragments" };
      return { key: "q_verified", label: "Verified quote", cls: "ok", attention: false, group: "quotes" };
    }
    if (status === "semantic_variant") return { key: "q_variant", label: "Wording differs", cls: "warn", attention: true, group: "quotes" };
    return { key: "q_baseless", label: "Not found", cls: "bad", attention: true, group: "quotes" };
  };

  function statusOf(e) {
    if (e.kind === "similar") return { key: "similar", label: "Close to a known text", cls: "warn", attention: true, group: "similar" };
    if (e.kind === "quote") return quoteStatus(e.quote.status, e.text);
    const r = e.result;
    if (r.outcome === "quote_checked") {
      // The card stands for the WHOLE sentence: a verified fragment inside it does not make the sentence a verified quote.
      const sg = (r.quote_check && r.quote_check.segments) || [];
      if (!sg.length) return { key: "quote_checked", label: "Quoted text checked", cls: "blue", attention: false, group: "quotes" };
      const words = t => (t || "").trim().split(/\s+/).filter(Boolean).length;
      const total = Math.max(1, words(e.text));
      const verified = sg.filter(x => x.status === "verified").reduce((n, x) => n + words(x.segment_text), 0);
      if (verified / total >= 0.6) return quoteStatus("verified", e.text);
      if (verified) return { key: "q_partial", label: "Only a part matches", cls: "warn", attention: true, group: "quotes" };
      const variant = sg.find(x => x.status === "semantic_variant");
      return quoteStatus(variant ? "semantic_variant" : "baseless", e.text);
    }
    return { key: r.outcome, label: SHORT[r.outcome] || r.outcome, cls: CHIP[r.outcome] || "", attention: !["supported", "out_of_scope"].includes(r.outcome), group: "claims" };
  }

  function bestSource(e) {
    let s = null, cls = "hadith";
    if (e.kind === "quote") s = e.quote.source;
    else if (e.kind === "similar") { s = e.similar.evidence.source; cls = e.similar.evidence.classification; }
    else {
      const r = e.result, sg = r.quote_check && r.quote_check.segments.find(x => x.source);
      const it = (r.supporting || [])[0] || (r.partial || [])[0] || (r.contradicting || [])[0];
      if (sg) s = sg.source; else if (it) { s = it.source; cls = it.classification; } else if (r.similar) { s = r.similar.evidence.source; cls = r.similar.evidence.classification; }
    }
    if (!s) return "";
    if (s.book === "القرآن الكريم") cls = "quran";
    return `<span class="src">${esc(whereOf(s, cls))}</span>${strengthChip(s)}`;
  }

  // ---------- the tabs inside an opened card ----------
  function tabsOf(e, idx, store) {
    const tabs = [];
    const r = e.result;
    if (e.kind === "claim") {
      const ev = [...(r.supporting || []), ...(r.contradicting || [])];
      if (ev.length) tabs.push({ id: "evidence", label: "Evidence", n: ev.length, html: () => list("Evidence that supports the claim", r.supporting || [], "supports") + list("Evidence that contradicts the claim", r.contradicting || [], "contradicts") });
      const side = [...(r.partial || []), ...(r.related || [])];
      if (side.length) tabs.push({ id: "related", label: r.outcome === "evidence_only" ? "Related texts" : "Partial & related", n: side.length, html: () => list("Texts that support only part of the claim", r.partial || [], "supports") + list(r.outcome === "evidence_only" ? "Related texts" : "Related, but not deciding", r.related || [], "related") });
      if (r.quote_check) tabs.push({ id: "quote", label: "Quote check", html: () => r.quote_check.segments.map(segmentHtml).join("") });
      if (r.similar) tabs.push({ id: "similar", label: "Close text", html: () => similarHtml(r.similar) });
    } else if (e.kind === "quote") {
      tabs.push({ id: "quote", label: "Quote check", html: () => segmentHtml(e.quote) });
    } else {
      tabs.push({ id: "similar", label: "Close text", html: () => similarHtml(e.similar) });
    }
    const payload = e.kind === "claim" ? { claim: e.text, result: r } : e.kind === "quote" ? { claim: e.text, segment: e.quote } : null;
    if (payload && !(e.kind === "claim" && r.outcome === "out_of_scope")) {
      store[idx] = payload;
      tabs.push({ id: "explain", label: "Explain · اشرح", html: () => `<div class="explain"><button class="explain-btn" data-i="${idx}">Explain in Arabic · اشرح</button><div class="small">Written by an AI from the texts in this card only. It starts only when you click.</div><div class="explain-out"></div></div>` });
    }
    return tabs;
  }

  function panelHtml(e, tabs, idx) {
    let head = "";
    if (e.kind === "claim") {
      const r = e.result;
      head += `<div class="outcome ${esc(r.outcome)}"><h3>${esc(TITLES[r.outcome] || r.outcome)}</h3><p>${esc(r.summary_en)}</p><p dir="rtl">${esc(r.summary_ar)}</p></div>`;
      if (r.refer_to_scholar && r.reason) head += `<div class="banner"><b>Please ask a qualified scholar.</b> ${esc(r.reason)}</div>`;
      if (r.llm && r.llm.error) head += `<div class="err">${esc(r.llm.error)}</div>`;
    }
    const bar = `<div class="tabbar" role="tablist">${tabs.map((t, i) => `<button role="tab" class="tab" data-card="${idx}" data-tab="${t.id}" aria-selected="${i === 0}">${esc(t.label)}${t.n ? ` <span class="count">${t.n}</span>` : ""}</button>`).join("")}</div>`;
    const notice = e.kind === "claim" ? `<div class="notice" dir="auto"><b>${esc(e.result.notice_en)}</b><span dir="rtl" style="display:block;margin-top:4px">${esc(e.result.notice_ar)}</span></div>` : "";
    return `${head}${bar}<div class="tabbody"></div>${notice}`;
  }

  // ---------- the page: summary strip, filters, cards ----------
  function render(container, data, opts = {}) {
    const entries = entriesOf(data).map((e, i) => Object.assign(e, { i, st: statusOf(e) }));
    const store = {};
    const state = { group: "all", attention: false, status: null };
    const tabsFor = entries.map(e => tabsOf(e, e.i, store));

    const counts = {};
    for (const e of entries) counts[e.st.key] = counts[e.st.key] || { n: 0, label: e.st.label, cls: e.st.cls };
    for (const e of entries) counts[e.st.key].n++;
    const groupCount = g => entries.filter(e => e.st.group === g).length;
    const needs = entries.filter(e => e.st.attention).length;

    let intro = "";
    if (data.items) {
      intro += `<div class="small" style="margin:10px 0">${entries.length} item(s) found in ${data.sentences} sentence(s); ${data.commentary_sentences} sentence(s) were commentary.${data.skipped_claims ? ` ${data.skipped_claims} more claim(s) were not checked (limit per request).` : ""}${data.truncated ? " The text was longer than the limit; only the first part was read." : ""}</div>`;
      if (data.llm && data.llm.error) intro += `<div class="err">${esc(data.llm.error)}</div>`;
      if (!data.llm || !data.llm.used) intro += `<div class="banner">No model was used, so only quoted texts were checked.</div>`;
    }
    const multi = entries.length > 1;
    const root = document.createElement("div");  // listeners live on a fresh element, so re-rendering never stacks them
    container.replaceChildren(root);
    root.innerHTML = intro + (multi ? `<div class="strip" id="strip"></div><div class="filters" id="filters"></div>` : "") + `<div class="cards" id="cards"></div>`;
    const cardsEl = root.querySelector("#cards");

    cardsEl.innerHTML = entries.map(e => `
      <article class="card" data-i="${e.i}" data-group="${e.st.group}" data-status="${e.st.key}" data-needs="${e.st.attention ? 1 : 0}">
        <button class="card-head" aria-expanded="false" data-i="${e.i}">
          <span class="badge chip ${e.st.cls}">${esc(e.st.label)}</span>
          <span class="card-text ar">${esc(e.text)}</span>
          <span class="card-src">${bestSource(e)}</span>
          <span class="chev" aria-hidden="true">▾</span>
        </button>
        <div class="card-panel" hidden></div>
      </article>`).join("");

    function showTab(card, idx, tabId) {
      const tab = tabsFor[idx].find(t => t.id === tabId);
      card.querySelectorAll(".tab").forEach(b => b.setAttribute("aria-selected", String(b.dataset.tab === tabId)));
      card.querySelector(".tabbody").innerHTML = tab.html();
    }
    function toggle(card, open) {
      const idx = +card.dataset.i, head = card.querySelector(".card-head"), panel = card.querySelector(".card-panel");
      const want = open === undefined ? head.getAttribute("aria-expanded") !== "true" : open;
      head.setAttribute("aria-expanded", String(want));
      panel.hidden = !want;
      card.classList.toggle("open", want);
      if (want && !panel.dataset.built) {  // built on first opening: a long sermon stays light
        panel.dataset.built = "1";
        panel.innerHTML = panelHtml(entries[idx], tabsFor[idx], idx);
        if (tabsFor[idx].length) showTab(card, idx, tabsFor[idx][0].id);
      }
    }

    cardsEl.addEventListener("click", async ev => {
      const head = ev.target.closest(".card-head");
      if (head) return toggle(head.closest(".card"));
      const tab = ev.target.closest(".tab");
      if (tab) return showTab(tab.closest(".card"), +tab.dataset.card, tab.dataset.tab);
      const btn = ev.target.closest(".explain-btn");
      if (!btn) return;
      const out = btn.parentElement.querySelector(".explain-out");
      btn.disabled = true; out.innerHTML = `<div class="small">Writing the explanation…</div>`;
      try {
        const res = await fetch("/api/explain", { method: "POST", headers: Object.assign({ "Content-Type": "application/json" }, opts.headers ? opts.headers() : {}), body: JSON.stringify(store[+btn.dataset.i]) });
        const d = await res.json();
        if (!res.ok) throw new Error(res.status === 401 ? "The server needs an access code: enter it in Settings." : JSON.stringify(d));
        out.innerHTML = explainHtml(d); btn.remove();
      } catch (e) { out.innerHTML = `<div class="err">${esc(e.message)}</div>`; btn.disabled = false; }
    });

    function applyFilters() {
      cardsEl.querySelectorAll(".card").forEach(c => {
        const ok = (state.group === "all" ? c.dataset.group !== "fragments" || state.status === "q_fragment" : c.dataset.group === state.group)
          && (!state.attention || c.dataset.needs === "1") && (!state.status || c.dataset.status === state.status);
        c.hidden = !ok;
      });
      const shown = [...cardsEl.querySelectorAll(".card")].filter(c => !c.hidden).length;
      let none = cardsEl.querySelector(".none");
      if (!shown && !none) { cardsEl.insertAdjacentHTML("beforeend", `<div class="none small">Nothing matches this filter.</div>`); }
      else if (shown && none) none.remove();
      const f = root.querySelector("#filters");
      if (f) f.querySelectorAll("[data-g]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.g === state.group)));
      if (f) f.querySelector("[data-attn]").setAttribute("aria-pressed", String(state.attention));
      root.querySelectorAll("#strip [data-s]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.s === state.status)));
    }

    if (multi) {
      root.querySelector("#strip").innerHTML = ORDER.filter(k => counts[k]).map(k => `<button class="chip ${counts[k].cls}" data-s="${k}" aria-pressed="false">${counts[k].n} · ${esc(counts[k].label)}</button>`).join("");
      root.querySelector("#filters").innerHTML =
        [["all", "All", entries.filter(e => e.st.group !== "fragments").length], ...Object.keys(GROUPS).filter(g => groupCount(g)).map(g => [g, GROUPS[g], groupCount(g)])]
          .map(([g, label, n]) => `<button class="seg" data-g="${g}" aria-pressed="${g === "all"}">${label} <span class="count">${n}</span></button>`).join("")
        + `<button class="seg warnseg" data-attn="1" aria-pressed="false">Needs attention <span class="count">${needs}</span></button>`
        + `<span class="spacer"></span><button class="seg" data-act="open">Open all</button><button class="seg" data-act="close">Close all</button>`;
      root.addEventListener("click", ev => {
        const s = ev.target.closest("[data-s]"), g = ev.target.closest("[data-g]"), a = ev.target.closest("[data-attn]"), act = ev.target.closest("[data-act]");
        if (s) state.status = state.status === s.dataset.s ? null : s.dataset.s;
        else if (g) { state.group = g.dataset.g; state.status = null; }
        else if (a) state.attention = !state.attention;
        else if (act) { cardsEl.querySelectorAll(".card:not([hidden])").forEach(c => toggle(c, act.dataset.act === "open")); return; }
        else return;
        applyFilters();
      });
      applyFilters();
    } else if (entries.length === 1) toggle(cardsEl.querySelector(".card"), true);  // a single claim opens straight away
  }

  function explainHtml(e) {
    let h = `<div class="item" dir="rtl"><div class="meta"><span class="chip ${e.ai_written ? "blue" : ""}">${e.ai_written ? "كتب هذا الشرح نموذج ذكاء اصطناعي اعتمادًا على النصوص المعروضة فقط" : "شرح مبسّط مولَّد آليًا من النتيجة"}</span></div>`;
    if (e.summary_ar) h += `<p><b>${esc(e.summary_ar)}</b></p>`;
    h += (e.points || []).map(p => `<p>${esc(p.text)} <span class="small">[${p.cites.join("، ")}]</span></p>`).join("");
    if (e.caution) h += `<p class="small">${esc(e.caution)}</p>`;
    h += (e.texts || []).map(t => `<div class="small">[${t.n}] ${esc(t.label)}${t.stance_ar ? " — " + esc(t.stance_ar) : ""}${t.strength_ar ? " — " + esc(t.strength_ar) : ""}</div>`).join("");
    if (!e.ai_written && e.note) h += `<div class="small" dir="ltr">(${esc(e.note)})</div>`;
    return h + "</div>";
  }

  return { render, esc, statusOf };
})();
