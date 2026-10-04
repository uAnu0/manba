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
  const ORDER = ["q_verified", "supported", "supported_in_part", "supported_weakly", "mixed", "fiqh_disputed", "fiqh_differs", "contradicted", "no_clear_evidence", "q_variant", "q_partial", "q_baseless",
    "similar", "refer_to_scholar", "evidence_only", "out_of_scope", "q_fragment", "quote_checked"];
  const FRAGMENT_WORDS = 5;  // a verified run this short is a stock phrase, not a quotation: kept apart so it does not inflate "verified"

  // Content levels of the challenge's scientific pack (set by the server on every result).
  const LEVELS = {
    "أ": ["مستوى أ", "ok", "Level A · settled text (Quran, authentic hadith): answer directly with the source"],
    "ب": ["مستوى ب", "blue", "Level B · explanation from approved material, with the reference shown"],
    "ج": ["مستوى ج", "warn", "Level C · disputed or sensitive: state the disagreement or refer"],
    "د": ["مستوى د", "bad", "Level D · personal case or fatwa: general information and referral only"] };
  const levelChip = lv => { const m = LEVELS[lv]; return m ? `<span class="chip ${m[1]} level" title="${esc(m[2])}">${m[0]}</span>` : ""; };

  // ---------- fiqh: what the Kuwaiti Fiqh Encyclopedia reports ----------
  const FIQH = {
    consensus_claim_disputed: ["ادّعاء إجماع في مسألة خلافية", "bad"], stated_as_certain_disputed: ["مسألة خلافية بصيغة القطع", "warn"],
    disagreement_acknowledged: ["الخلاف مذكور", "ok"], agreement_reported: ["تنقل الموسوعة الاتفاق", "ok"],
    agreement_differs: ["يخالف ما نُقل الاتفاق عليه", "bad"], partly_disputed: ["اتفاق في جانب وخلاف في جانب", "warn"],
    found_no_marker: ["وُجدت المسألة دون تصريح باتفاق أو خلاف", ""], not_found: ["لم توجد في الموسوعة الفقهية", ""] };
  // A ruling the encyclopedia reports as disputed is not "supported" because some text can be cited for one view: the card says so.
  // (The text-evidence outcome itself is unchanged; only what the badge and the headline claim.)
  const POSITIVE = ["supported", "supported_weakly", "supported_in_part"];
  const DISPUTED = ["consensus_claim_disputed", "stated_as_certain_disputed", "partly_disputed"];
  const fiqhFlag = r => {
    const s = r && r.fiqh && r.fiqh.status;
    if (!r || !POSITIVE.includes(r.outcome)) return null;
    if (DISPUTED.includes(s)) return "disputed";
    return s === "agreement_differs" ? "differs" : null;
  };
  function fiqhHead(r, flag) {
    const disputed = flag === "disputed";
    const en = disputed
      ? "Scholars differ on this ruling. The texts in the Evidence tab are cited for one view only; the Kuwaiti Fiqh Encyclopedia reports disagreement among the schools. Read the Fiqh tab first."
      : "The Kuwaiti Fiqh Encyclopedia reports an agreed ruling that differs from this sentence. Read the Fiqh tab first.";
    const ar = disputed
      ? "العلماء مختلفون في هذه المسألة. النصوص في تبويب Evidence تُذكر لأحد الأقوال فقط، والموسوعة الفقهية الكويتية تنقل الخلاف بين المذاهب. اقرأ تبويب الفقه أولًا."
      : "تنقل الموسوعة الفقهية الكويتية اتفاقًا على حكم يخالف ما في هذه الجملة. اقرأ تبويب الفقه أولًا.";
    return `<div class="outcome ${disputed ? "fiqh_disputed" : "fiqh_differs"}"><h3>${disputed ? "Disputed ruling · مسألة خلافية" : "Differs from the agreed ruling · يخالف المتفق عليه"}</h3><p>${en}</p><p dir="rtl">${ar}</p>`
      + `<p class="small">What the text search found for this wording: ${esc(TITLES[r.outcome] || r.outcome)}. That describes the texts, not the ruling.</p></div>`;
  }
  const AGREE = { agreement: ["اتفاق", "ok"], disagreement: ["خلاف", "warn"], both: ["اتفاق وخلاف", "warn"], none: ["", ""] };
  const fiqhChip = f => { const m = f && FIQH[f.status]; return m ? `<span class="chip ${m[1]}">فقه · ${m[0]}</span>` : ""; };
  function fiqhHtml(f) {
    const m = FIQH[f.status] || [f.status, ""];
    const said = { consensus: "النص يدّعي الإجماع أو الاتفاق", definite: "النص يذكر الحكم بصيغة القطع", hedged: "النص يذكر الخلاف أو ينسب القول" }[f.assertion] || "";
    let h = `<div class="outcome fiqh ${esc(f.status)}" dir="rtl"><h3><span class="chip ${m[1]}">${esc(m[0])}</span></h3><p>${esc(f.summary_ar)}</p><p class="small" dir="ltr">${esc(f.summary_en)}</p>`
      + (said ? `<p class="small">${esc(said)}${(f.assertion_words || []).length ? `: «${f.assertion_words.map(esc).join("، ")}»` : ""}</p>` : "") + `</div>`;
    h += (f.passages || []).map(p => {
      const a = AGREE[p.agreement] || ["", ""];
      const ruling = p.ruling_sentence ? `<div class="ruling" dir="rtl"><span class="small">موضع الحكم في النص:</span> ${esc(p.ruling_sentence)}</div>` : "";
      const pos = (p.positions || []).length ? `<div class="positions" dir="rtl"><div class="small">أقوال المذاهب كما في الموسوعة:</div>${p.positions.map(x => `<div class="pos"><span class="chip">${x.schools.map(esc).join(" · ")}</span> ${esc(x.text)}</div>`).join("")}</div>` : "";
      const head = [p.entry, p.heading].filter(Boolean).map(esc).join(" · ");
      return `<div class="item fiqh-passage" dir="rtl"><div class="meta"><span class="src">${head}</span>${a[0] ? `<span class="chip ${a[1]}">${a[0]}</span>` : ""}${p.same_issue === null ? `<span class="chip">مطابقة بالكلمات</span>` : ""}</div>`
        + ruling + pos + `<details><summary>نص الفقرة كاملًا</summary><div class="ar">${esc(p.text)}</div></details><div class="small cite">${esc(p.cite)}</div></div>`;
    }).join("");
    if (f.error) h += `<div class="small" dir="ltr">AI step unavailable, keyword match used: ${esc(f.error)}</div>`;
    return h + `<div class="notice" dir="rtl">${esc(f.notice_ar)}<span dir="ltr" style="display:block;margin-top:4px">${esc(f.notice_en)}</span></div>`;
  }

  // ---------- Dorar: gradings as Dorar gives them, fetched from the reader's browser ----------
  // The server asks Dorar's official API (services/dorar.py); if that fails the page tries JSONP, then offers the search on dorar.net.
  const DORAR_CATS = [["fabricated", ["موضوع", "باطل", "لا أصل له", "لا اصل له", "ليس له أصل", "ليس له اصل", "مكذوب", "كذب", "ليس بحديث", "لا يعرف مرفوعا"]],
    ["daif", ["لم يصح", "جرحه", "ليس بصحيح", "غير صحيح", "ليس بثابت", "لم يثبت", "لا يثبت مرفوعا", "ضعيف", "ضعفه", "لا يعرف", "لين", "منكر", "لا يصح", "لا يثبت", "شاذ", "معلول", "مرسل", "منقطع", "واه", "فيه ضعف", "متروك", "مجهول"]],
    ["hasan", ["حسن"]], ["sahih", ["صحيح", "ثابت", "متفق عليه", "على شرط", "إسناده جيد", "اسناده جيد", "رجاله ثقات"]]];
  const CAT_AR = { sahih: ["صحيح أو ثابت", "ok"], hasan: ["حسن", "blue"], daif: ["ضعيف أو فيه علة", "warn"], fabricated: ["موضوع أو لا أصل له", "bad"], other: ["حكم آخر", ""] };
  const undiac = t => String(t || "").replace(/[\u064B-\u065F\u0670\u0640]/g, "");
  const dorarCategory = g => { const t = undiac(g); for (const [c, ws] of DORAR_CATS) if (ws.some(w => t.includes(w))) return c; return "other"; };
  const DORAR_DROP = new Set(["و", "ف", "قال", "وقال", "فقال", "يقول", "ويقول", "رسول", "الله", "النبي", "صلى", "عليه", "وسلم", "رواه", "حديث", "في", "الحديث"]);
  const dorarQuery = t => {  // the quoted words only: no attribution, punctuation or stray clitics
    const words = undiac(t).replace(/ﷺ|صلى الله عليه وسلم|قال رسول الله|قال النبي/g, " ").replace(/[^\u0621-\u064A\s]/g, " ").split(/\s+/).filter(Boolean);
    let k = 0; while (k < words.length && DORAR_DROP.has(words[k])) k++;  // leading "وقال" etc.
    return words.slice(k).slice(0, 10).join(" ");
  };
  function dorarParse(htmlText) {
    const doc = new DOMParser().parseFromString(htmlText, "text/html");
    return [...doc.querySelectorAll(".hadith-info")].map(info => {
      const body = info.previousElementSibling, flat = info.textContent.replace(/\s+/g, " ");
      const field = label => { const m = flat.match(new RegExp(label + "\\s*:\\s*(.*?)(?=(الراوي|المحدث|المصدر|الصفحة أو الرقم|خلاصة حكم المحدث)\\s*:|$)")); return m ? m[1].trim() : ""; };
      const grade = field("خلاصة حكم المحدث");
      return { text: (body ? body.textContent : "").replace(/^\s*\d+\s*-\s*/, "").trim(), narrator: field("الراوي"), scholar: field("المحدث"), source: field("المصدر"), page: field("الصفحة أو الرقم"), grade, category: dorarCategory(grade) };
    });
  }
  let dorarSeq = 0;
  function dorarJsonp(q) {
    return new Promise((resolve, reject) => {
      const cb = "manbaDorar" + (++dorarSeq), s = document.createElement("script");
      const done = () => { clearTimeout(timer); delete window[cb]; s.remove(); };
      const timer = setTimeout(() => { done(); reject(new Error("Dorar did not answer")); }, 9000);
      window[cb] = d => { done(); resolve(d); };
      s.onerror = () => { done(); reject(new Error("Dorar could not be reached from this browser")); };
      s.src = "https://dorar.net/dorar_api.json?skey=" + encodeURIComponent(q) + "&callback=" + cb;
      document.head.appendChild(s);
    });
  }
  async function dorarLookup(q, headers) {
    // The server calls Dorar's official API with a Chrome-like connection, which Dorar's Cloudflare accepts; the in-page
    // JSONP request is refused by Cloudflare today but is kept as a second try in case that changes.
    let serverError = "";
    try {
      const res = await fetch("/api/dorar?q=" + encodeURIComponent(q), { headers });
      const d = await res.json();
      if (res.ok && d.available) return { items: d.items, via: "server" };
      serverError = (d && d.error) || ("HTTP " + res.status);
    } catch (e) { serverError = e.message; }
    try {
      const d = await dorarJsonp(q);
      return { items: dorarParse((d && d.ahadith && d.ahadith.result) || ""), via: "browser" };
    } catch (e) { throw new Error(serverError || e.message); }
  }
  function dorarHtml(r, q) {
    if (!r.items.length) return `<div class="small" dir="rtl">لم يُرجع الدرر السنية نتائج لهذا النص («${esc(q)}»).</div>`;
    const counts = {}; r.items.forEach(i => counts[i.category] = (counts[i.category] || 0) + 1);
    const strip = Object.keys(CAT_AR).filter(c => counts[c]).map(c => `<span class="chip ${CAT_AR[c][1]}">${counts[c]} · ${CAT_AR[c][0]}</span>`).join("");
    const mixed = (counts.sahih || counts.hasan) && (counts.daif || counts.fabricated);
    return `<div dir="rtl"><div class="meta">${strip}</div>${mixed ? `<div class="banner">أحكام العلماء على هذه الروايات مختلفة؛ تُعرض كما هي دون ترجيح، ويُرجع إلى أهل الاختصاص.</div>` : ""}`
      + r.items.map(i => `<div class="item dorar-item"><div class="meta"><span class="chip ${(CAT_AR[i.category] || ["", ""])[1]}">${esc(i.grade || "—")}</span><span class="src">${esc(i.scholar)}</span><span class="small">${esc(i.source)}${i.page ? " · " + esc(i.page) : ""}${i.narrator ? " · الراوي: " + esc(i.narrator) : ""}</span></div><div class="ar">${esc(i.text)}</div></div>`).join("")
      + `<div class="small">المصدر: الموسوعة الحديثية، الدرر السنية (dorar.net). الأحكام منقولة بألفاظ أصحابها كما يعرضها الموقع. · Gradings as given by Dorar (${r.via === "browser" ? "fetched by your browser" : "fetched by the server"}).</div></div>`;
  }
  const dorarSearchUrl = q => "https://dorar.net/hadith/search?q=" + encodeURIComponent(q);
  const dorarLinkHtml = q => `<div class="dorar-link" dir="rtl"><a class="dorar-open" href="${esc(dorarSearchUrl(q))}" target="_blank" rel="noopener">افتح البحث في الموسوعة الحديثية بالدرر السنية ↗</a>`
    + `<div class="small">يعرض الموقع أحكام المحدثين على كل رواية مع المصدر والصفحة. لم يُعرض هنا مباشرة لأن الدرر السنية تحجب الطلبات الآلية. · Dorar blocks automated requests, so the search opens on dorar.net in a new tab.</div></div>`;
  const dorarBox = text => `<div class="dorar-box" data-q="${esc(dorarQuery(text))}"><button class="dorar-btn" type="button">Gradings from Dorar · أحكام العلماء من الدرر السنية</button><div class="small">Searches Dorar's hadith encyclopedia for: «${esc(dorarQuery(text))}»</div><div class="dorar-out"></div></div>`;

  // ---------- small pieces of markup ----------
  const strengthChip = s => { if (window.ManbaGrades && s.strength && s.strength !== "quran") return ""; const m = STRENGTH[s.strength]; return m ? `<span class="chip ${m[1]}">Level ${s.level} · ${m[0]}</span>` : ""; };
  const G_CLS = { ok: "ok", fix: "warn", bad: "bad", neu: "" };
  // Arabic grading chips (grades.js): "في الصحيحين" for Bukhari/Muslim, the grader named for the Sunan, and a plain
  // "no grading in our data" with a Dorar link for Ahmad, al-Darimi and anything else ungraded.
  const gradeChips = (s, text) => window.ManbaGrades && s.book !== QURAN ? ManbaGrades.chips(s, k => G_CLS[k], { text })
    : (s.grades || []).map(g => `<span class="chip">${esc(g.grade)} · ${esc(g.name)}</span>`).join("");
  const whereOf = (s, cls) => [s.book, s.chapter && cls === "quran" ? s.chapter : "", s.number].filter(Boolean).join(" · ");

  // A Quran verse shown in a card gets a Tafsir button; the commentary is fetched only when it is clicked (it is not part of the result).
  const QURAN = "القرآن الكريم";
  const quranRef = s => (s && s.book === QURAN && /^\d{1,3}:\d{1,3}(-\d{1,3})?$/.test(s.number || "")) ? s.number : null;
  const tafsirBox = s => { const ref = quranRef(s); return ref ? `<div class="tafsir-box"><button class="tafsir-btn" data-ref="${esc(ref)}">Tafsir · تفسير</button><div class="tafsir-out"></div></div>` : ""; };
  function tafsirHtml(d) {
    const blocks = d.verses.filter(v => v.entries.length).map(v => `<div class="tafsir-verse"><div class="small" dir="ltr">Tafsir of ${esc(v.ref)}</div>` + v.entries.map((e, i) => {
      const long = e.text.length > 900;
      const range = e.covers_from ? `<div class="small" dir="rtl">هذا التفسير يشمل الآيات ${esc(e.covers_from)} إلى ${esc(e.covers_to)}</div>` : "";
      return `<details class="tafsir" ${i === 0 ? "open" : ""}><summary><b>${esc(e.name_ar)}</b> <span class="small">${esc(e.author_ar)}</span></summary>${range}<div class="tafsir-text ${long ? "clamp" : ""}" dir="rtl">${e.text.split("\n").map(p => `<p>${esc(p)}</p>`).join("")}</div>${long ? `<button class="more-btn" type="button">Show more · المزيد</button>` : ""}</details>`;
    }).join("") + "</div>");
    if (!blocks.length) return `<div class="small">No tafsir is available for this verse in our sources.</div>`;
    return blocks.join("") + `<div class="small" style="margin-top:6px">Shown as written by each author; it is not part of the evidence and does not affect the result. · نصّ المفسّر كما كتبه، وهو ليس من الأدلة ولا يؤثّر في النتيجة.</div>`;
  }

  function evidenceItem(it, cls) {
    const s = it.source;
    const covers = (it.covers || []).length ? `<div class="small">Supports this part of the claim: <b>${it.covers.map(esc).join(" · ")}</b></div>` : "";
    const says = it.says ? `<div class="small">The judge's note: ${esc(it.says)}</div>` : "";
    const full = it.full_text && it.full_text !== s.matched_text
      ? `<details><summary>Full text${it.classification === "hadith" ? " with chain of narrators" : ""}</summary><div class="ar">${esc(it.full_text)}</div></details>` : "";
    const ctx = window.ManbaGrades ? ManbaGrades.context(it) : "";
    return `<div class="item ${cls}"><div class="meta"><span class="src">${esc(whereOf(s, it.classification))}</span>${strengthChip(s)}${gradeChips(s, s.matched_text)}</div><div class="ar">${esc(s.matched_text)}</div>${ctx}${covers}${says}${full}${tafsirBox(s)}</div>`;
  }
  const list = (title, items, cls) => items.length ? `<h4>${title} (${items.length})</h4>` + items.map(i => evidenceItem(i, cls)).join("") : "";
  // Texts nobody judged for or against the claim: closed by default and labelled, so a bare verse is not read as evidence.
  const sideList = (title, items) => items.length ? `<details class="unjudged"><summary><b>${title} (${items.length})</b></summary>`
    + `<div class="small" dir="rtl">لم يُحكم بأن هذه النصوص تؤيد العبارة أو تخالفها. تُعرض للاطلاع فقط؛ اقرأ كل آية مع سياقها. · Not judged for or against: read each verse in its context.</div>`
    + items.map(i => evidenceItem(i, "related")).join("") + `</details>` : "";

  function segmentHtml(sg) {
    const st = { verified: ["Verified", "ok"], semantic_variant: ["Wording differs", "warn"], baseless: ["Not found in the sources", "bad"] }[sg.status] || [sg.status, ""];
    const s = sg.source;
    const partial = sg.match_type === "partial" && sg.status === "verified" && s && s.matched_text
      ? `<div class="small">This is only part of the verse. <details style="display:inline"><summary style="display:inline">Show the whole verse</summary><div class="ar">${esc(s.matched_text)}</div></details></div>` : "";
    const diffs = (sg.differences || []).length ? `<ul class="small" dir="rtl">${sg.differences.map(d => `<li>${esc(d)}</li>`).join("")}</ul>` : "";
    return `<div class="item"><div class="meta"><span class="chip ${st[1]}">${st[0]}</span>${sg.match_type === "partial" && sg.status === "verified" ? `<span class="chip warn">Part of the verse</span>` : ""}${s ? strengthChip(s) : ""}${s ? `<span class="src">${esc([s.book, s.number].filter(Boolean).join(" · "))}</span>` : ""}${s ? gradeChips(s, sg.segment_text) : ""}</div><div class="ar">${esc(sg.segment_text)}</div>${partial}${diffs}${s ? tafsirBox(s) : ""}</div>`;
  }

  function similarHtml(sm) {
    const e = sm.evidence, s = e.source;
    const miss = (sm.missing_words || []).length ? `<div class="small" dir="rtl">كلمات في الجملة ليست في هذا النص: <b>${sm.missing_words.map(esc).join("، ")}</b></div>` : "";
    return `<div class="item related"><div class="meta"><span class="chip warn">Close to a known text, not the same wording</span><span class="src">${esc(whereOf(s, e.classification))}</span>${strengthChip(s)}${gradeChips(s, s.matched_text)}</div>`
      + `<div class="small">The sentence shares ${Math.round(sm.shared_share * 100)}% of its distinctive words with this text. Read both: this is a pointer, not a verification.</div>`
      + `<div class="ar">${esc(e.full_text.length > 600 ? s.matched_text : e.full_text)}</div>${miss}${tafsirBox(s)}</div>`;
  }

  // ---------- entries: one per card ----------
  function entriesOf(data) {
    if (data.items) return data.items.map(it => ({ kind: it.kind, text: it.text, start: it.start, result: it.result, quote: it.quote, similar: it.similar, fragment: it.fragment, level: it.content_level }));
    return [{ kind: "claim", text: data.claim, start: 0, result: data, level: data.content_level }];
  }

  const quoteStatus = (status, text, fragment) => {
    if (status === "verified") {
      // the server flags unmarked short runs (fragment); older responses fall back to counting the words
      if (fragment === undefined ? (text || "").trim().split(/\s+/).length <= FRAGMENT_WORDS : fragment) return { key: "q_fragment", label: "Matched phrase", cls: "", attention: false, group: "fragments" };
      return { key: "q_verified", label: "Verified quote", cls: "ok", attention: false, group: "quotes" };
    }
    if (status === "semantic_variant") return { key: "q_variant", label: "Wording differs", cls: "warn", attention: true, group: "quotes" };
    return { key: "q_baseless", label: "Not found", cls: "bad", attention: true, group: "quotes" };
  };

  function statusOf(e) {
    if (e.kind === "similar") return { key: "similar", label: "Close to a known text", cls: "warn", attention: true, group: "similar" };
    if (e.kind === "quote") return quoteStatus(e.quote.status, e.text, e.fragment);
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
    const flag = fiqhFlag(r);
    if (flag === "disputed") return { key: "fiqh_disputed", label: "Disputed ruling · خلافية", cls: "warn", attention: true, group: "claims" };
    if (flag === "differs") return { key: "fiqh_differs", label: "Differs from the agreed ruling", cls: "bad", attention: true, group: "claims" };
    return { key: r.outcome, label: SHORT[r.outcome] || r.outcome, cls: CHIP[r.outcome] || "", attention: !["supported", "out_of_scope"].includes(r.outcome) || !!(r.fiqh && r.fiqh.attention), group: "claims" };
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
    const hadithLike = sg => sg && (sg.classification === "hadith" || (sg.status !== "verified" && /قال رسول الله|قال النبي|ﷺ|صلى الله عليه وسلم|حديث|رواه/.test(e.text || "")));
    if (e.kind === "claim" && r.fiqh) tabs.push({ id: "fiqh", label: "Fiqh · الفقه", n: (r.fiqh.passages || []).length, html: () => fiqhHtml(r.fiqh) });
    if (e.kind === "claim") {
      const ev = [...(r.supporting || []), ...(r.contradicting || [])];
      if (ev.length) tabs.push({ id: "evidence", label: "Evidence", n: ev.length, html: () => list("Evidence that supports the claim", r.supporting || [], "supports") + list("Evidence that contradicts the claim", r.contradicting || [], "contradicts") });
      const side = [...(r.partial || []), ...(r.related || [])];
      if (side.length) tabs.push({ id: "related", label: r.outcome === "evidence_only" ? "Related texts" : "Partial & related", n: side.length, html: () => list("Texts that support only part of the claim", r.partial || [], "supports") + sideList(r.outcome === "quote_checked" ? "Texts with similar words, not this quote · نصوص بألفاظ قريبة" : r.outcome === "evidence_only" ? "Related texts · نصوص ذات صلة" : "Related, but not deciding · ذات صلة غير حاسمة", r.related || []) });
      if (r.quote_check) tabs.push({ id: "quote", label: "Quote check", html: () => r.quote_check.segments.map(segmentHtml).join("") });
      const hs = r.quote_check && r.quote_check.segments.find(hadithLike);
      if (hs) tabs.push({ id: "dorar", label: "Dorar · الدرر", html: () => dorarBox(hs.segment_text) });
      if (r.similar) tabs.push({ id: "similar", label: "Close text", html: () => similarHtml(r.similar) });
    } else if (e.kind === "quote") {
      tabs.push({ id: "quote", label: "Quote check", html: () => segmentHtml(e.quote) });
      if (hadithLike(e.quote)) tabs.push({ id: "dorar", label: "Dorar · الدرر", html: () => dorarBox(e.quote.segment_text) });
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
      const flag = fiqhFlag(r);
      head += flag ? fiqhHead(r, flag)
        : `<div class="outcome ${esc(r.outcome)}"><h3>${esc(TITLES[r.outcome] || r.outcome)}</h3><p>${esc(r.summary_en)}</p><p dir="rtl">${esc(r.summary_ar)}</p></div>`;
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
      if (!data.llm || !data.llm.used) intro += `<div class="banner">No model was used, so only quoted texts and sentences worded as fiqh rulings were checked.</div>`;
      const lv = ["أ", "ب", "ج", "د"].filter(l => data.summary && data.summary["level_" + l]);
      if (lv.length) intro += `<div class="meta levels-strip" dir="rtl"><span class="small">مستويات المحتوى:</span>${lv.map(l => `${levelChip(l)}<span class="small">${data.summary["level_" + l]}</span>`).join(" ")}</div>`;
    }
    const multi = entries.length > 1;
    const root = document.createElement("div");  // listeners live on a fresh element, so re-rendering never stacks them
    container.replaceChildren(root);
    root.innerHTML = intro + (multi ? `<div class="strip" id="strip"></div><div class="filters" id="filters"></div>` : "") + `<div class="cards" id="cards"></div>`;
    const cardsEl = root.querySelector("#cards");

    cardsEl.innerHTML = entries.map(e => `
      <article class="card" data-i="${e.i}" data-group="${e.st.group}" data-status="${e.st.key}" data-needs="${e.st.attention ? 1 : 0}">
        <button class="card-head" aria-expanded="false" data-i="${e.i}">
          <span class="badge"><span class="chip ${e.st.cls}">${esc(e.st.label)}</span>${levelChip(e.level)}${e.kind === "claim" ? fiqhChip(e.result.fiqh) : ""}</span>
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
      const more = ev.target.closest(".more-btn");
      if (more) { const t = more.parentElement.querySelector(".tafsir-text"); const open = t.classList.toggle("clamp") === false; more.textContent = open ? "Show less · أقل" : "Show more · المزيد"; return; }
      const tb = ev.target.closest(".tafsir-btn");
      if (tb) {
        const out = tb.parentElement.querySelector(".tafsir-out");
        if (out.innerHTML) { out.hidden = !out.hidden; return; }  // already loaded: the button shows or hides it
        tb.disabled = true; out.innerHTML = `<div class="small">Loading…</div>`;
        try {
          const res = await fetch("/api/tafsir/" + encodeURIComponent(tb.dataset.ref), { headers: opts.headers ? opts.headers() : {} });
          const d = await res.json();
          if (!res.ok) throw new Error(res.status === 401 ? "The server needs an access code: enter it in Settings." : JSON.stringify(d));
          out.innerHTML = tafsirHtml(d);
        } catch (e) { out.innerHTML = `<div class="err">${esc(e.message)}</div>`; }
        tb.disabled = false; return;
      }
      const db = ev.target.closest(".dorar-btn");
      if (db) {
        const box = db.parentElement, out = box.querySelector(".dorar-out");
        db.disabled = true; out.innerHTML = `<div class="small">Asking Dorar…</div>`;
        try { out.innerHTML = dorarHtml(await dorarLookup(box.dataset.q, opts.headers ? opts.headers() : {}), box.dataset.q); db.remove(); }
        catch (e) {  // Dorar's Cloudflare refuses requests that are not a normal page visit: open the same search on dorar.net instead
          out.innerHTML = dorarLinkHtml(box.dataset.q); db.remove();
        }
        return;
      }
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
    let h = `<div class="item" dir="rtl"><div class="meta"><span class="chip ${e.ai_written ? "blue" : ""}">${e.ai_written ? "شرح مولَّد بالذكاء الاصطناعي من النصوص المعروضة فقط، وليس من نصوص المصادر" : "شرح مبسّط مولَّد آليًا من النتيجة"}</span></div>`;
    if (e.summary_ar) h += `<p><b>${esc(e.summary_ar)}</b></p>`;
    h += (e.points || []).map(p => `<p>${esc(p.text)} <span class="small">[${p.cites.join("، ")}]</span></p>`).join("");
    if (e.caution) h += `<p class="small">${esc(e.caution)}</p>`;
    h += (e.texts || []).map(t => `<div class="small">[${t.n}] ${esc(t.label)}${t.stance_ar ? " — " + esc(t.stance_ar) : ""}${t.strength_ar ? " — " + esc(t.strength_ar) : ""}</div>`).join("");
    if (!e.ai_written && e.note) h += `<div class="small" dir="ltr">(${esc(e.note)})</div>`;
    return h + "</div>";
  }

  return { render, esc, statusOf, fiqhFlag };
})();
