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

  // A quote in another language: compared with the official translations (QuranEnc for the Quran), which lead to the Arabic.
  const NOT_IN_TR = "not found in the official translations searched";
  function trVerdict(sg, text) {
    const t = sg.translation, s = sg.source, quran = sg.classification === "quran" || isQuran(s);
    const type = quran ? "آية" : sg.classification === "hadith" ? "حديث" : "اقتباس";
    const used = ((store.data && store.data.translations_used) || []).join("، ");
    if (!t) return { k: "bad", label: quran ? "لم نجده في الترجمات المعتمدة" : sg.classification === "hadith" ? "لم نجده في الأحاديث المترجمة" : "لم نجده في الترجمات المعتمدة",
      type, why: `بحثنا عنه في: ${used || "الترجمات المعتمدة"}.`, next: "لا يُنسب إلى الله أو إلى النبي ﷺ حتى يُعرف مصدره" };
    const at = quran ? surahRef(s) : where(s);
    if (sg.status === "verified") {
      const base = segVerdict(Object.assign({}, sg, { translation: null }), text);
      return Object.assign({}, base, { label: quran ? "ترجمة معتمدة لآية" : base.label, why: `${at} · مطابق للترجمة المعتمدة: ${t.title}`, trans: t });
    }
    const ref = (sg.differences || []).find(d => /^the reference given/.test(d));
    const miss = ((sg.differences || []).find(d => /^words not in/.test(d)) || "").replace(/^words not in the official translation: /, "");
    return { k: "fix", label: ref ? "عُزي إلى غير موضعه" : "ترجمة بلفظ يخالف المعتمدة", type, trans: t,
      why: ref ? `الكلمات من ${at}، لا من الموضع المذكور في النص.` : `أقرب نص: ${at}.${miss ? ` كلمات ليست في الترجمة المعتمدة: ${miss}.` : ""}`,
      next: ref ? "صحّح الإحالة" : "انقل الترجمة المعتمدة بلفظها", copy: t.text, copyLtr: true, dorar: false };
  }

  function segVerdict(sg, text) {
    if (sg.translation || (sg.differences || []).includes(NOT_IN_TR)) return trVerdict(sg, text);
    const s = sg.source, quran = sg.classification === "quran" || isQuran(s);
    if (sg.status === "verified" && s) {
      if (quran) return { k: "ok", label: "آية موثّقة", type: "آية", why: surahRef(s) };
      const st = s.strength;
      if (st === "sahihayn") return { k: "ok", label: "حديث صحيح", type: "حديث", why: `${where(s)} · في الصحيحين، وقد تلقتهما الأمة بالقبول` };
      if (st === "sahih") return { k: "ok", label: "حديث صحيح", type: "حديث", why: where(s) };
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
  // The three input tabs: a pill slides under the chosen tab, and the new pane slides in from the side of its tab (the tabs run right to left).
  const TAB_ORDER = ["paste", "file", "scan"], TAB_IDS = { paste: "tabPaste", file: "tabFile", scan: "tabScan" }, PANE_IDS = { paste: "panePaste", file: "paneFile", scan: "paneScan" };
  let currentTab = "paste", pillReady = false;
  function placePill() {
    const bar = document.querySelector(".tabs"), pill = $("tabPill"), t = $(TAB_IDS[currentTab]);
    if (!bar || !pill || !t || !t.offsetWidth) return;   // not shown right now: placed again when it is (see the observer below)
    pill.style.width = t.offsetWidth + "px"; pill.style.height = t.offsetHeight + "px";
    pill.style.transform = `translate(${t.offsetLeft}px, ${t.offsetTop}px)`;
    if (!pillReady) { pillReady = true; requestAnimationFrame(() => requestAnimationFrame(() => pill.classList.add("slide"))); }   // the first placement is not animated
  }
  function showTab(which) {
    const from = TAB_ORDER.indexOf(currentTab), to = TAB_ORDER.indexOf(which);
    for (const k of TAB_ORDER) { $(TAB_IDS[k]).setAttribute("aria-selected", String(which === k)); $(PANE_IDS[k]).hidden = which !== k; }
    currentTab = which; placePill();
    const pane = $(PANE_IDS[which]);
    if (from !== to && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
      pane.style.setProperty("--from", to > from ? "-30px" : "30px");
      pane.classList.remove("pane-in"); void pane.offsetWidth; pane.classList.add("pane-in");
      pane.addEventListener("animationend", () => pane.classList.remove("pane-in"), { once: true });
    }
  }
  (() => { const bar = document.querySelector(".tabs"); if (!bar) return; bar.classList.add("has-pill"); if (window.ResizeObserver) { const ro = new ResizeObserver(placePill); /* a tab can change width (font loading, bold) without the bar changing */ ro.observe(bar); bar.querySelectorAll(".tab").forEach(t => ro.observe(t)); } window.addEventListener("resize", placePill); if (document.fonts && document.fonts.ready) document.fonts.ready.then(placePill); placePill(); })();
  $("tabPaste").onclick = () => showTab("paste");
  $("tabFile").onclick = () => showTab("file");
  $("tabScan").onclick = () => showTab("scan");
  // Scan a PDF or image (static/ocr.js): the text lands in the same box, so the word count and the review button below work unchanged.
  if (typeof Ocr !== "undefined") Ocr.mount($("scanRoot"), { textarea: $("text"), headers: () => headers(true), lang: "ar", onReview: () => { showTab("paste"); $("text").focus(); } });
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
  let timer = null, typers = [], loading = null;
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  // Each step is written letter by letter when it appears; the next one then appears below it and the card grows (the earlier steps turn into a tick).
  function typeInto(node, text, reduced, speed) {
    if (reduced) { node.textContent = text; return; }
    let n = 0; node.classList.add("typing");
    const id = setInterval(() => { n++; node.textContent = text.slice(0, n); if (n >= text.length) { clearInterval(id); node.classList.remove("typing"); } }, speed || 38);
    node._typer = id; typers.push(id);
  }
  function startLoading() {
    $("inputView").hidden = true; $("reportView").hidden = true; $("loadingView").hidden = false;
    const box = $("steps"), reduced = matchMedia("(prefers-reduced-motion: reduce)").matches; let i = -1;
    box.innerHTML = ""; $("barFill").style.width = "0";
    const ctl = loading = { reduced, step: () => i, last: STEPS.length - 1, box };
    ctl.next = fast => {
      i++;
      const prev = box.lastElementChild;
      if (prev) {   // the earlier step is finished at once if it was still being written
        const t = prev.querySelector(".t"); clearInterval(t._typer); t.textContent = STEPS[i - 1]; t.classList.remove("typing");
        prev.className = "step done"; prev.querySelector(".d").textContent = "✓";
      }
      const el = document.createElement("div"); el.className = "step now enter";
      el.innerHTML = `<span class="d">${AR_DIGITS(i + 1)}</span><span class="t"></span>`;
      box.appendChild(el); typeInto(el.querySelector(".t"), STEPS[i], reduced, fast ? 16 : 38);
      $("barFill").style.width = Math.min(92, 12 + i * 24) + "%";
    };
    ctl.next();
    timer = setInterval(() => { if (i < STEPS.length - 1) ctl.next(); }, 3500);
  }
  // The answer can come back at once (it was checked before and is kept): the person still sees every step, quickly, so it is clear what was checked.
  async function finishLoading() {
    const ctl = loading; if (!ctl) return;
    clearInterval(timer); timer = null;
    const k = ctl.reduced ? 0.15 : 1;
    while (ctl.step() < ctl.last) { ctl.next(true); await sleep(900 * k); }
    const last = ctl.box.lastElementChild;
    if (last && last.querySelector(".t.typing")) await sleep(700 * k);   // the last step finishes being written
    if (last) { const t = last.querySelector(".t"); clearInterval(t._typer); t.textContent = STEPS[ctl.last]; t.classList.remove("typing"); last.className = "step done"; last.querySelector(".d").textContent = "✓"; }
    $("barFill").style.width = "100%";
    await sleep(500 * k);
  }
  function stopLoading() { clearInterval(timer); typers.forEach(clearInterval); typers = []; loading = null; $("loadingView").hidden = true; }

  // ---------- run ----------
  async function run() {
    const text = $("text").value.trim();
    if (!text || words() > MAX_WORDS) return;
    startLoading();
    try {
      const res = await fetch("/api/check", { method: "POST", headers: headers(true), body: JSON.stringify({ text, use_llm: true, use_meaning: true }) });
      const data = await res.json().catch(() => ({}));
      if (res.status === 401) { stopLoading(); $("inputView").hidden = false; alertInline("الخادم يطلب رمز دخول: أدخله من الإعدادات."); openSettings(); return; }
      if (res.status === 422) throw new Error("النص طويل أو غير صالح للفحص. اختصره إلى 500 كلمة أو أقل.");
      if (!res.ok) throw new Error("تعذر الفحص الآن. أعد المحاولة بعد قليل.");
      await finishLoading();
      stopLoading();
      renderReport(data);
      history.pushState({ report: true }, "", "#report");
    } catch (e) {
      stopLoading(); $("inputView").hidden = false; alertInline(e.message || "تعذر الاتصال بالخادم. تحقق من الاتصال وأعد المحاولة.");
    }
  }
  $("go").onclick = run;
  // "New review" is a button in the report's summary card (next to copy and print); the report is its only place, so there is nothing to show or hide.
  function newReview(fromHistory) { $("reportView").hidden = true; $("inputView").hidden = false; if (!fromHistory) history.pushState({}, "", "#"); $("text").focus(); popIn(); }
  window.addEventListener("popstate", () => { if (!location.hash.includes("report")) newReview(true); });

  // ---------- "what we check" boxes: each opens an example of the report it produces ----------
  // Built from the same card markup as the real report, so the preview is what the reviewer will get.
  function pvCard(c) {
    return `<article class="card ${c.k === "bad" ? "k-bad-b" : ""}" style="animation: none">
      <div class="head"><div><span class="num">${AR_DIGITS(c.n || 1)}</span><span class="chip k-${c.k}">${esc(c.label)}</span>${c.lvl ? `<span class="lv">مستوى ${c.lvl}</span>` : ""}</div><span class="cap">${esc(c.type)}</span></div>
      <div class="quote" dir="auto">${esc(c.quote)}</div>
      ${c.why ? `<p class="why">${esc(c.why)}</p>` : ""}${c.extra || ""}
      ${c.next ? `<div class="next"><b>الخطوة التالية: ${esc(c.next)}</b>${c.copy ? `<div class="${c.ltr ? "tr-copy" : "q"}" dir="auto" style="font-size: ${c.ltr ? 16 : 19}px; line-height: 2">${esc(c.copy)}</div>` : ""}</div>` : ""}
    </article>`;
  }
  const PREVIEWS = {
    quran: { title: "الآيات", lead: "كل آية تُطابَق حرفًا بحرف مع نص المصحف (Tanzil). إن تغيّرت كلمة بيّنّاها، وأعطيناك الآية الصحيحة لتنسخها.",
      input: "قال تعالى: «وأحل الله البيع وحرم الزنا»",
      out: () => pvCard({ k: "fix", label: "آية بلفظ محرّف", lvl: "أ", type: "آية", quote: "«وأحل الله البيع وحرم الزنا»", why: "يختلف عن نص المصحف في سورة البقرة، الآية ٢٧٥: «الزنا» مكان «الربا».", next: "استبدل بالنص الصحيح", copy: "وَأَحَلَّ ٱللَّهُ ٱلْبَيْعَ وَحَرَّمَ ٱلرِّبَوٰا۟" }) },
    hadith: { title: "الأحاديث", lead: "نبحث عن الحديث في الكتب التسعة، ونذكر كتابه ورقمه وأحكام المحدثين عليه. ما لا يوجد فيها نعرض أحكام العلماء عليه من الدرر السنية.",
      input: "قال رسول الله ﷺ: «اطلبوا العلم ولو في الصين». وقال ﷺ: «الراحمون يرحمهم الرحمن»",
      out: () => pvCard({ n: 1, k: "bad", label: "لم يوجد في كتب الحديث", lvl: "ج", type: "حديث", quote: "«اطلبوا العلم ولو في الصين»", why: "أحكام المحدثين على هذا اللفظ في الدرر السنية: ١١ ضعيف أو فيه علة، ٤ موضوع أو لا أصل له.", next: "لا يُنسب إلى النبي ﷺ حتى يثبت: احذفه أو تحقق منه" })
        + pvCard({ n: 2, k: "ok", label: "حديث صحيح", lvl: "أ", type: "حديث", quote: "«الراحمون يرحمهم الرحمن»", why: "جامع الترمذي · 1924",
          extra: `<div class="counts"><span class="chip k-ok">صحيح · الألباني</span><span class="chip k-ok">حسن صحيح · بشار عواد معروف</span></div>` }) },
    fiqh: { title: "الأحكام الفقهية", lead: "كل جملة فيها حكم (واجب، حرام، يجوز، بالإجماع…) نبحث عنها في الموسوعة الفقهية الكويتية، ونقرأ منها: هل نُقل فيها اتفاق أم خلاف؟ مع المجلد والصفحة وأقوال المذاهب بنصها.",
      input: "وزكاة الحلي المستعمل واجبة بالإجماع.",
      out: () => pvCard({ k: "bad", label: "إجماع مدّعى غير ثابت", lvl: "ج", type: "حكم فقهي", quote: "زكاة الحلي المستعمل واجبة بالإجماع", why: "النص يدّعي الإجماع، والموسوعة الفقهية تنقل في المسألة خلافًا (ج18، ص113، مادة «حلي»).",
        extra: `<p class="why">في التقرير الفعلي تظهر فقرة الموسوعة بنصها وأقوال المذاهب كما وردت فيها: الوجوب عند الحنفية، وعدمه عند الجمهور.</p>`,
        next: "احذف ادعاء الإجماع، واذكر الخلاف أو انسب القول إلى قائله" }) },
    lang: { title: "بلغات أخرى", lead: "اقتباس الآية بالإنجليزية أو الفرنسية أو الأردية أو غيرها لا يُقارن بنص كتبه أحد من ذاكرته: نبحث عنه في الترجمات المعتمدة من موسوعة القرآن الكريم المترجمة (QuranEnc)، ثم نعرض الأصل العربي من المصحف. والادعاء بلغة أخرى يُترجم إلى العربية ويُفحص كأي ادعاء.",
      input: "Allah says: \"Allah has permitted trade and forbidden adultery\" (2:275).",
      out: () => pvCard({ k: "fix", label: "ترجمة بلفظ يخالف المعتمدة", lvl: "أ", type: "آية", quote: "\"Allah has permitted trade and forbidden adultery\"", why: "أقرب نص: سورة البقرة، الآية ٢٧٥. كلمات ليست في الترجمة المعتمدة: adultery.",
        next: "انقل الترجمة المعتمدة بلفظها", copy: "Allah has permitted trade and has forbidden interest.", ltr: true }) },
  };
  let previewKey = null;
  function openPreview(key) {
    const pv = PREVIEWS[key]; if (!pv) return;
    previewKey = key;
    $("previewTitle").textContent = pv.title; $("previewLead").textContent = pv.lead;
    $("previewInput").textContent = pv.input; $("previewOut").innerHTML = `<span class="cap pv-tag">مثال توضيحي لما يظهر في التقرير</span>` + pv.out();
    const d = $("previewDlg"); d.showModal ? d.showModal() : d.setAttribute("open", "");
  }
  document.querySelectorAll("[data-preview]").forEach(el => {
    el.addEventListener("click", () => openPreview(el.dataset.preview));
    el.addEventListener("keydown", ev => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); openPreview(el.dataset.preview); } });
  });
  $("previewTry").onclick = () => {
    const pv = PREVIEWS[previewKey]; if (!pv) return;
    $("previewDlg").close(); $("text").value = pv.input; updateCount(); run();
  };

  // ---------- report ----------
  // The first thing the reviewer reads: what stops publication, in one sentence.
  // The verdict speaks about the kind of text entered: a sermon is delivered, a post is published (services/genre.py).
  function trNote(data) {
    const used = data.translations_used || [], quran = used.filter(t => !/hadith/i.test(t)).length, hadith = used.some(t => /hadith/i.test(t));
    if (!used.length) return "لا توجد عندنا ترجمة معتمدة لهذه اللغة، فلم تُفحص إلا الاقتباسات العربية فيه.";
    return `قُورنت الاقتباسات بـ${AR_DIGITS(quran)} ${quran > 2 ? "ترجمات" : "ترجمة"} معتمدة للقرآن من موسوعة القرآن الكريم المترجمة (QuranEnc)${hadith ? " وبالترجمة الإنجليزية لسبعة من كتب الحديث" : ""}، ثم بأصلها العربي. اسم الترجمة يظهر في تفاصيل كل نتيجة.`;
  }
  const LANG_AR = { en: "بالإنجليزية", fr: "بالفرنسية", ur: "بالأردية", id: "بالإندونيسية", tr: "بالتركية", es: "بالإسبانية", other: "بلغة أخرى" };
  const TYPES = {
    khutbah: { label: "خطبة", the: "هذه الخطبة", f: true, act: "للإلقاء", tip: "صحّح المواضع المظللة قبل صعود المنبر؛ ما يُقال على المنبر يُنقل عن الخطيب." },
    post: { label: "منشور", the: "هذا المنشور", act: "للنشر", tip: "المنشور يُعاد نشره بلا ضابط؛ تصحيحه قبل النشر أيسر من تتبّعه بعده." },
    article: { label: "مقال", the: "هذا المقال", act: "للنشر" },
    lesson: { label: "درس", the: "هذا الدرس", act: "للإلقاء" },
    question: { label: "سؤال", the: "هذا النص", act: "للنشر", tip: "إن كان سؤالًا عن حالة بعينها فجوابه عند عالم يسمع تفاصيلها." },
    text: { label: "نص", the: "هذا النص", act: "للنشر" },
  };
  function headline(needs, counts) {
    const t = TYPES[store.type] || TYPES.text, ready = t.f ? "جاهزة" : "جاهز", inIt = t.f ? "فيها" : "فيه";
    if (needs) return `${t.the} غير ${ready} ${t.act}: ${AR_DIGITS(needs)} ${needs === 1 ? "موضع يحتاج" : needs === 2 ? "موضعان يحتاجان" : "مواضع تحتاج"} تعديلًا`;
    if (counts.khl) return `${t.the} ${ready} ${t.act}، و${inIt} مسائل خلافية تُنسب إلى قائليها`;
    if (counts.ref) return `${t.the} ${ready} ${t.act}، و${inIt} ما يُحال إلى مختص`;
    return `${t.the} ${ready} ${t.act} من جهة النصوص والأحكام التي ${inIt}`;
  }
  function typeLine(data) {
    const cues = (data.content_type_cues || []).map(c => `«${esc(c)}»`).join("، ");
    return `<div class="typeline no-print"><label for="typeSel" class="cap">نوع النص:</label>
      <select id="typeSel">${Object.keys(TYPES).map(k => `<option value="${k}" ${k === store.type ? "selected" : ""}>${TYPES[k].label}</option>`).join("")}</select>
      ${cues ? `<span class="cap">عرفناه من: ${cues}</span>` : ""}</div>`;
  }
  function renderReport(data) {
    store.data = data;
    store.type = data.content_type || "text";
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
          <button class="btn primary" id="newBtn">مراجعة نص جديد</button>
        </div>
      </div>
      ${store.entries.length ? `<p class="headline" id="headline" tabindex="-1">${headline(needs, counts)}</p>${typeLine(data)}${needs && (TYPES[store.type] || {}).tip ? `<p class="cap type-tip" id="typeTip">${TYPES[store.type].tip}</p>` : `<p class="cap type-tip" id="typeTip" hidden></p>`}<div class="seg" aria-hidden="true">${["bad", "fix", "khl", "ref", "neu", "ok"].filter(k => counts[k]).map(k => `<i class="s-${k}" style="flex: ${counts[k]}"></i>`).join("")}</div>
      <div class="counts">
        ${["bad", "fix", "khl", "ref", "neu", "ok"].filter(k => counts[k]).map(k => `<span class="chip k-${k}">${AR_DIGITS(counts[k])} ${K_LABEL[k]}</span>`).join("")}</div>` : ""}
      ${data.language && data.language !== "ar" ? `<div class="notice" role="status">النص ${esc(LANG_AR[data.language] || "بلغة أخرى")}: ${trNote(data)}${llmOff ? " ترجمة الادعاءات غير المقتبسة إلى العربية تحتاج الذكاء الاصطناعي، وهو غير متاح الآن." : ""}</div>` : ""}
      ${llmOff && !(data.language && data.language !== "ar") ? `<div class="notice" role="status">خدمة الذكاء الاصطناعي غير متاحة الآن، فتحققنا من الاقتباسات والأحكام الفقهية الصريحة بالمطابقة المباشرة فقط. قد لا تظهر الادعاءات غير المقتبسة.</div>` : ""}
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
          <p dir="${data.language && data.language !== "ar" && data.language !== "ur" ? "ltr" : "rtl"}">${markedText(data.original_text)}</p>
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
    if (typeof Ocr !== "undefined" && Ocr.active()) rv.insertAdjacentHTML("afterbegin", Ocr.warningHtml());  // the text was read from a scan: say so on the report too
    rv.classList.toggle("foreign", !!(data.language && data.language !== "ar" && data.language !== "ur"));
    rv.hidden = false;
    applyFilter();
    window.scrollTo({ top: 0 });
    // Details stay closed until the reviewer opens a card; the card itself already says what is wrong and what to do.
    const sel = $("typeSel");
    if (sel) sel.onchange = () => {
      store.type = sel.value;
      $("headline").textContent = headline(needs, counts);
      const tip = $("typeTip"), tp = (TYPES[store.type] || {}).tip;
      tip.hidden = !(needs && tp); tip.textContent = tp || "";
    };
    const hl = $("headline"); if (hl) hl.focus({ preventScroll: true });  // keyboard and screen-reader users land on the verdict
    dorarSummaries();
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
    const quoteText = isQuoteish(v) ? shownQuote(it.text) : it.text;
    const isScripture = v.type === "آية" || v.type === "حديث" || v.type === "اقتباس";
    return `<article class="card ${v.k === "bad" ? "k-bad-b" : ""}" id="card-${e.n}" data-k="${v.k}" style="--i: ${e.n}">
      <div class="head">
        <div><span class="num" style="vertical-align: baseline">${AR_DIGITS(e.n)}</span><span class="chip k-${v.k}">${esc(v.label)}</span>${lvl ? `<span class="lv" title="${esc(LEVEL_TITLE[lvl] || "")}">مستوى ${esc(lvl)}</span>` : ""}</div>
        <span class="cap">${esc(v.type)}</span>
      </div>
      <div class="${isScripture ? "quote" : ""}" dir="auto" style="${isScripture ? "" : "font-size: 16px; line-height: 1.8"}">${esc(quoteText)}</div>
      ${it.translated_ar ? `<p class="cap tr-ar">ترجمة آلية بُحث بها في المصادر <span class="gen">مولَّد بالذكاء الاصطناعي</span>: ${esc(it.translated_ar)}</p>` : ""}
      ${v.why ? `<p class="why">${esc(v.why)}</p>` : ""}
      ${v.next ? `<div class="next"><b>الخطوة التالية: ${esc(v.next)}</b>${v.copy ? `<div class="${v.copyLtr ? "tr-copy" : "q"}" dir="auto" style="font-size: ${v.copyLtr ? 16 : 19}px; line-height: 2">${esc(v.copy)}</div>` : ""}</div>` : ""}
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
    const g = gradeChips(s, s.matched_text);
    return `<div class="src"><span class="cap">${esc(label || where(s))}</span><div class="q">${esc(s.matched_text)}</div>${g ? `<div class="counts">${g}</div>` : ""}</div>`;
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
  const gradeChips = (s, text) => window.ManbaGrades ? ManbaGrades.chips(s, k => "k-" + k, { text }) : "";
  // One evidence text: where it is, its grading (hadith) or its tafsir line (verse), and the text itself.
  const evItem = (it, lab) => {
    const g = gradeChips(it.source, it.source.matched_text);
    return `<div class="src"><span class="cap">${lab ? lab + " · " : ""}${esc(where(it.source))}</span><div class="q">${esc(it.source.matched_text)}</div>${g ? `<div class="counts">${g}</div>` : ""}${window.ManbaGrades ? ManbaGrades.context(it) : ""}</div>`;
  };
  function evidenceBlock(r) {
    const sup = (r.supporting || []).slice(0, 3), con = (r.contradicting || []).slice(0, 3);
    const side = [...(r.partial || []), ...(r.related || [])].slice(0, 6);
    return (sup.length ? `<b style="font-size: 14px">نصوص تؤيده</b>` + sup.map(x => evItem(x, "يؤيد")).join("") : "")
      + (con.length ? `<b style="font-size: 14px">نصوص تخالفه</b>` + con.map(x => evItem(x, "يخالف")).join("") : "")
      // Texts found by words or meaning that the judge did not count for or against: kept closed and labelled, because a verse
      // on fighting listed under a claim about violence reads as evidence when it is shown bare.
      + (side.length ? `<details class="related"><summary class="cap" style="cursor: pointer">${AR_DIGITS(side.length)} نصوص قريبة من موضوع العبارة، لم يُحكم بأنها تؤيدها أو تخالفها</summary>
          <p class="cap" style="margin: 6px 0">تُعرض للاطلاع فقط. اقرأ كل آية مع سياقها، ولا تُنسب إليها العبارة.</p>${side.map(x => evItem(x, "")).join("")}</details>` : "");
  }
  function detailsHtml(e) {
    const v = e.v, it = e.it;
    let h = "";
    const sg = v.seg;
    if (v.trans) h += `<div class="src"><span class="cap">الترجمة المعتمدة: ${esc(v.trans.title)}${v.trans.version ? ` · الإصدار ${esc(v.trans.version)}` : ""}${v.trans.source_url ? ` · <a href="${esc(v.trans.source_url)}" target="_blank" rel="noopener">${v.trans.kind === "quran" ? "QuranEnc" : "المصدر"}</a>` : ""}</span><div dir="auto" style="line-height: 1.9">${esc(v.trans.text)}</div></div>`;
    if (sg && sg.source) h += sourceBlock(sg.source, v.trans ? `الأصل العربي: ${where(sg.source)}` : sg.status === "verified" ? where(sg.source) : `النص في المصدر: ${where(sg.source)}`) + (v.trans ? "" : diffBlock(sg));
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

  // The words inside «…», ﴿…﴾ or "…" when the sentence quotes them, else the sentence itself.
  function quoteOf(t) { const m = /[«"“﴿]([^»"”﴾]{4,})[»"”﴾]/.exec(t || ""); return (m ? m[1] : t || "").trim(); }
  // On a card, the quote with its marks ("«اطلبوا العلم ولو في الصين»"), not the sentence around it ("الحمد لله، أما بعد…").
  function shownQuote(t) { const m = /[«"“﴿][^»"”﴾]{4,}[»"”﴾]/.exec(t || ""); return m ? m[0] : t; }
  const isQuoteish = v => v.type === "آية" || v.type === "حديث" || v.type === "اقتباس";
  const normAr = t => (t || "").replace(/[\u064B-\u065F\u0670\u0640]/g, "").replace(/[إأآٱ]/g, "ا").replace(/ى/g, "ي").replace(/ة/g, "ه").replace(/[^\u0621-\u064A\s]/g, " ");
  // Share of the quoted words found in a narration's text: Dorar's search also returns other hadiths on the same theme.
  function wordingScore(q, text) {
    const qs = normAr(q).split(/\s+/).filter(w => w.length > 1), ts = new Set(normAr(text).split(/\s+/));
    if (!qs.length) return 0;
    return qs.filter(w => ts.has(w) || ts.has(w.replace(/^(و|ف|ب|ل|ال)/, "")) || ts.has("ال" + w)).length / qs.length;
  }
  const CAT = { sahih: ["صحيح أو ثابت", "k-ok"], hasan: ["حسن", "k-ref"], daif: ["ضعيف أو فيه علة", "k-fix"], fabricated: ["موضوع أو لا أصل له", "k-bad"], other: ["حكم آخر", "k-neu"] };
  const dorarCache = new Map();
  function fetchDorar(q) {
    if (!dorarCache.has(q)) dorarCache.set(q, fetch("/api/dorar?q=" + encodeURIComponent(q), { headers: headers(false) })
      .then(async res => { const d = await res.json(); if (!res.ok || !d.available) throw new Error(d.error || "unavailable"); return d; })
      .catch(e => { dorarCache.delete(q); throw e; }));
    return dorarCache.get(q);
  }
  // After the report is drawn: the scholars' rulings on the same wording, written into the card itself, so a reviewer sees
  // "١١ ضعيف، ٤ موضوع" without opening the details. Counts only; the rulings themselves stay in the details.
  async function dorarSummaries() {
    const targets = store.entries.filter(e => e.v.dorar).slice(0, 4);
    await Promise.all(targets.map(async e => {
      const q = quoteOf((e.v.seg && e.v.seg.segment_text) || e.it.text);
      try {
        const d = await fetchDorar(q);
        const same = d.items.filter(i => wordingScore(q, i.text) >= 0.6);
        const card = document.getElementById("card-" + e.n);
        if (!card || !same.length) return;
        const c = {}; same.forEach(i => { c[i.category] = (c[i.category] || 0) + 1; });
        const parts = ["sahih", "hasan", "daif", "fabricated", "other"].filter(k => c[k]).map(k => `${AR_DIGITS(c[k])} ${CAT[k][0]}`);
        const p = document.createElement("p"); p.className = "why dorar-sum";
        p.textContent = `أحكام المحدثين على هذا اللفظ في الدرر السنية: ${parts.join("، ")}.`;
        const why = card.querySelector(".why"); (why || card.querySelector(".head")).after(p);
      } catch (err) { /* the details still offer the Dorar link */ }
    }));
  }
  async function loadDorar(el) {
    try {
      const d = await fetchDorar(el.dataset.q);
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
    const hl = document.getElementById("headline");
    const lines = ["تقرير مراجعة مَنبَع", hl ? hl.textContent : "", ""];
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

  // A highlighted passage and its card point at each other: hover or focus one and the other lights up.
  (() => {
    const rv = $("reportView"); let now = null;
    const set = (n, on) => { const c = $("card-" + n); if (c) c.classList.toggle("hl", on); rv.querySelectorAll(`.mk[data-goto="${n}"]`).forEach(m => m.classList.toggle("hl", on)); };
    const which = el => { const m = el.closest && el.closest(".mk"); if (m) return m.dataset.goto; const c = el.closest && el.closest(".card"); return c ? c.id.replace("card-", "") : null; };
    const move = ev => { const n = which(ev.target); if (n === now) return; if (now) set(now, false); now = n; if (n) set(n, true); };
    const clear = () => { if (now) set(now, false); now = null; };
    // a colour in the summary (bar segment or count chip): every passage and card of that status lights up, the others dim
    let kind = null;
    const kindOf = el => { const t = el.closest && el.closest(".summary .seg i, .summary .counts .chip"); const m = t && /\b[sk]-(bad|fix|khl|ref|neu|ok)\b/.exec(t.className); return m ? m[1] : null; };
    const setKind = (k, on) => {
      if (on) rv.dataset.focus = k; else delete rv.dataset.focus;
      rv.querySelectorAll(`.mk.k-${k}`).forEach(m => m.classList.toggle("hl", on));
      rv.querySelectorAll(`#cards .card[data-k="${k}"]`).forEach(c => c.classList.toggle("hl-soft", on));
    };
    rv.addEventListener("mouseover", ev => { const k = kindOf(ev.target); if (k === kind) return; if (kind) setKind(kind, false); kind = k; if (k) setKind(k, true); });
    rv.addEventListener("mouseleave", () => { if (kind) setKind(kind, false); kind = null; });
    rv.addEventListener("mouseover", move); rv.addEventListener("focusin", move); rv.addEventListener("mouseleave", clear); rv.addEventListener("focusout", ev => { if (!rv.contains(ev.relatedTarget)) clear(); });
  })();
  $("reportView").addEventListener("click", ev => {
    const t = ev.target.closest("button, a"); if (!t) return;
    if (t.dataset.goto) { const e = store.entries.find(x => x.n === +t.dataset.goto), card = $("card-" + e.n); if (card.hidden) { store.filter = "all"; applyFilter(); }
      card.scrollIntoView({ behavior: "smooth", block: "start" }); card.classList.add("flash"); setTimeout(() => card.classList.remove("flash"), 1400); return; }
    if (t.dataset.open) { const e = store.entries.find(x => x.n === +t.dataset.open); openCard(e, t.closest(".card")); return; }
    if (t.dataset.copy) { const e = store.entries.find(x => x.n === +t.dataset.copy); copy(e.v.copy, t); return; }
    if (t.dataset.f) { store.filter = t.dataset.f; applyFilter(); return; }
    if (t.dataset.tafsir) { loadTafsir(t); return; }
    if (t.dataset.explain) { explain(t); return; }
    if (t.hasAttribute("data-allrows")) { t.parentElement.querySelectorAll("[data-extra]").forEach(r => { r.hidden = false; }); t.remove(); return; }
    if (t.id === "copySummary") { copy(summaryText(), t); return; }
    if (t.id === "printBtn") { document.querySelectorAll(".more").forEach(m => { m.hidden = true; }); window.print(); return; }
    if (t.id === "editBtn" || t.id === "newBtn") { newReview(); return; }
  });

  // ---------- theme: dark is the default; the button switches to light and back, and the choice is remembered ----------
  const root = document.documentElement, themeBtn = $("themeBtn");
  const isLight = () => root.dataset.theme === "light";
  function labelTheme() { const t = isLight() ? "الوضع الداكن" : "الوضع الفاتح"; themeBtn.setAttribute("aria-label", t); themeBtn.title = t; }
  themeBtn.onclick = () => {
    root.classList.add("theme-anim"); const next = isLight() ? "dark" : "light";
    if (next === "light") root.dataset.theme = "light"; else delete root.dataset.theme;
    try { localStorage.setItem("manba_theme", next); } catch (e) {}
    labelTheme(); themeBtn.classList.remove("spin"); void themeBtn.offsetWidth; themeBtn.classList.add("spin");
    setTimeout(() => root.classList.remove("theme-anim"), 500);
  };
  labelTheme();
  // a printed report is always on white paper, so it is printed in the light theme
  let themeBeforePrint = null;
  window.addEventListener("beforeprint", () => { themeBeforePrint = isLight(); root.dataset.theme = "light"; });
  window.addEventListener("afterprint", () => { if (themeBeforePrint === false) delete root.dataset.theme; themeBeforePrint = null; });

  // ---------- dialogs and settings ----------
  $("aboutBtn").onclick = () => $("aboutDlg").showModal();
  // Settings are saved only by the Save button. Closing the window any other way (a click outside it, Esc) throws the edits away, and the fields show what is saved the next time.
  // Every way of closing a dialog (its button, Esc, a click outside) first plays the closing animation (the window shrinks away), then closes it.
  function closeDialog(dlg) {
    if (!dlg.open || dlg.classList.contains("closing")) return;
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) { dlg.close(); return; }
    dlg.classList.add("closing");
    setTimeout(() => { dlg.classList.remove("closing"); if (dlg.open) dlg.close(); }, 230);
  }
  document.querySelectorAll("dialog").forEach(d => {
    d.addEventListener("cancel", ev => { ev.preventDefault(); closeDialog(d); });
    d.querySelectorAll('form[method="dialog"]').forEach(f => f.addEventListener("submit", ev => { ev.preventDefault(); closeDialog(d); }));
  });
  const SETTING_FIELDS = [["token", "manba_access_token"], ["orkey", "manba_openrouter_key"], ["gkey", "manba_gemini_key"], ["provider", "manba_llm_provider"]];
  const settingsDlg = $("settingsDlg");
  const loadSettings = () => { for (const [id, key] of SETTING_FIELDS) { let v = ""; try { v = localStorage.getItem(key) || ""; } catch (e) {} $(id).value = v; } };
  const saveSettings = () => { for (const [id, key] of SETTING_FIELDS) { try { localStorage.setItem(key, $(id).value.trim()); } catch (e) {} } };
  function openSettings() { loadSettings(); settingsDlg.showModal(); }
  $("settingsBtn").onclick = openSettings;
  loadSettings();
  settingsDlg.querySelector("form button").addEventListener("click", saveSettings);
  // A click outside any dialog closes it (with the closing animation). The press must also start outside, so selecting text inside and letting go outside does not close it.
  document.querySelectorAll("dialog").forEach(d => {
    const outside = ev => { const r = d.getBoundingClientRect(); return ev.clientX < r.left || ev.clientX > r.right || ev.clientY < r.top || ev.clientY > r.bottom; };
    let downOutside = false;
    d.addEventListener("pointerdown", ev => { downOutside = outside(ev); });
    d.addEventListener("click", ev => { if (downOutside && outside(ev)) closeDialog(d); downOutside = false; });
  });
  settingsDlg.addEventListener("close", loadSettings);   // after Save this shows the saved values; after any other way of closing it drops the edits
  // The parts of the home page pop in one after another (the CSS does the staggering); it is also replayed when a new review starts.
  function popIn() {
    const h = $("inputView"); if (!h) return;
    h.classList.remove("wait", "pop"); void h.getBoundingClientRect(); h.classList.add("pop");
  }
  // Intro: the logo is written over the blurred page (after the font has loaded, so the letters have their real shape), held a moment, then the
  // cover fades away. A click or a key skips it; with reduced motion it is not shown. (The CSS also hides it after 9 s whatever happens.)
  (function intro() {
    const cover = $("intro"), logo = $("introLogo"); if (!cover) return;
    let seen = false;
    try { seen = sessionStorage.getItem("manba_intro") === "1"; sessionStorage.setItem("manba_intro", "1"); } catch (e) {}
    // Once per visit: a reload during a demo goes straight to the page.
    if (seen || matchMedia("(prefers-reduced-motion: reduce)").matches) { cover.remove(); $("inputView").classList.remove("wait"); return; }
    let done = false, hold = null;
    const finish = () => { if (done) return; done = true; clearTimeout(hold); document.documentElement.style.overflow = ""; placePill(); cover.classList.add("out"); popIn(); setTimeout(() => cover.remove(), 700); };
    document.documentElement.style.overflow = "hidden";
    cover.addEventListener("click", finish); window.addEventListener("keydown", finish, { once: true });
    const font = document.fonts && document.fonts.load ? Promise.race([document.fonts.load('700 96px "Amiri"', "مَنبَع"), new Promise(r => setTimeout(r, 1500))]) : Promise.resolve();
    font.catch(() => {}).then(() => { if (done) return; logo.classList.add("go"); hold = setTimeout(finish, 2000); });  // writing takes about 1.7 s, then a short hold
  })();
  fetch("/api/config").then(r => r.json()).then(c => {
    const k = c.server_keys || {};
    const has = Object.keys(k).filter(x => k[x]);
    $("cfgNote").textContent = `تبقى المفاتيح في متصفحك فقط. ${has.length ? "لدى الخادم مفتاح جاهز، فلا حاجة لإدخال مفتاحك." : "لا يوجد مفتاح على الخادم: أدخل مفتاحك ليعمل تقييم الادعاءات."}${c.access_required ? " الخادم يطلب رمز دخول." : ""}`;
  }).catch(() => {});

  updateCount();
})();
