/* Manba reviewer page: input -> /api/check -> a report ordered by what must change before publishing.
   Every verdict shown here is read from the API result (sources, gradings, fiqh agreement), never invented in the page. */
(() => {
  const $ = id => document.getElementById(id);
  const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const AR_DIGITS = n => String(n).replace(/\d/g, d => "٠١٢٣٤٥٦٧٨٩"[d]);
  const MAX_WORDS = 500;

  const SURAH = ["الفاتحة","البقرة","آل عمران","النساء","المائدة","الأنعام","الأعراف","الأنفال","التوبة","يونس","هود","يوسف","الرعد","إبراهيم","الحجر","النحل","الإسراء","الكهف","مريم","طه","الأنبياء","الحج","المؤمنون","النور","الفرقان","الشعراء","النمل","القصص","العنكبوت","الروم","لقمان","السجدة","الأحزاب","سبأ","فاطر","يس","الصافات","ص","الزمر","غافر","فصلت","الشورى","الزخرف","الدخان","الجاثية","الأحقاف","محمد","الفتح","الحجرات","ق","الذاريات","الطور","النجم","القمر","الرحمن","الواقعة","الحديد","المجادلة","الحشر","الممتحنة","الصف","الجمعة","المنافقون","التغابن","الطلاق","التحريم","الملك","القلم","الحاقة","المعارج","نوح","الجن","المزمل","المدثر","القيامة","الإنسان","المرسلات","النبأ","النازعات","عبس","التكوير","الانفطار","المطففين","الانشقاق","البروج","الطارق","الأعلى","الغاشية","الفجر","البلد","الشمس","الليل","الضحى","الشرح","التين","العلق","القدر","البينة","الزلزلة","العاديات","القارعة","التكاثر","العصر","الهمزة","الفيل","قريش","الماعون","الكوثر","الكافرون","النصر","المسد","الإخلاص","الفلق","الناس"];
  const QURAN = "القرآن الكريم";

  const SAMPLES = [
    ["خطبة فيها أخطاء شائعة", "الحمد لله، أما بعد: أيها الإخوة، إن طلب العلم من أعظم القربات، وقد قال رسول الله ﷺ: «اطلبوا العلم ولو في الصين». ومن ثمرات العلم معرفة الحلال والحرام؛ قال تعالى: «وأحل الله البيع وحرم الزنا». ومن العلم الواجب على المرأة أن تعلم أن زكاة الحلي المستعمل واجبة بالإجماع، وأن التسمية عند الوضوء واجبة. فاصبروا على طلبه، فإن الله يقول: ﴿فإن مع العسر يسرا﴾."],
    ["منشور متداول", "انشرها تؤجر! قال رسول الله ﷺ: «النظافة من الإيمان». وقال ﷺ: «اختلاف أمتي رحمة». وقال ﷺ: «الراحمون يرحمهم الرحمن، ارحموا من في الأرض يرحمكم من في السماء»."],
    ["ادّعاء إجماع في مسألة فقهية", "أجمع العلماء على أن قراءة الفاتحة خلف الإمام واجبة. وأكل لحم الإبل ينقض الوضوء. وتارك الصلاة كسلًا كافر بالإجماع."],
    ["آية منقولة بخطأ", "قال تعالى: «وأحل الله البيع وحرم الزنا». وقال سبحانه: ﴿إن مع العسر يسرا﴾."],
  ];

  // ---------- verdicts: one plain-language class per result ----------
  // k: bad (must change) | fix (needs correcting) | khl (disputed, attribute it) | ref (refer) | neu (no conclusion) | ok (verified)
  const RANK = { bad: 0, fix: 1, khl: 2, ref: 3, neu: 4, ok: 5 };
  const K_LABEL = { bad: "لا يثبت", fix: "يحتاج تصحيحًا", khl: "مسألة خلافية", ref: "يُحال إلى مختص", neu: "بلا حكم", ok: "موثّق" };
  const LEVEL_TITLE = { "أ": "مستوى أ: نص أصلي مستقر", "ب": "مستوى ب: شرح مع إظهار المرجع", "ج": "مستوى ج: خلافي أو حساس", "د": "مستوى د: حالة شخصية تُحال" };

  const surahRef = s => {
    const m = /^(\d+):(\d+)(?:-(\d+))?$/.exec((s && s.number) || "");
    return m ? `سورة ${SURAH[+m[1] - 1] || m[1]}، الآية ${AR_DIGITS(m[2])}${m[3] ? "–" + AR_DIGITS(m[3]) : ""}` : (s ? [s.book, s.number].filter(Boolean).join(" ") : "");
  };
  const isQuran = s => s && s.book === QURAN;
  const where = s => !s ? "" : isQuran(s) ? surahRef(s) : [s.book, s.number].filter(Boolean).join(" · ");
  const HADITH_CUE = /قال رسول الله|قال النبي|ﷺ|صلى الله عليه وسلم|رواه|حديث/;

  function segVerdict(sg, text) {
    const s = sg.source, quran = sg.classification === "quran" || isQuran(s);
    if (sg.status === "verified" && s) {
      if (quran) return { k: "ok", label: "آية موثّقة", type: "آية", why: surahRef(s) };
      const st = s.strength;
      if (st === "sahihayn" || st === "sahih") return { k: "ok", label: "حديث صحيح", type: "حديث", why: where(s) };
      if (st === "hasan") return { k: "ok", label: "حديث حسن", type: "حديث", why: where(s) };
      if (st === "daif") return { k: "bad", label: "حديث ضعيف", type: "حديث", why: `${where(s)} · حكم عليه العلماء بالضعف`, next: "لا يُستدل به، أو يُذكر مع بيان ضعفه", dorar: true };
      if (st === "disputed") return { k: "khl", label: "أحكام المحدثين مختلفة", type: "حديث", why: `${where(s)} · بعض العلماء صححه وبعضهم ضعفه`, next: "اطّلع على أحكام المحدثين قبل الاستدلال به", dorar: true };
      return { k: "fix", label: "درجته غير مبيّنة عندنا", type: "حديث", why: where(s), next: "تحقق من درجته في أحكام المحدثين", dorar: true };
    }
    if (sg.status === "semantic_variant" && s) {
      return { k: "fix", label: quran ? "آية بلفظ محرّف" : "حديث بلفظ مختلف", type: quran ? "آية" : "حديث",
        why: quran ? `يختلف عن نص المصحف في ${surahRef(s)}` : `يختلف عن لفظه في ${where(s)}`,
        next: "استبدل بالنص الصحيح", copy: s.matched_text, dorar: !quran };
    }
    const hadithy = HADITH_CUE.test(text || "") || sg.classification === "hadith";
    return { k: "bad", label: hadithy ? "لم يوجد في كتب الحديث" : "لم يوجد في المصادر", type: hadithy ? "حديث" : "اقتباس",
      why: hadithy ? "لم نجده في الكتب التسعة. انظر أحكام المحدثين عليه في الدرر السنية." : "لم نجده في المصحف ولا في الكتب التسعة.",
      next: hadithy ? "لا يُنسب إلى النبي ﷺ حتى يثبت: احذفه أو تحقق منه" : "تحقق من مصدره قبل نشره", dorar: hadithy };
  }

  const FIQH_V = {
    consensus_claim_disputed: { k: "bad", label: "إجماع مدّعى غير ثابت", next: "احذف ادعاء الإجماع، واذكر الخلاف أو انسب القول إلى قائله" },
    stated_as_certain_disputed: { k: "khl", label: "مسألة خلافية بصيغة القطع", next: "انسب القول إلى قائله أو اذكر الخلاف" },
    partly_disputed: { k: "khl", label: "اتفاق في جانب وخلاف في جانب", next: "راجع موضع الحكم في نص الموسوعة وصِغه بدقة" },
    agreement_differs: { k: "bad", label: "يخالف ما نُقل الاتفاق عليه", next: "راجع الحكم في ضوء نص الموسوعة" },
    disagreement_acknowledged: { k: "ok", label: "الخلاف مذكور", next: null },
    agreement_reported: { k: "ok", label: "موافق لما نُقل الاتفاق عليه", next: null },
    found_no_marker: { k: "neu", label: "وُجدت المسألة دون تصريح باتفاق أو خلاف", next: "راجع نص الموسوعة" },
    not_found: { k: "neu", label: "لم توجد في الموسوعة الفقهية", next: "يُرجع فيها إلى مختص" },
  };
  const OUTCOME_V = {
    supported: { k: "ok", label: "تؤيده الأدلة" },
    supported_in_part: { k: "fix", label: "مؤيد جزئيًا", next: "قيّد العبارة بما تؤيده النصوص" },
    supported_weakly: { k: "fix", label: "دليله ضعيف", next: "لا تبنِ عليه إلا بدليل ثابت" },
    contradicted: { k: "bad", label: "تخالفه الأدلة", next: "راجع العبارة في ضوء النصوص المعروضة" },
    mixed: { k: "khl", label: "أدلة من الجانبين", next: "يحتاج إلى عالم يوازن بين الأدلة" },
    no_clear_evidence: { k: "neu", label: "لا دليل واضح", next: "لم نجد ما يؤيده أو يخالفه: تحقق منه" },
    refer_to_scholar: { k: "ref", label: "يُحال إلى مختص", next: "مسألة شخصية: يُسأل فيها عالم مؤهل" },
    evidence_only: { k: "neu", label: "نصوص ذات صلة دون حكم" },
  };

  function claimVerdict(r, text) {
    if (r.outcome === "quote_checked" && r.quote_check && r.quote_check.segments.length) {
      const vs = r.quote_check.segments.filter(s => s.is_claim !== false).map(s => ({ v: segVerdict(s, text), s }));
      if (vs.length) { vs.sort((a, b) => RANK[a.v.k] - RANK[b.v.k]); return Object.assign({ seg: vs[0].s }, vs[0].v); }
    }
    if (r.fiqh && FIQH_V[r.fiqh.status]) {
      const f = FIQH_V[r.fiqh.status], p = (r.fiqh.passages || [])[0];
      return { k: f.k, label: f.label, type: "حكم فقهي", why: r.fiqh.summary_ar + (p ? ` (${p.cite})` : ""), next: f.next, fiqh: r.fiqh };
    }
    const o = OUTCOME_V[r.outcome] || { k: "neu", label: r.outcome };
    let why = r.summary_ar || "";
    if (r.outcome === "refer_to_scholar" && r.reason) why = "مسألة تخص حالة بعينها؛ الحكم فيها يحتاج عالمًا يسمع تفاصيلها.";
    return { k: o.k, label: o.label, type: "ادعاء", why, next: o.next };
  }

  function similarVerdict(sm) {
    const e = sm.evidence, s = e.source;
    return { k: "fix", label: "قريب من نص معروف بلفظ مختلف", type: isQuran(s) ? "آية" : "حديث",
      why: `يشبه ${where(s)} (${Math.round(sm.shared_share * 100)}٪ من كلماته المميزة)، وليس بلفظه.`,
      next: "انقل النص بلفظه من مصدره", copy: s.matched_text, simItem: e };
  }

  function verdictOf(it) {
    if (it.kind === "quote") return Object.assign({ seg: it.quote }, segVerdict(it.quote, it.text));
    if (it.kind === "similar") return similarVerdict(it.similar);
    return claimVerdict(it.result, it.text);
  }

  // ---------- state ----------
  const store = { data: null, entries: [], filter: "attention" };
  const headers = (json) => {
    const h = json ? { "Content-Type": "application/json" } : {};
    const g = k => { try { return localStorage.getItem(k) || ""; } catch (e) { return ""; } };
    if (g("manba_access_token")) h["X-Access-Token"] = g("manba_access_token");
    if (g("manba_openrouter_key")) h["X-OpenRouter-Key"] = g("manba_openrouter_key");
    if (g("manba_llm_provider")) h["X-LLM-Provider"] = g("manba_llm_provider");
    if (g("manba_gemini_key")) h["X-Gemini-Key"] = g("manba_gemini_key");
    return h;
  };

  // ---------- input view ----------
  const words = () => ($("text").value.trim().match(/\S+/g) || []).length;
  function updateCount() {
    const n = words();
    $("wc").textContent = `${AR_DIGITS(n)} كلمة من ${AR_DIGITS(MAX_WORDS)}` + (n > MAX_WORDS ? " · النص أطول من الحد، اختصره أو قسّمه" : "");
    $("wc").style.color = n > MAX_WORDS ? "var(--bad)" : "";
    $("go").disabled = n === 0 || n > MAX_WORDS;
  }
  $("text").addEventListener("input", updateCount);
  $("text").addEventListener("keydown", e => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) run(); });
  for (const [label, text] of SAMPLES) {
    const b = document.createElement("button");
    b.className = "sample"; b.textContent = label; b.type = "button";
    b.onclick = () => { $("text").value = text; showTab("paste"); updateCount(); run(); };
    $("samples").appendChild(b);
  }
  function showTab(which) {
    $("tabPaste").setAttribute("aria-selected", String(which === "paste"));
    $("tabFile").setAttribute("aria-selected", String(which === "file"));
    $("panePaste").hidden = which !== "paste";
    $("paneFile").hidden = which !== "file";
  }
  $("tabPaste").onclick = () => showTab("paste");
  $("tabFile").onclick = () => showTab("file");
  async function readFile(f) {
    if (!f) return;
    if (!/\.(txt|md)$/i.test(f.name) && !(f.type || "").startsWith("text/")) { alertInline("هذا النوع من الملفات غير مدعوم بعد. استخدم ملفًا نصيًا ‎.txt‎ أو الصق النص."); return; }
    $("text").value = (await f.text()).trim(); showTab("paste"); updateCount(); $("text").focus();
  }
  $("file").addEventListener("change", e => readFile(e.target.files[0]));
  $("drop").addEventListener("dragover", e => { e.preventDefault(); $("drop").style.borderColor = "var(--brand)"; });
  $("drop").addEventListener("dragleave", () => { $("drop").style.borderColor = ""; });
  $("drop").addEventListener("drop", e => { e.preventDefault(); $("drop").style.borderColor = ""; readFile(e.dataTransfer.files[0]); });
  function alertInline(msg) {
    let el = document.querySelector("#inputView .err");
    if (!el) { el = document.createElement("div"); el.className = "err"; el.setAttribute("role", "alert"); document.querySelector(".composer").appendChild(el); }
    el.textContent = msg;
  }

  // ---------- loading ----------
  const STEPS = ["استخراج الآيات والأحاديث والأحكام", "المطابقة مع المصحف والكتب التسعة", "تقييم الادعاءات بالأدلة", "المسائل الفقهية في الموسوعة الكويتية"];
  let timer = null;
  function startLoading() {
    $("inputView").hidden = true; $("reportView").hidden = true; $("loadingView").hidden = false;
    let i = 0;
    const paint = () => {
      $("steps").innerHTML = STEPS.map((s, k) => `<div class="step ${k < i ? "done" : k === i ? "now" : ""}"><span class="d">${k < i ? "✓" : AR_DIGITS(k + 1)}</span>${esc(s)}</div>`).join("");
      $("barFill").style.width = Math.min(92, 12 + i * 24) + "%";
    };
    paint();
    timer = setInterval(() => { if (i < STEPS.length - 1) { i++; paint(); } }, 3500);
  }
  function stopLoading() { clearInterval(timer); $("loadingView").hidden = true; }

  // ---------- run ----------
  async function run() {
    const text = $("text").value.trim();
    if (!text || words() > MAX_WORDS) return;
    startLoading();
    try {
      const res = await fetch("/api/check", { method: "POST", headers: headers(true), body: JSON.stringify({ text, use_llm: true, use_meaning: true }) });
      const data = await res.json().catch(() => ({}));
      if (res.status === 401) { stopLoading(); $("inputView").hidden = false; alertInline("الخادم يطلب رمز دخول: أدخله من الإعدادات."); $("settingsDlg").showModal(); return; }
      if (res.status === 422) throw new Error("النص طويل أو غير صالح للفحص. اختصره إلى 500 كلمة أو أقل.");
      if (!res.ok) throw new Error("تعذر الفحص الآن. أعد المحاولة بعد قليل.");
      stopLoading();
      renderReport(data);
      history.pushState({ report: true }, "", "#report");
    } catch (e) {
      stopLoading(); $("inputView").hidden = false; alertInline(e.message || "تعذر الاتصال بالخادم. تحقق من الاتصال وأعد المحاولة.");
    }
  }
  $("go").onclick = run;
  $("newBtn").onclick = () => { $("reportView").hidden = true; $("inputView").hidden = false; $("newBtn").hidden = true; history.pushState({}, "", "#"); $("text").focus(); };
  window.addEventListener("popstate", () => { if (!location.hash.includes("report")) $("newBtn").onclick(); });

  // ---------- report ----------
  function renderReport(data) {
    store.data = data;
    const items = (data.items || []).filter(it => !it.fragment && !(it.kind === "claim" && it.result && it.result.outcome === "out_of_scope"));
    store.entries = items.map((it, i) => ({ it, v: verdictOf(it), i }))
      .sort((a, b) => RANK[a.v.k] - RANK[b.v.k] || a.it.start - b.it.start);
    store.entries.forEach((e, n) => { e.n = n + 1; });
    const counts = {}; store.entries.forEach(e => { counts[e.v.k] = (counts[e.v.k] || 0) + 1; });
    const needs = (counts.bad || 0) + (counts.fix || 0);
    store.filter = store.entries.length > 6 ? "attention" : "all";

    const llmOff = !data.llm || !data.llm.used;
    const head = `<section class="summary" aria-label="ملخص التقرير">
      <div class="row-between">
        <div style="display: flex; flex-direction: column; gap: 2px">
          <h1>تقرير المراجعة</h1>
          <span class="cap">${AR_DIGITS(data.word_count)} كلمة · ${AR_DIGITS(store.entries.length)} من النصوص والأحكام · ${AR_DIGITS(data.commentary_sentences || 0)} جملة تعليق لا تحتاج تحققًا</span>
        </div>
        <div class="actions no-print">
          <button class="btn" id="copySummary">نسخ ملخص التقرير</button>
          <button class="btn" id="printBtn">طباعة أو حفظ PDF</button>
        </div>
      </div>
      ${store.entries.length ? `<div class="seg" aria-hidden="true">${["bad", "fix", "khl", "ref", "neu", "ok"].filter(k => counts[k]).map(k => `<i class="s-${k}" style="flex: ${counts[k]}"></i>`).join("")}</div>
      <div class="counts"><b>${needs ? `${AR_DIGITS(needs)} ${needs === 1 ? "موضع يحتاج" : "مواضع تحتاج"} تعديلًا قبل النشر` : "لا شيء يمنع النشر"}</b>
        ${["bad", "fix", "khl", "ref", "neu", "ok"].filter(k => counts[k]).map(k => `<span class="chip k-${k}">${AR_DIGITS(counts[k])} ${K_LABEL[k]}</span>`).join("")}</div>` : ""}
      ${llmOff ? `<div class="notice" role="status">خدمة الذكاء الاصطناعي غير متاحة الآن، فتحققنا من الاقتباسات والأحكام الفقهية الصريحة بالمطابقة المباشرة فقط. قد لا تظهر الادعاءات غير المقتبسة.</div>` : ""}
      ${data.truncated ? `<div class="notice">النص أطول من الحد، فُحص الجزء الأول منه فقط.</div>` : ""}
    </section>`;

    let body;
    if (!store.entries.length) {
      body = `<section class="empty"><b style="font-size: 20px">لم نجد آيات أو أحاديث أو أحكامًا شرعية نتحقق منها</b>
        <span class="cap" style="max-width: 520px; line-height: 1.8">إن كان في النص حديث أو آية بغير علامات تنصيص فضعه بين «» وأعد الفحص.</span>
        <button class="btn primary" id="editBtn">تعديل النص</button></section>`;
    } else {
      body = `<div class="cols">
        <section class="doc" aria-label="النص كما أُدخل">
          <div class="row-between"><b class="cap" style="font-size: 14px">النص كما أُدخل</b><span class="cap">اضغط موضعًا مظلَّلًا لفتح نتيجته</span></div>
          <p>${markedText(data.original_text)}</p>
        </section>
        <section class="list" aria-label="النتائج">
          <div class="row-between"><b class="cap" style="font-size: 14px">النتائج، الأهم أولًا</b>
            <div class="filters" role="group" aria-label="تصفية النتائج">
              <button class="btn small" data-f="attention" aria-pressed="${store.filter === "attention"}">تحتاج إجراء ${AR_DIGITS(store.entries.filter(e => e.v.k !== "ok").length)}</button>
              <button class="btn small" data-f="all" aria-pressed="${store.filter === "all"}">الكل ${AR_DIGITS(store.entries.length)}</button>
            </div></div>
          <div id="cards" style="display: flex; flex-direction: column; gap: 12px">${store.entries.map(cardHtml).join("")}</div>
        </section>
      </div>`;
    }
    const rv = $("reportView");
    rv.innerHTML = head + body + `<p class="cap" style="line-height: 1.8">هذا التقرير يبيّن مواضع النصوص في المصادر وأحكام العلماء كما نقلتها، وليس فتوى ولا ترجيحًا. ما كتبه الذكاء الاصطناعي معلَّم بذلك.</p>`;
    rv.hidden = false; $("newBtn").hidden = false;
    applyFilter();
    window.scrollTo({ top: 0 });
    const first = rv.querySelector(".card"); if (first && RANK[store.entries[0].v.k] <= 1) openCard(store.entries[0], first);
  }

  function markedText(text) {
    const spans = store.entries.map(e => ({ s: e.it.start, e: e.it.end, en: e })).sort((a, b) => a.s - b.s);
    let out = "", pos = 0;
    for (const sp of spans) {
      if (sp.s < pos) continue;
      out += esc(text.slice(pos, sp.s));
      out += `<button class="mk k-${sp.en.v.k}" data-goto="${sp.en.n}" aria-label="النتيجة ${sp.en.n}: ${esc(sp.en.v.label)}">${esc(text.slice(sp.s, sp.e))}</button><span class="num" aria-hidden="true">${AR_DIGITS(sp.en.n)}</span>`;
      pos = sp.e;
    }
    return out + esc(text.slice(pos));
  }

  function cardHtml(e) {
    const v = e.v, it = e.it, lvl = it.content_level;
    const quoteText = it.kind === "claim" ? it.text : it.text;
    const isScripture = v.type === "آية" || v.type === "حديث" || v.type === "اقتباس";
    return `<article class="card ${v.k === "bad" ? "k-bad-b" : ""}" id="card-${e.n}" data-k="${v.k}">
      <div class="head">
        <div><span class="num" style="vertical-align: baseline">${AR_DIGITS(e.n)}</span><span class="chip k-${v.k}">${esc(v.label)}</span>${lvl ? `<span class="lv" title="${esc(LEVEL_TITLE[lvl] || "")}">مستوى ${esc(lvl)}</span>` : ""}</div>
        <span class="cap">${esc(v.type)}</span>
      </div>
      <div class="${isScripture ? "quote" : ""}" style="${isScripture ? "" : "font-size: 16px; line-height: 1.8"}">${esc(quoteText)}</div>
      ${v.why ? `<p class="why">${esc(v.why)}</p>` : ""}
      ${v.next ? `<div class="next"><b>الخطوة التالية: ${esc(v.next)}</b>${v.copy ? `<div class="q" style="font-size: 19px; line-height: 2">${esc(v.copy)}</div>` : ""}</div>` : ""}
      <div class="actions no-print">
        <button class="btn small" data-open="${e.n}" aria-expanded="false">التفاصيل والمصادر</button>
        ${v.copy ? `<button class="btn small" data-copy="${e.n}">نسخ النص الصحيح</button>` : ""}
      </div>
      <div class="more" id="more-${e.n}" hidden></div>
    </article>`;
  }

  function applyFilter() {
    document.querySelectorAll("#cards .card").forEach(c => { c.hidden = store.filter === "attention" && c.dataset.k === "ok"; });
    document.querySelectorAll(".filters [data-f]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.f === store.filter)));
  }

  // ---------- details ----------
  function sourceBlock(s, label) {
    if (!s) return "";
    const grades = (s.grades || []).map(g => `${esc(g.name)}: ${esc(g.grade)}`).join(" · ");
    return `<div class="src"><span class="cap">${esc(label || where(s))}</span><div class="q">${esc(s.matched_text)}</div>${grades ? `<span class="cap">أحكام العلماء في بياناتنا: ${grades}</span>` : ""}</div>`;
  }
  function diffBlock(sg) {
    const d = (sg.differences || []).filter(x => !/^verbatim/.test(x));
    return d.length ? `<div class="src"><span class="cap">مواضع الاختلاف</span><ul style="margin: 0; padding-inline-start: 18px; line-height: 1.9">${d.map(x => `<li>${esc(x)}</li>`).join("")}</ul></div>` : "";
  }
  function fiqhBlock(f) {
    const ps = f.passages || [];
    if (!ps.length) return `<p class="why">${esc(f.summary_ar)}</p>`;
    return ps.slice(0, 2).map(p => `<div class="src">
      <div class="row-between"><b>${esc([p.entry, p.heading].filter(Boolean).join(" · "))}</b><span class="chip ${p.agreement === "agreement" ? "k-ok" : p.agreement === "none" ? "k-neu" : "k-khl"}">${{ agreement: "تنقل الاتفاق", disagreement: "تنقل الخلاف", both: "اتفاق وخلاف", none: "دون تصريح" }[p.agreement] || ""}</span></div>
      ${p.ruling_sentence ? `<div class="ruling">${esc(p.ruling_sentence)}</div>` : ""}
      ${(p.positions || []).length ? `<div class="schools">${p.positions.slice(0, 4).map(x => `<div><span class="cap">${esc(x.schools.join("، "))}</span><div class="q" style="font-size: 17px">${esc(x.text)}</div></div>`).join("")}</div>` : ""}
      <details><summary class="cap" style="cursor: pointer">نص الفقرة كاملًا</summary><div class="q" style="font-size: 17px; line-height: 2; margin-top: 6px">${esc(p.text)}</div></details>
      <span class="cap">${esc(p.cite)}${p.same_issue === null ? " · مطابقة بالكلمات، تأكد أنها في المسألة نفسها" : ""}</span>
    </div>`).join("") + `<span class="cap">${esc(f.notice_ar)}</span>`;
  }
  function evidenceBlock(r) {
    const sup = (r.supporting || []).slice(0, 3), con = (r.contradicting || []).slice(0, 3);
    const one = (it, lab) => `<div class="src"><span class="cap">${lab} · ${esc(where(it.source))}${it.source.strength && it.source.strength !== "quran" ? "" : ""}</span><div class="q">${esc(it.source.matched_text)}</div></div>`;
    return (sup.length ? `<b style="font-size: 14px">نصوص تؤيده</b>` + sup.map(x => one(x, "يؤيد")).join("") : "")
      + (con.length ? `<b style="font-size: 14px">نصوص تخالفه</b>` + con.map(x => one(x, "يخالف")).join("") : "");
  }
  function detailsHtml(e) {
    const v = e.v, it = e.it;
    let h = "";
    const sg = v.seg;
    if (sg && sg.source) h += sourceBlock(sg.source, sg.status === "verified" ? where(sg.source) : `النص في المصدر: ${where(sg.source)}`) + diffBlock(sg);
    if (v.simItem) h += sourceBlock(v.simItem.source);
    if (v.fiqh) h += fiqhBlock(v.fiqh);
    if (it.kind === "claim" && !v.fiqh && it.result.outcome !== "quote_checked") h += evidenceBlock(it.result);
    if (it.kind === "claim" && v.fiqh && (it.result.supporting || []).length) h += `<details><summary class="cap" style="cursor: pointer">نصوص من القرآن والسنة ذُكرت لأحد الأقوال</summary>${evidenceBlock(it.result)}</details>`;
    const s = (sg && sg.source) || (v.simItem && v.simItem.source);
    if (isQuran(s) && /^\d+:\d+/.test(s.number)) h += `<div class="actions"><button class="btn small" data-tafsir="${esc(s.number)}">التفسير الميسر والسعدي</button></div><div class="tafsir-out"></div>`;
    if (v.dorar) h += `<div class="dorar" data-q="${esc(quoteOf((sg && sg.segment_text) || it.text))}"><span class="cap">جارٍ جلب أحكام المحدثين من الدرر السنية…</span></div>`;
    h += `<div class="explain"><button class="btn small" data-explain="${e.n}">اشرح النتيجة بالعربية</button> <span class="gen">مولَّد بالذكاء الاصطناعي</span><div class="explain-out"></div></div>`;
    return h;
  }
  function openCard(e, card) {
    const more = card.querySelector(".more"), btn = card.querySelector("[data-open]");
    const open = more.hidden;
    if (open && !more.dataset.built) { more.innerHTML = detailsHtml(e); more.dataset.built = "1"; const d = more.querySelector(".dorar"); if (d) loadDorar(d); }
    more.hidden = !open; if (btn) { btn.setAttribute("aria-expanded", String(open)); btn.textContent = open ? "إخفاء التفاصيل" : "التفاصيل والمصادر"; }
  }

  // The words inside «…» or "…" when the sentence quotes them, else the sentence itself.
  function quoteOf(t) { const m = /[«"“]([^»"”]{4,})[»"”]/.exec(t || ""); return (m ? m[1] : t || "").trim(); }
  const normAr = t => (t || "").replace(/[\u064B-\u065F\u0670\u0640]/g, "").replace(/[إأآٱ]/g, "ا").replace(/ى/g, "ي").replace(/ة/g, "ه").replace(/[^\u0621-\u064A\s]/g, " ");
  // Share of the quoted words found in a narration's text: Dorar's search also returns other hadiths on the same theme.
  function wordingScore(q, text) {
    const qs = normAr(q).split(/\s+/).filter(w => w.length > 1), ts = new Set(normAr(text).split(/\s+/));
    if (!qs.length) return 0;
    return qs.filter(w => ts.has(w) || ts.has(w.replace(/^(و|ف|ب|ل|ال)/, "")) || ts.has("ال" + w)).length / qs.length;
  }
  const CAT = { sahih: ["صحيح أو ثابت", "k-ok"], hasan: ["حسن", "k-ref"], daif: ["ضعيف أو فيه علة", "k-fix"], fabricated: ["موضوع أو لا أصل له", "k-bad"], other: ["حكم آخر", "k-neu"] };
  async function loadDorar(el) {
    try {
      const res = await fetch("/api/dorar?q=" + encodeURIComponent(el.dataset.q), { headers: headers(false) });
      const d = await res.json();
      if (!res.ok || !d.available) throw new Error(d.error || "unavailable");
      if (!d.items.length) { el.innerHTML = `<span class="cap">لم تُرجع الدرر السنية نتائج لهذا اللفظ. <a href="https://dorar.net/hadith/search?q=${encodeURIComponent(d.query)}" target="_blank" rel="noopener">ابحث في الدرر</a></span>`; return; }
      const order = ["sahih", "hasan", "daif", "fabricated", "other"];
      const same = d.items.filter(i => wordingScore(el.dataset.q, i.text) >= 0.6);
      const near = d.items.filter(i => !same.includes(i));
      const counts = {}; same.forEach(i => { counts[i.category] = (counts[i.category] || 0) + 1; });
      const mixed = (counts.sahih || counts.hasan) && (counts.daif || counts.fabricated);
      const row = (i, hide) => `<div class="dorar-row" ${hide ? "data-extra hidden" : ""}><div class="row-between"><b>${esc(i.scholar)}</b><span class="chip ${CAT[i.category][1]}">${esc(i.grade || "—")}</span></div><span class="dtext">${esc(i.text.length > 140 ? i.text.slice(0, 140) + "…" : i.text)}</span><span class="cap">${esc(i.source)}${i.page ? " · " + esc(i.page) : ""}${i.narrator ? " · الراوي: " + esc(i.narrator) : ""}</span></div>`;
      let h = `<div class="src"><b style="font-size: 14px">أحكام المحدثين كما في الدرر السنية</b>`;
      if (same.length) {
        h += `<span class="cap">${AR_DIGITS(same.length)} رواية بهذا اللفظ:</span><div class="counts">${order.filter(c => counts[c]).map(c => `<span class="chip ${CAT[c][1]}">${AR_DIGITS(counts[c])} ${CAT[c][0]}</span>`).join("")}</div>
        ${mixed ? `<span class="cap">الأحكام مختلفة؛ تُعرض كما هي دون ترجيح.</span>` : ""}
        <div>${same.map((i, k) => row(i, k >= 4)).join("")}</div>
        ${same.length > 4 ? `<button class="link" data-allrows>عرض الأحكام كلها (${AR_DIGITS(same.length)})</button>` : ""}`;
      } else {
        h += `<span class="cap">لم نجد هذا اللفظ بعينه في نتائج الدرر.</span>`;
      }
      if (near.length) h += `<details><summary class="cap" style="cursor: pointer">${AR_DIGITS(near.length)} حديث بألفاظ قريبة، ليست هذا النص بعينه</summary><div>${near.map(i => row(i, false)).join("")}</div></details>`;
      h += `<span class="cap">المصدر: الموسوعة الحديثية، الدرر السنية · <a href="https://dorar.net/hadith/search?q=${encodeURIComponent(d.query)}" target="_blank" rel="noopener">افتح البحث في الدرر</a></span></div>`;
      el.innerHTML = h;
    } catch (e) {
      el.innerHTML = `<span class="cap">تعذر جلب أحكام المحدثين الآن. <a href="https://dorar.net/hadith/search?q=${encodeURIComponent(el.dataset.q)}" target="_blank" rel="noopener">ابحث في الدرر السنية مباشرة</a></span>`;
    }
  }

  async function loadTafsir(btn) {
    const out = btn.parentElement.nextElementSibling;
    btn.disabled = true; out.innerHTML = `<span class="cap">جارٍ التحميل…</span>`;
    try {
      const res = await fetch("/api/tafsir/" + encodeURIComponent(btn.dataset.tafsir), { headers: headers(false) });
      const d = await res.json(); if (!res.ok) throw new Error();
      out.innerHTML = d.verses.flatMap(vv => vv.entries.map(en => `<details class="src" open><summary style="cursor: pointer"><b>${esc(en.name_ar)}</b> <span class="cap">${esc(en.author_ar)}</span></summary><div class="q" style="font-size: 18px; line-height: 2">${esc(en.text)}</div></details>`)).join("") || `<span class="cap">لا يتوفر تفسير لهذه الآية في مصادرنا.</span>`;
      btn.remove();
    } catch (e) { out.innerHTML = `<span class="cap">تعذر تحميل التفسير.</span>`; btn.disabled = false; }
  }

  async function explain(btn) {
    const e = store.entries.find(x => x.n === +btn.dataset.explain), out = btn.parentElement.querySelector(".explain-out");
    const payload = e.it.kind === "claim" ? { claim: e.it.text, result: e.it.result } : e.it.kind === "quote" ? { claim: e.it.text, segment: e.it.quote } : null;
    if (!payload) { out.innerHTML = `<span class="cap">لا يتوفر شرح لهذا النوع.</span>`; return; }
    btn.disabled = true; out.innerHTML = `<span class="cap">جارٍ كتابة الشرح…</span>`;
    try {
      const res = await fetch("/api/explain", { method: "POST", headers: headers(true), body: JSON.stringify(payload) });
      const d = await res.json(); if (!res.ok) throw new Error();
      out.innerHTML = `<div class="src" style="border-style: dashed"><span class="gen" style="align-self: flex-start">${d.ai_written ? "كتبه الذكاء الاصطناعي من النصوص المعروضة فقط، وليس من نصوص المصادر" : "شرح مبسّط مولَّد آليًا من النتيجة"}</span>
        ${d.summary_ar ? `<b>${esc(d.summary_ar)}</b>` : ""}${(d.points || []).map(p => `<p style="margin: 0; line-height: 1.9">${esc(p.text)}</p>`).join("")}${d.caution ? `<span class="cap">${esc(d.caution)}</span>` : ""}</div>`;
      btn.remove();
    } catch (err) { out.innerHTML = `<span class="cap">تعذر كتابة الشرح الآن.</span>`; btn.disabled = false; }
  }

  function summaryText() {
    const lines = ["تقرير مراجعة مَنبَع", ""];
    for (const e of store.entries) {
      lines.push(`${e.n}. [${e.v.label}] ${e.it.text}`);
      if (e.v.why) lines.push(`   ${e.v.why}`);
      if (e.v.next) lines.push(`   الخطوة التالية: ${e.v.next}`);
      if (e.v.copy) lines.push(`   النص الصحيح: ${e.v.copy}`);
    }
    lines.push("", "بيان لمواضع النصوص في المصادر وليس فتوى. المصادر: المصحف، الكتب التسعة، الدرر السنية، الموسوعة الفقهية الكويتية.");
    return lines.join("\n");
  }
  async function copy(text, btn) {
    try { await navigator.clipboard.writeText(text); const t = btn.textContent; btn.textContent = "نُسخ"; setTimeout(() => { btn.textContent = t; }, 1500); }
    catch (e) { window.prompt("انسخ النص:", text); }
  }

  $("reportView").addEventListener("click", ev => {
    const t = ev.target.closest("button, a"); if (!t) return;
    if (t.dataset.goto) { const e = store.entries.find(x => x.n === +t.dataset.goto), card = $("card-" + e.n); if (card.hidden) { store.filter = "all"; applyFilter(); }
      card.scrollIntoView({ behavior: "smooth", block: "start" }); card.classList.add("flash"); setTimeout(() => card.classList.remove("flash"), 1400); if (card.querySelector(".more").hidden) openCard(e, card); return; }
    if (t.dataset.open) { const e = store.entries.find(x => x.n === +t.dataset.open); openCard(e, t.closest(".card")); return; }
    if (t.dataset.copy) { const e = store.entries.find(x => x.n === +t.dataset.copy); copy(e.v.copy, t); return; }
    if (t.dataset.f) { store.filter = t.dataset.f; applyFilter(); return; }
    if (t.dataset.tafsir) { loadTafsir(t); return; }
    if (t.dataset.explain) { explain(t); return; }
    if (t.hasAttribute("data-allrows")) { t.parentElement.querySelectorAll("[data-extra]").forEach(r => { r.hidden = false; }); t.remove(); return; }
    if (t.id === "copySummary") { copy(summaryText(), t); return; }
    if (t.id === "printBtn") { document.querySelectorAll(".more").forEach(m => { m.hidden = true; }); window.print(); return; }
    if (t.id === "editBtn") { $("newBtn").onclick(); return; }
  });

  // ---------- dialogs and settings ----------
  $("aboutBtn").onclick = () => $("aboutDlg").showModal();
  $("settingsBtn").onclick = () => $("settingsDlg").showModal();
  for (const [id, key] of [["token", "manba_access_token"], ["orkey", "manba_openrouter_key"], ["gkey", "manba_gemini_key"], ["provider", "manba_llm_provider"]]) {
    try { $(id).value = localStorage.getItem(key) || ""; } catch (e) {}
    $(id).addEventListener("change", () => { try { localStorage.setItem(key, $(id).value.trim()); } catch (e) {} });
  }
  fetch("/api/config").then(r => r.json()).then(c => {
    const k = c.server_keys || {};
    const has = Object.keys(k).filter(x => k[x]);
    $("cfgNote").textContent = `تبقى المفاتيح في متصفحك فقط. ${has.length ? "لدى الخادم مفتاح جاهز، فلا حاجة لإدخال مفتاحك." : "لا يوجد مفتاح على الخادم: أدخل مفتاحك ليعمل تقييم الادعاءات."}${c.access_required ? " الخادم يطلب رمز دخول." : ""}`;
  }).catch(() => {});

  updateCount();
})();
