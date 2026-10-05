/* Manba reviewer page: input -> /api/check -> a report ordered by what must change before publishing.
   Every verdict shown here is read from the API result (sources, gradings, fiqh agreement), never invented in the page. */
(() => {
  const $ = id => document.getElementById(id);
  const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const AR_DIGITS = n => String(n).replace(/\d/g, d => "٠١٢٣٤٥٦٧٨٩"[d]);
  const MAX_WORDS = 500;
  // Interface language: Arabic (default) or English. Every string the page writes is given in both; L() picks one.
  let LANG = "ar";
  try { if (localStorage.getItem("manba_lang") === "en") LANG = "en"; } catch (e) {}
  const L = (ar, en) => (LANG === "en" ? en : ar);
  const P = x => (Array.isArray(x) ? L(x[0], x[1]) : x);
  const N = n => (LANG === "en" ? String(n) : AR_DIGITS(n));
  const LVL_EN = { "أ": "A", "ب": "B", "ج": "C", "د": "D" };
  const BOOK_EN = { "صحيح البخاري": "Sahih al-Bukhari", "صحيح مسلم": "Sahih Muslim", "سنن أبي داود": "Sunan Abi Dawud", "جامع الترمذي": "Jami' al-Tirmidhi",
    "سنن النسائي": "Sunan al-Nasa'i", "سنن ابن ماجه": "Sunan Ibn Majah", "موطأ مالك": "Muwatta Malik", "مسند أحمد": "Musnad Ahmad", "سنن الدارمي": "Sunan al-Darimi" };
  const SCHOOL_EN = { "الحنفية": "Hanafi", "المالكية": "Maliki", "الشافعية": "Shafi'i", "الحنابلة": "Hanbali", "الجمهور": "The majority", "الظاهرية": "Zahiri" };
  const RULING_EN = { "واجب": "obligatory", "غير واجب": "not obligatory", "سنة": "sunnah", "حرام": "forbidden", "لا يجوز": "not permitted", "مكروه": "disliked",
    "جائز": "permitted", "ينقض": "breaks wudu", "لا ينقض": "does not break wudu", "يبطل": "invalidates" };
  const TYPE_L = { quran: ["آية", "Verse"], hadith: ["حديث", "Hadith"], quote: ["اقتباس", "Quote"], fiqh: ["حكم فقهي", "Fiqh ruling"], claim: ["ادعاء", "Claim"] };

  const SURAH = ["الفاتحة","البقرة","آل عمران","النساء","المائدة","الأنعام","الأعراف","الأنفال","التوبة","يونس","هود","يوسف","الرعد","إبراهيم","الحجر","النحل","الإسراء","الكهف","مريم","طه","الأنبياء","الحج","المؤمنون","النور","الفرقان","الشعراء","النمل","القصص","العنكبوت","الروم","لقمان","السجدة","الأحزاب","سبأ","فاطر","يس","الصافات","ص","الزمر","غافر","فصلت","الشورى","الزخرف","الدخان","الجاثية","الأحقاف","محمد","الفتح","الحجرات","ق","الذاريات","الطور","النجم","القمر","الرحمن","الواقعة","الحديد","المجادلة","الحشر","الممتحنة","الصف","الجمعة","المنافقون","التغابن","الطلاق","التحريم","الملك","القلم","الحاقة","المعارج","نوح","الجن","المزمل","المدثر","القيامة","الإنسان","المرسلات","النبأ","النازعات","عبس","التكوير","الانفطار","المطففين","الانشقاق","البروج","الطارق","الأعلى","الغاشية","الفجر","البلد","الشمس","الليل","الضحى","الشرح","التين","العلق","القدر","البينة","الزلزلة","العاديات","القارعة","التكاثر","العصر","الهمزة","الفيل","قريش","الماعون","الكوثر","الكافرون","النصر","المسد","الإخلاص","الفلق","الناس"];
  const QURAN = "القرآن الكريم";

  const SAMPLES = [
    [["خطبة فيها أخطاء شائعة", "A khutbah with common mistakes"], "الحمد لله، أما بعد: أيها الإخوة، إن طلب العلم من أعظم القربات، وقد قال رسول الله ﷺ: «اطلبوا العلم ولو في الصين». ومن ثمرات العلم معرفة الحلال والحرام؛ قال تعالى: «وأحل الله البيع وحرم الزنا». ومن العلم الواجب على المرأة أن تعلم أن زكاة الحلي المستعمل واجبة بالإجماع، وأن التسمية عند الوضوء واجبة. فاصبروا على طلبه، فإن الله يقول: ﴿فإن مع العسر يسرا﴾."],
    [["منشور متداول", "A viral post"], "انشرها تؤجر! قال رسول الله ﷺ: «النظافة من الإيمان». وقال ﷺ: «اختلاف أمتي رحمة». وقال ﷺ: «الراحمون يرحمهم الرحمن، ارحموا من في الأرض يرحمكم من في السماء»."],
    [["ادّعاء إجماع في مسألة فقهية", "Consensus claimed on a fiqh question"], "أجمع العلماء على أن قراءة الفاتحة خلف الإمام واجبة. وأكل لحم الإبل ينقض الوضوء. وتارك الصلاة كسلًا كافر بالإجماع."],
    [["آية منقولة بخطأ", "A misquoted verse"], "قال تعالى: «وأحل الله البيع وحرم الزنا». وقال سبحانه: ﴿إن مع العسر يسرا﴾."],
    [["نسبة أقوال إلى المذاهب", "Rulings attributed to schools"], "التسمية عند الوضوء واجبة عند الحنفية. والوتر واجب عند الحنفية. وأكل لحم الإبل ينقض الوضوء عند الحنابلة."],
    [["مقال بالإنجليزية", "An English article"], "Dear brothers and sisters, Allah says: \"Indeed, with hardship comes ease\" (2:255). The Prophet ﷺ said: \"Cleanliness is half of faith.\" He also said: \"Seek knowledge even if you have to go to China.\" And Allah says: \"Allah has permitted trade and forbidden adultery\" (2:275)."],
  ];

  // ---------- verdicts: one plain-language class per result ----------
  // k: bad (must change) | fix (needs correcting) | khl (disputed, attribute it) | ref (refer) | neu (no conclusion) | ok (verified)
  const RANK = { bad: 0, fix: 1, khl: 2, ref: 3, neu: 4, ok: 5 };
  const K_LABEL = { bad: ["غير مُثبت", "Not established"], fix: ["يحتاج تصحيحًا", "Needs correcting"], khl: ["مسألة خلافية", "Disputed"], ref: ["يُحال إلى مختص", "Refer to a scholar"], neu: ["بلا حكم", "No conclusion"], ok: ["موثّق", "Verified"] };
  const LEVEL_TITLE = { "أ": ["مستوى أ: نص أصلي مستقر", "Level A: a settled text"], "ب": ["مستوى ب: شرح مع إظهار المرجع", "Level B: explanation with its reference"], "ج": ["مستوى ج: خلافي أو حساس", "Level C: disputed or sensitive"], "د": ["مستوى د: حالة شخصية تُحال", "Level D: a personal case, referred"] };
  const lvlTag = l => L(`مستوى ${l}`, `Level ${LVL_EN[l] || l}`);

  const surahRef = s => {
    const m = /^(\d+):(\d+)(?:-(\d+))?$/.exec((s && s.number) || "");
    if (m && LANG === "en") return `${s.chapter ? s.chapter + " " : "Quran "}${m[1]}:${m[2]}${m[3] ? "-" + m[3] : ""}`;
    return m ? `سورة ${SURAH[+m[1] - 1] || m[1]}، الآية ${AR_DIGITS(m[2])}${m[3] ? "–" + AR_DIGITS(m[3]) : ""}` : (s ? [s.book, s.number].filter(Boolean).join(" ") : "");
  };
  const isQuran = s => s && s.book === QURAN;
  const where = s => !s ? "" : isQuran(s) ? surahRef(s) : [LANG === "en" ? (BOOK_EN[s.book] || s.book) : s.book, s.number].filter(Boolean).join(" · ");
  const HADITH_CUE = /قال رسول الله|قال النبي|ﷺ|صلى الله عليه وسلم|رواه|حديث/;

  // A quote in another language: compared with the official translations (QuranEnc for the Quran), which lead to the Arabic.
  const NOT_IN_TR = "not found in the official translations searched";
  function trVerdict(sg, text) {
    const t = sg.translation, s = sg.source, quran = sg.classification === "quran" || isQuran(s);
    const t2 = quran ? "quran" : sg.classification === "hadith" ? "hadith" : "quote";
    const used = ((store.data && store.data.translations_used) || []).join(L("، ", ", "));
    if (!t) return { k: "bad", label: sg.classification === "hadith" ? L("لم نجده في الأحاديث المترجمة", "Not found in the translated hadith") : L("لم نجده في الترجمات المعتمدة", "Not in the approved translations"),
      t: t2, why: L(`بحثنا عنه في: ${used || "الترجمات المعتمدة"}.`, `Searched in: ${used || "the approved translations"}.`), next: L("لا يُنسب إلى الله أو إلى النبي ﷺ حتى يُعرف مصدره", "Do not attribute it to Allah or the Prophet ﷺ until its source is known") };
    const at = quran ? surahRef(s) : where(s);
    if (sg.status === "verified") {
      const base = segVerdict(Object.assign({}, sg, { translation: null }), text);
      return Object.assign({}, base, { label: quran ? L("ترجمة معتمدة لآية", "Approved translation of a verse") : base.label, why: L(`${at} · مطابق للترجمة المعتمدة: ${t.title}`, `${at} · matches the approved translation: ${t.title}`), trans: t });
    }
    const ref = (sg.differences || []).find(d => /^the reference given/.test(d));
    const miss = ((sg.differences || []).find(d => /^words not in/.test(d)) || "").replace(/^words not in the official translation: /, "");
    return { k: "fix", label: ref ? L("عُزي إلى غير موضعه", "Wrong reference") : L("ترجمة بلفظ يخالف المعتمدة", "Differs from the approved translation"), t: t2, trans: t,
      why: ref ? L(`الكلمات من ${at}، لا من الموضع المذكور في النص.`, `These words are from ${at}, not from the reference given.`) : L(`أقرب نص: ${at}.${miss ? ` كلمات ليست في الترجمة المعتمدة: ${miss}.` : ""}`, `Closest text: ${at}.${miss ? ` Words not in the approved translation: ${miss}.` : ""}`),
      next: ref ? L("صحّح الإحالة", "Correct the reference") : L("انقل الترجمة المعتمدة بلفظها", "Use the approved translation word for word"), copy: t.text, copyLtr: true, dorar: false };
  }

  function segVerdict(sg, text) {
    if (sg.translation || (sg.differences || []).includes(NOT_IN_TR)) return trVerdict(sg, text);
    const s = sg.source, quran = sg.classification === "quran" || isQuran(s);
    if (sg.status === "verified" && s) {
      if (quran) return { k: "ok", label: L("آية موثّقة", "Verified verse"), t: "quran", why: surahRef(s) };
      const st = s.strength;
      if (st === "sahihayn") return { k: "ok", label: L("حديث صحيح", "Authentic hadith"), t: "hadith", why: L(`${where(s)} · في الصحيحين، وقد تلقتهما الأمة بالقبول`, `${where(s)} · in al-Bukhari or Muslim, accepted as authentic by the Muslim community`) };
      if (st === "sahih") return { k: "ok", label: L("حديث صحيح", "Authentic hadith"), t: "hadith", why: where(s) };
      if (st === "hasan") return { k: "ok", label: L("حديث حسن", "Hasan hadith"), t: "hadith", why: where(s) };
      if (st === "daif") return { k: "bad", label: L("حديث ضعيف", "Weak hadith"), t: "hadith", why: L(`${where(s)} · حكم عليه العلماء بالضعف`, `${where(s)} · graded weak by the scholars`), next: L("لا يُستدل به، أو يُذكر مع بيان ضعفه", "Do not use it as evidence, or state that it is weak"), dorar: true };
      if (st === "disputed") return { k: "khl", label: L("أحكام المحدثين مختلفة", "Scholars' gradings differ"), t: "hadith", why: L(`${where(s)} · بعض العلماء صححه وبعضهم ضعفه`, `${where(s)} · some scholars graded it authentic, others weak`), next: L("اطّلع على أحكام المحدثين قبل الاستدلال به", "Read the gradings before using it as evidence"), dorar: true };
      return { k: "fix", label: L("درجته غير مبيّنة عندنا", "No grading in our data"), t: "hadith", why: where(s), next: L("تحقق من درجته في أحكام المحدثين", "Check its grading before using it"), dorar: true };
    }
    if (sg.status === "semantic_variant" && s) {
      return { k: "fix", label: quran ? L("آية بلفظ محرّف", "Verse with altered wording") : L("حديث بلفظ مختلف", "Hadith with different wording"), t: quran ? "quran" : "hadith",
        why: quran ? L(`يختلف عن نص المصحف في ${surahRef(s)}`, `Differs from the Mushaf at ${surahRef(s)}`) : L(`يختلف عن لفظه في ${where(s)}`, `Differs from its wording in ${where(s)}`),
        next: L("استبدل بالنص الصحيح", "Replace it with the correct text"), copy: s.matched_text, dorar: !quran };
    }
    const hadithy = HADITH_CUE.test(text || "") || sg.classification === "hadith";
    return { k: "bad", label: hadithy ? L("لم يوجد في كتب الحديث", "Not found in the hadith books") : L("لم يوجد في المصادر", "Not found in the sources"), t: hadithy ? "hadith" : "quote",
      why: hadithy ? L("لم نجده في الكتب التسعة. انظر أحكام المحدثين عليه في الدرر السنية.", "Not in the nine books. See the scholars' rulings on it from Dorar.") : L("لم نجده في المصحف ولا في الكتب التسعة.", "Not in the Mushaf or the nine hadith books."),
      next: hadithy ? L("لا يُنسب إلى النبي ﷺ حتى يثبت: احذفه أو تحقق منه", "Do not attribute it to the Prophet ﷺ until it is established: remove or verify it") : L("تحقق من مصدره قبل نشره", "Verify its source before publishing"), dorar: hadithy };
  }

  const FIQH_V = {
    school_differs: { k: "bad", label: ["نسبة القول إلى المذهب لا تطابق الموسوعة", "Attribution to the school does not match"], next: ["صحّح نسبة القول بحسب ما تنقله الموسوعة عن المذهب", "Correct the attribution to what the encyclopedia reports for that school"] },
    school_matches: { k: "ok", label: ["نسبة القول إلى المذهب صحيحة", "Attribution to the school is correct"], next: null },
    consensus_claim_disputed: { k: "bad", label: ["إجماع مدّعى غير ثابت", "Claimed consensus not established"], next: ["احذف ادعاء الإجماع، واذكر أقوال المذاهب أو انسب القول إلى قائله", "Remove the consensus claim; give the schools' views or attribute the opinion"] },
    stated_as_certain_disputed: { k: "khl", label: ["مسألة خلافية بصيغة القطع", "Disputed, stated as settled"], next: ["انسب القول إلى مذهبه، أو اذكر أقوال المذاهب", "Attribute the opinion to its school, or give the schools' views"] },
    partly_disputed: { k: "khl", label: ["اتفاق في جانب وخلاف في جانب", "Agreed in part, disputed in part"], next: ["راجع موضع الحكم في نص الموسوعة وصِغه بدقة", "Check the ruling in the encyclopedia's text and word it precisely"] },
    agreement_differs: { k: "bad", label: ["يخالف ما نُقل الاتفاق عليه", "Contradicts the reported agreement"], next: ["راجع الحكم في ضوء نص الموسوعة", "Revise the ruling in light of the encyclopedia"] },
    disagreement_acknowledged: { k: "ok", label: ["الخلاف مذكور", "Disagreement acknowledged"], next: null },
    agreement_reported: { k: "ok", label: ["موافق لما نُقل الاتفاق عليه", "Matches the reported agreement"], next: null },
    found_no_marker: { k: "neu", label: ["وُجدت المسألة دون تصريح باتفاق أو خلاف", "Found, no agreement or disagreement stated"], next: ["راجع نص الموسوعة", "Read the encyclopedia's text"] },
    not_found: { k: "neu", label: ["لم توجد في الموسوعة الفقهية", "Not found in the fiqh encyclopedia"], next: ["يُرجع فيها إلى مختص", "Refer it to a specialist"] },
  };
  const OUTCOME_V = {
    supported: { k: "neu", label: ["تأييد محتمل بتقييم آلي: يحتاج مراجعة", "AI-assessed support: needs review"] },
    supported_in_part: { k: "fix", label: ["مؤيد جزئيًا", "Partly supported"], next: ["قيّد العبارة بما تؤيده النصوص", "Limit the statement to what the texts support"] },
    supported_weakly: { k: "fix", label: ["دليله ضعيف", "Weak evidence only"], next: ["لا تبنِ عليه إلا بدليل ثابت", "Do not rely on it without authentic evidence"] },
    contradicted: { k: "bad", label: ["تخالفه الأدلة", "Contradicted by the evidence"], next: ["راجع العبارة في ضوء النصوص المعروضة", "Revise it in light of the texts shown"] },
    mixed: { k: "khl", label: ["أدلة من الجانبين", "Evidence on both sides"], next: ["يحتاج إلى عالم يوازن بين الأدلة", "A scholar is needed to weigh the evidence"] },
    no_clear_evidence: { k: "neu", label: ["لا دليل واضح", "No clear evidence"], next: ["لم نجد ما يؤيده أو يخالفه: تحقق منه", "Nothing found for or against it: verify it"] },
    refer_to_scholar: { k: "ref", label: ["يُحال إلى مختص", "Refer to a scholar"], next: ["مسألة شخصية: يُسأل فيها عالم مؤهل", "A personal case: ask a qualified scholar"] },
    evidence_only: { k: "neu", label: ["نصوص ذات صلة دون حكم", "Related texts, no verdict"] },
  };
  // A fiqh citation from its parts, in the interface language.
  const citeOf = p => !p ? "" : L(p.cite, `Kuwaiti Fiqh Encyclopedia, vol. ${p.volume}, p. ${p.page}, entry "${p.entry}"${p.number ? `, para. ${p.number}` : ""}`);

  function claimVerdict(r, text) {
    if (r.outcome === "quote_checked" && r.quote_check && r.quote_check.segments.length) {
      const vs = r.quote_check.segments.filter(s => s.is_claim !== false).map(s => ({ v: segVerdict(s, text), s }));
      if (vs.length) { vs.sort((a, b) => RANK[a.v.k] - RANK[b.v.k]); return Object.assign({ seg: vs[0].s }, vs[0].v); }
    }
    if (r.fiqh && FIQH_V[r.fiqh.status]) {
      const f = FIQH_V[r.fiqh.status], p = (r.fiqh.passages || [])[0];
      return { k: f.k, label: P(f.label), t: "fiqh", why: L(r.fiqh.summary_ar, r.fiqh.summary_en) + (p ? ` (${citeOf(p)})` : ""), next: P(f.next), fiqh: r.fiqh };
    }
    const o = OUTCOME_V[r.outcome] || { k: "neu", label: r.outcome };
    let why = L(r.summary_ar, r.summary_en) || "";
    if (r.outcome === "refer_to_scholar" && r.reason) why = L("مسألة تخص حالة بعينها؛ الحكم فيها يحتاج عالمًا يسمع تفاصيلها.", "A question about a particular case: answering it needs a scholar who hears its details.");
    return { k: o.k, label: P(o.label), t: "claim", why, next: P(o.next) };
  }

  function similarVerdict(sm) {
    const e = sm.evidence, s = e.source;
    return { k: "fix", label: L("قريب من نص معروف بلفظ مختلف", "Close to a known text, different wording"), t: isQuran(s) ? "quran" : "hadith",
      why: L(`يشبه ${where(s)} (${Math.round(sm.shared_share * 100)}٪ من كلماته المميزة)، وليس بلفظه.`, `Resembles ${where(s)} (${Math.round(sm.shared_share * 100)}% of its distinctive words), not its wording.`),
      next: L("انقل النص بلفظه من مصدره", "Quote it word for word from its source"), copy: s.matched_text, simItem: e };
  }

  function verdictOf(it) {
    const v = localVerdictOf(it);
    if (it.verdict_kind) {
      if (v.k === "ok" && it.verdict_kind !== "ok") v.label = L("مطابقة للمصدر تحتاج مراجعة", "Source match needs review");
      v.k = it.verdict_kind;
    }
    return v;
  }
  const needsAction = e => typeof e.it.needs_action === "boolean" && e.it.verdict_kind ? e.it.needs_action : e.v.k !== "ok";
  function localVerdictOf(it) {
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
    $("wc").textContent = L(`${AR_DIGITS(n)} كلمة من ${AR_DIGITS(MAX_WORDS)}`, `${n} of ${MAX_WORDS} words`) + (n > MAX_WORDS ? L(" · النص أطول من الحد، اختصره أو قسّمه", " · too long: shorten or split it") : "");
    $("wc").style.color = n > MAX_WORDS ? "var(--bad)" : "";
    $("go").disabled = n === 0 || n > MAX_WORDS;
    $("clearBtn").hidden = !$("text").value.length;
  }
  $("text").addEventListener("input", updateCount);
  $("clearBtn").onclick = () => { $("text").value = ""; updateCount(); $("text").focus(); };
  $("text").addEventListener("keydown", e => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) run(); });
  function renderSamples() {
    $("samples").innerHTML = "";
    for (const [label, text] of SAMPLES) {
      const b = document.createElement("button");
      b.className = "sample"; b.textContent = P(label); b.type = "button";
      b.onclick = () => { $("text").value = text; showTab("paste"); updateCount(); run(); };
      $("samples").appendChild(b);
    }
  }
  renderSamples();
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
  if (typeof Ocr !== "undefined") Ocr.mount($("scanRoot"), { textarea: $("text"), headers: () => headers(true), lang: LANG, onReview: () => { showTab("paste"); $("text").focus(); } });
  async function readFile(f) {
    if (!f) return;
    if (!/\.(txt|md)$/i.test(f.name) && !(f.type || "").startsWith("text/")) { alertInline(L("هذا النوع من الملفات غير مدعوم بعد. استخدم ملفًا نصيًا ‎.txt‎ أو الصق النص.", "This file type is not supported yet. Use a .txt file or paste the text.")); return; }
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
  const STEPS_L = [["استخراج الآيات والأحاديث والأحكام", "Finding verses, hadith and rulings"], ["المطابقة مع المصحف والكتب التسعة", "Matching with the Mushaf and the nine books"], ["تقييم الادعاءات بالأدلة", "Weighing claims against the evidence"], ["المسائل الفقهية في الموسوعة الكويتية", "Fiqh questions in the Kuwaiti encyclopedia"]];
  let STEPS = STEPS_L.map(P);
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
    STEPS = STEPS_L.map(P);
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
      el.innerHTML = `<span class="d">${N(i + 1)}</span><span class="t"></span>`;
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
      const sample = SAMPLES.findIndex(s => s[1] === text);
      const demo = sample >= 0 && !headers(false)["X-Access-Token"];
      const res = demo ? await fetch(`/static/demo/${sample + 1}.json`) : await fetch("/api/check", { method: "POST", headers: headers(true), body: JSON.stringify({ text, use_llm: true, use_meaning: true }) });
      const data = await res.json().catch(() => ({}));
      if (demo) data.demo = true;
      if (res.status === 401) { stopLoading(); $("inputView").hidden = false; alertInline(L("الخادم يطلب رمز دخول: أدخله من الإعدادات.", "The server needs an access code: enter it in Settings.")); openSettings(); return; }
      if (res.status === 422) throw new Error(L("النص طويل أو غير صالح للفحص. اختصره إلى 500 كلمة أو أقل.", "The text is too long or not valid. Keep it to 500 words or fewer."));
      if (!res.ok) throw new Error(L("تعذر الفحص الآن. أعد المحاولة بعد قليل.", "The check could not run right now. Try again shortly."));
      await finishLoading();
      stopLoading();
      renderReport(data);
      history.pushState({ report: true }, "", "#report");
    } catch (e) {
      stopLoading(); $("inputView").hidden = false; alertInline(e.message || L("تعذر الاتصال بالخادم. تحقق من الاتصال وأعد المحاولة.", "Could not reach the server. Check the connection and try again."));
    }
  }
  $("go").onclick = run;
  // "New review" is a button in the report's summary card (next to copy and print); the report is its only place, so there is nothing to show or hide.
  function newReview(fromHistory) { store.onReport = false; $("reportView").hidden = true; $("howView").hidden = true; $("whoView").hidden = true; $("inputView").hidden = false; if (!fromHistory) history.pushState({}, "", "#"); $("text").focus(); popIn(); }
  window.addEventListener("popstate", () => { const h = location.hash; if (h === "#report" && store.data) { showView("review", false); return; } if (!h.includes("report") && h !== "#how" && h !== "#who") newReview(true); });

  // ---------- "what we check" boxes: each opens an example of the report it produces ----------
  // Built from the same card markup as the real report, so the preview is what the reviewer will get.
  function pvCard(c) {
    return `<article class="card ${c.k === "bad" ? "k-bad-b" : ""}" style="animation: none">
      <div class="head"><div><span class="num">${N(c.n || 1)}</span><span class="chip k-${c.k}">${esc(P(c.label))}</span>${c.lvl ? `<span class="lv">${lvlTag(c.lvl)}</span>` : ""}</div><span class="cap">${esc(P(TYPE_L[c.t]))}</span></div>
      <div class="quote" dir="auto">${esc(c.quote)}</div>
      ${c.why ? `<p class="why">${esc(P(c.why))}</p>` : ""}${P(c.extra) || ""}
      ${c.next ? `<div class="next"><b>${L("الخطوة التالية", "Next step")}: ${esc(P(c.next))}</b>${c.copy ? `<div class="${c.ltr ? "tr-copy" : "q"}" dir="auto" style="font-size: ${c.ltr ? 16 : 19}px; line-height: 2">${esc(c.copy)}</div>` : ""}</div>` : ""}
    </article>`;
  }
  const PREVIEWS = {
    quran: { title: ["الآيات", "Verses"], lead: ["كل آية تُطابَق حرفًا بحرف مع نص المصحف (Tanzil). إن تغيّرت كلمة بيّنّاها، وأعطيناك الآية الصحيحة لتنسخها.", "Every verse is matched letter by letter with the Mushaf (Tanzil). If a word was changed we show which one, and give you the correct verse to copy."],
      input: "قال تعالى: «وأحل الله البيع وحرم الزنا»",
      out: () => pvCard({ k: "fix", label: ["آية بلفظ محرّف", "Verse with altered wording"], lvl: "أ", t: "quran", quote: "«وأحل الله البيع وحرم الزنا»", why: ["يختلف عن نص المصحف في سورة البقرة، الآية ٢٧٥: «الزنا» مكان «الربا».", "Differs from the Mushaf at al-Baqarah 2:275: «الزنا» (adultery) in place of «الربا» (usury)."], next: ["استبدل بالنص الصحيح", "Replace it with the correct text"], copy: "وَأَحَلَّ ٱللَّهُ ٱلْبَيْعَ وَحَرَّمَ ٱلرِّبَوٰا۟" }) },
    hadith: { title: ["الأحاديث", "Hadith"], lead: ["نبحث عن الحديث في الكتب التسعة، ونذكر كتابه ورقمه وأحكام المحدثين عليه. ما لا يوجد فيها نعرض أحكام العلماء عليه من الدرر السنية.", "We look for the hadith in the nine books and give its book, number and the scholars' gradings. For what is not there, we show the scholars' rulings on it from Dorar."],
      input: "قال رسول الله ﷺ: «اطلبوا العلم ولو في الصين». وقال ﷺ: «الراحمون يرحمهم الرحمن»",
      out: () => pvCard({ n: 1, k: "bad", label: ["لم يوجد في كتب الحديث", "Not found in the hadith books"], lvl: "ج", t: "hadith", quote: "«اطلبوا العلم ولو في الصين»", why: ["أحكام المحدثين على هذا اللفظ في الدرر السنية: ١١ ضعيف أو فيه علة، ٤ موضوع أو لا أصل له.", "Scholars' rulings on this wording in Dorar: 11 weak, 4 fabricated or baseless."], next: ["لا يُنسب إلى النبي ﷺ حتى يثبت: احذفه أو تحقق منه", "Do not attribute it to the Prophet ﷺ until it is established"] })
        + pvCard({ n: 2, k: "ok", label: ["حديث صحيح", "Authentic hadith"], lvl: "أ", t: "hadith", quote: "«الراحمون يرحمهم الرحمن»", why: ["جامع الترمذي · 1924", "Jami' al-Tirmidhi · 1924"],
          extra: [`<div class="counts"><span class="chip k-ok">صحيح · الألباني</span><span class="chip k-ok">حسن صحيح · بشار عواد معروف</span></div>`, `<div class="counts"><span class="chip k-ok">Sahih · Al-Albani</span><span class="chip k-ok">Hasan Sahih · Bashar Awad Maarouf</span></div>`] }) },
    fiqh: { title: ["الأحكام الفقهية", "Fiqh rulings"], lead: ["كل جملة فيها حكم (واجب، حرام، يجوز، بالإجماع، عند الحنفية…) نبحث عنها في الموسوعة الفقهية الكويتية، ونقرأ منها حكم كل مذهب. إن نُسب قول إلى مذهب تحققنا من النسبة، مع المجلد والصفحة.", "Every sentence that states a ruling (obligatory, forbidden, by consensus, according to the Hanafis…) is looked up in the Kuwaiti Fiqh Encyclopedia, and we read what each school holds. If the text attributes a view to a school, we check the attribution, with volume and page."],
      input: "التسمية عند الوضوء واجبة عند الحنفية.",
      out: () => pvCard({ k: "bad", label: ["نسبة القول إلى المذهب لا تطابق الموسوعة", "Attribution to the school does not match"], lvl: "ج", t: "fiqh", quote: "التسمية عند الوضوء واجبة عند الحنفية", why: ["نسب النص إلى الحنفية أن الحكم «واجب»، والذي تنقله الموسوعة الفقهية عنهم: «سنة» (ج8، ص89، مادة «بسملة»).", "The text attributes 'obligatory' to the Hanafis; the encyclopedia reports 'sunnah' for them (vol. 8, p. 89, entry 'Basmala')."],
        extra: [`<div class="schools-row"><span class="sch">الحنفية · سنة</span><span class="sch">المالكية · سنة</span><span class="sch">الشافعية · سنة</span><span class="sch">الحنابلة · واجب</span></div>`, `<div class="schools-row"><span class="sch">Hanafi · sunnah</span><span class="sch">Maliki · sunnah</span><span class="sch">Shafi'i · sunnah</span><span class="sch">Hanbali · obligatory</span></div>`],
        next: ["صحّح نسبة القول بحسب ما تنقله الموسوعة عن المذهب", "Correct the attribution to what the encyclopedia reports for that school"] }) },
    lang: { title: ["بلغات أخرى", "Other languages"], lead: ["اقتباس الآية بالإنجليزية أو الفرنسية أو الأردية أو غيرها لا يُقارن بنص كتبه أحد من ذاكرته: نبحث عنه في الترجمات المعتمدة من موسوعة القرآن الكريم المترجمة (QuranEnc)، ثم نعرض الأصل العربي من المصحف. والادعاء بلغة أخرى يُترجم إلى العربية ويُفحص كأي ادعاء.", "A verse quoted in English, French, Urdu or another language is not compared with someone's memory: we search the approved translations of QuranEnc, then show the Arabic original from the Mushaf. A claim in another language is translated into Arabic and checked like any claim."],
      input: "Allah says: \"Allah has permitted trade and forbidden adultery\" (2:275).",
      out: () => pvCard({ k: "fix", label: ["ترجمة بلفظ يخالف المعتمدة", "Differs from the approved translation"], lvl: "أ", t: "quran", quote: "\"Allah has permitted trade and forbidden adultery\"", why: ["أقرب نص: سورة البقرة، الآية ٢٧٥. كلمات ليست في الترجمة المعتمدة: adultery.", "Closest text: al-Baqarah 2:275. Words not in the approved translation: adultery."],
        next: ["انقل الترجمة المعتمدة بلفظها", "Use the approved translation word for word"], copy: "Allah has permitted trade and has forbidden interest.", ltr: true }) },
  };
  let previewKey = null;
  function openPreview(key) {
    const pv = PREVIEWS[key]; if (!pv) return;
    previewKey = key;
    $("previewTitle").textContent = P(pv.title); $("previewLead").textContent = P(pv.lead);
    $("previewInput").textContent = pv.input; $("previewOut").innerHTML = `<span class="cap pv-tag">${L("مثال توضيحي لما يظهر في التقرير", "An illustration of what the report shows")}</span>` + pv.out();
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
    if (!used.length) return L("لا توجد عندنا ترجمة معتمدة لهذه اللغة، فلم تُفحص إلا الاقتباسات العربية فيه.", "We have no approved translation for this language, so only its Arabic quotes were checked.");
    return L(`قُورنت الاقتباسات بـ${AR_DIGITS(quran)} ${quran > 2 ? "ترجمات" : "ترجمة"} معتمدة للقرآن من موسوعة القرآن الكريم المترجمة (QuranEnc)${hadith ? " وبالترجمة الإنجليزية لسبعة من كتب الحديث" : ""}، ثم بأصلها العربي. اسم الترجمة يظهر في تفاصيل كل نتيجة.`,
      `Quotes were compared with ${quran} approved Quran translation${quran > 1 ? "s" : ""} from QuranEnc${hadith ? " and the English translation of seven hadith books" : ""}, then with their Arabic original. Each result names the translation in its details.`);
  }
  const LANG_AR = { en: ["بالإنجليزية", "in English"], fr: ["بالفرنسية", "in French"], ur: ["بالأردية", "in Urdu"], id: ["بالإندونيسية", "in Indonesian"], tr: ["بالتركية", "in Turkish"], es: ["بالإسبانية", "in Spanish"], other: ["بلغة أخرى", "in another language"] };
  const TYPES = {
    khutbah: { label: "خطبة", the: "هذه الخطبة", f: true, act: "للإلقاء", tip: "صحّح المواضع المظللة قبل صعود المنبر؛ ما يُقال على المنبر يُنقل عن الخطيب.",
      en: { label: "Khutbah", the: "This khutbah", act: "to deliver", tip: "Fix the highlighted places before you stand at the minbar: what is said there is repeated in the khateeb's name." } },
    post: { label: "منشور", the: "هذا المنشور", act: "للنشر", tip: "المنشور يُعاد نشره بلا ضابط؛ تصحيحه قبل النشر أيسر من تتبّعه بعده.",
      en: { label: "Post", the: "This post", act: "to publish", tip: "A post is reshared without limit: correcting it before publishing is easier than chasing it afterwards." } },
    article: { label: "مقال", the: "هذا المقال", act: "للنشر", en: { label: "Article", the: "This article", act: "to publish" } },
    lesson: { label: "درس", the: "هذا الدرس", act: "للإلقاء", en: { label: "Lesson", the: "This lesson", act: "to deliver" } },
    question: { label: "سؤال", the: "هذا النص", act: "للنشر", tip: "إن كان سؤالًا عن حالة بعينها فجوابه عند عالم يسمع تفاصيلها.",
      en: { label: "Question", the: "This text", act: "to publish", tip: "If it asks about a particular case, the answer needs a scholar who hears its details." } },
    text: { label: "نص", the: "هذا النص", act: "للنشر", en: { label: "Text", the: "This text", act: "to publish" } },
  };
  const typeOf = k => { const t = TYPES[k] || TYPES.text; return LANG === "en" ? Object.assign({ f: false }, t.en) : t; };
  function headline(needs, counts) {
    const d = store.data;
    if (!needs && d && !d.review_complete) return L("المراجعة محدودة: لا يمكن تأكيد جاهزية النص للنشر", "Limited review: publishing readiness is unconfirmed");
    const t = typeOf(store.type);
    if (LANG === "en") {
      if (needs) return `${t.the} is not ready ${t.act}: ${needs} ${needs === 1 ? "place needs" : "places need"} changes`;
      return `No changes found in the completed review of ${t.the.toLowerCase()}`;
    }
    const ready = t.f ? "جاهزة" : "جاهز", inIt = t.f ? "فيها" : "فيه";
    if (needs) return `${t.the} غير ${ready} ${t.act}: ${needs === 1 ? "موضع واحد يحتاج" : needs === 2 ? "موضعان يحتاجان" : needs <= 10 ? `${AR_DIGITS(needs)} مواضع تحتاج` : `${AR_DIGITS(needs)} موضعًا يحتاج`} تعديلًا`;
    return `لم نجد مواضع تحتاج تعديلًا في المراجعة المكتملة لـ${t.the}`;
  }
  function typeLine(data) {
    const cues = (data.content_type_cues || []).map(c => `«${esc(c)}»`).join("، ");
    return `<div class="typeline no-print"><label for="typeSel" class="cap">${L("نوع النص:", "Kind of text:")}</label>
      <select id="typeSel">${Object.keys(TYPES).map(k => `<option value="${k}" ${k === store.type ? "selected" : ""}>${typeOf(k).label}</option>`).join("")}</select>
      ${cues ? `<span class="cap">${L("عرفناه من:", "Recognised from:")} ${cues}</span>` : ""}</div>`;
  }
  function renderReport(data) {
    if (store.data !== data) { store.manualDraft = undefined; store.fixes = {}; store.badge = null; }
    store.data = data; store.onReport = true;
    store.type = data.content_type || "text";
    const items = (data.items || []).filter(it => !it.fragment && !(it.kind === "claim" && it.result && it.result.outcome === "out_of_scope"));
    // Numbers follow the order of the text, so the marks read ١، ٢، ٣ down the page; the cards are ordered by what matters most.
    store.entries = items.map((it, i) => ({ it, v: verdictOf(it), i })).sort((a, b) => a.it.start - b.it.start);
    store.entries.forEach((e, n) => { e.n = n + 1; });
    store.entries.sort((a, b) => RANK[a.v.k] - RANK[b.v.k] || a.n - b.n);
    const counts = {}; store.entries.forEach(e => { counts[e.v.k] = (counts[e.v.k] || 0) + 1; });
    const needs = store.entries.filter(needsAction).length;
    store.filter = store.entries.length > 6 ? "attention" : "all";

    const llmOff = !data.llm || !data.llm.used;
    const head = `<section class="summary" aria-label="${L("ملخص التقرير", "Report summary")}">
      <div class="row-between">
        <div style="display: flex; flex-direction: column; gap: 2px">
          <h1>${L("تقرير المراجعة", "Review report")}</h1>
          <span class="cap">${L(`${AR_DIGITS(data.word_count)} كلمة · ${AR_DIGITS(store.entries.length)} من النصوص والأحكام · ${AR_DIGITS(data.commentary_sentences || 0)} جملة تعليق لا تحتاج تحققًا`, `${data.word_count} words · ${store.entries.length} texts and rulings · ${data.commentary_sentences || 0} commentary sentences with nothing to check`)}</span>
        </div>
        <div class="actions no-print">
          <button class="btn" id="shareBtn" title="${L("الرابط يتضمن النص كاملًا؛ يستطيع كل من يملكه قراءته", "The link contains the full text; anyone with it can read it")}">${L("مشاركة التقرير", "Share the report")}</button>
          <button class="btn" id="copySummary">${L("نسخ ملخص التقرير", "Copy summary")}</button>
          <button class="btn" id="printBtn">${L("طباعة أو حفظ PDF", "Print or save PDF")}</button>
          <button class="btn primary" id="newBtn">${L("مراجعة نص جديد", "Review another text")}</button>
        </div>
      </div>
      ${data.demo ? `<div class="notice" role="status">${L("عرض توضيحي محفوظ لأحد الأمثلة بالمطابقة المباشرة. ليست مراجعة حية؛ لا يمنح شارة. لمراجعة نصك استخدم رمز الدخول.", "Saved direct-matching sample demo. This is not a live review and cannot earn a badge. Reviewing your own text requires an access code.")}</div>` : ""}
      ${store.entries.length ? `<p class="headline" id="headline" tabindex="-1">${headline(needs, counts)}</p>${typeLine(data)}${needs && typeOf(store.type).tip ? `<p class="cap type-tip" id="typeTip">${typeOf(store.type).tip}</p>` : `<p class="cap type-tip" id="typeTip" hidden></p>`}<div class="seg" aria-hidden="true">${["bad", "fix", "khl", "ref", "neu", "ok"].filter(k => counts[k]).map(k => `<i class="s-${k}" style="flex: ${counts[k]}"></i>`).join("")}</div>
      <div class="counts">
        ${["bad", "fix", "khl", "ref", "neu", "ok"].filter(k => counts[k]).map(k => `<span class="chip k-${k}">${N(counts[k])} ${P(K_LABEL[k])}</span>`).join("")}</div>` : ""}
      ${data.language && data.language !== "ar" ? `<div class="notice" role="status">${L("النص", "The text is")} ${esc(P(LANG_AR[data.language] || LANG_AR.other))}: ${trNote(data)}${llmOff ? L(" ترجمة الادعاءات غير المقتبسة إلى العربية تحتاج الذكاء الاصطناعي، وهو غير متاح الآن.", " Translating unquoted claims into Arabic needs the AI, which is not available right now.") : ""}</div>` : ""}
      ${llmOff && !data.demo && !(data.language && data.language !== "ar") ? `<div class="notice" role="status">${L("جرت المراجعة بالمطابقة المباشرة فقط، فقد لا تظهر الادعاءات غير المقتبسة.", "This review used direct matching only; unquoted claims may not appear.")}${data.llm && data.llm.error ? `<details class="llm-why"><summary>${L("لماذا لم يعمل الذكاء الاصطناعي؟", "Why did the AI not run?")}</summary><code dir="ltr">${esc(String(data.llm.error).slice(0, 300))}</code></details>` : ""}</div>` : ""}
      ${data.skipped_claims ? `<div class="notice" role="status">${L(`لم يُفحص ${AR_DIGITS(data.skipped_claims)} من الادعاءات. قسّم النص وأعد الفحص.`, `${data.skipped_claims} claims were not checked. Split the text and re-check.`)}</div>` : ""}
      ${data.llm && data.llm.used && data.llm.error ? `<div class="notice" role="status">${L("تعذر إكمال بعض خطوات المراجعة؛ لا يمكن منح شارة.", "Some review steps failed; a badge cannot be issued.")}</div>` : ""}
      ${data.badge_unavailable === "signing_unavailable" ? `<div class="notice" role="status">${L("توقيع الشارات غير مهيأ على الخادم.", "Badge signing is not configured on the server.")}</div>` : ""}
      ${data.truncated ? `<div class="notice">${L("النص أطول من الحد، فُحص الجزء الأول منه فقط.", "The text is over the limit: only its first part was checked.")}</div>` : ""}
    </section>`;

    let body;
    if (!store.entries.length) {
      body = `<section class="empty"><b style="font-size: 20px">${L("لم نجد آيات أو أحاديث أو أحكامًا شرعية نتحقق منها", "No verses, hadith or rulings to check were found")}</b>
        <span class="cap" style="max-width: 520px; line-height: 1.8">${L("إن كان في النص حديث أو آية بغير علامات تنصيص فضعه بين «» وأعد الفحص.", "If the text quotes a hadith or verse without quotation marks, put it in quotes and check again.")}</span>
        <button class="btn primary" id="editBtn">${L("تعديل النص", "Edit the text")}</button></section>`;
    } else {
      body = `<div class="cols">
        <section class="doc" aria-label="${L("النص كما أُدخل", "The text as entered")}">
          <div class="row-between"><b class="cap" style="font-size: 14px">${L("النص كما أُدخل", "The text as entered")}</b><span class="cap">${L("اضغط موضعًا مظلَّلًا لفتح نتيجته", "Click a highlighted passage to see its result")}</span></div>
          <p dir="${data.language && data.language !== "ar" && data.language !== "ur" ? "ltr" : "rtl"}">${markedText(data.original_text)}</p>
        </section>
        <section class="list" aria-label="${L("النتائج", "Results")}">
          <div class="row-between"><b class="cap" style="font-size: 14px">${L("النتائج، الأهم أولًا", "Results, most important first")}</b>
            <div class="filters" role="group" aria-label="${L("تصفية النتائج", "Filter results")}">
              <button class="btn small" data-f="attention" aria-pressed="${store.filter === "attention"}">${L("تحتاج إجراء", "Need action")} ${N(store.entries.filter(needsAction).length)}</button>
              <button class="btn small" data-f="all" aria-pressed="${store.filter === "all"}">${L("الكل", "All")} ${N(store.entries.length)}</button>
            </div></div>
          ${progressHtml()}
          <div id="cards" style="display: flex; flex-direction: column; gap: 12px">${store.entries.map(cardHtml).join("")}</div>
        </section>
      </div>`;
    }
    const rv = $("reportView");
    rv.innerHTML = head + body + `<p class="cap" style="line-height: 1.8">${L("هذا التقرير يبيّن مواضع النصوص في المصادر وأحكام العلماء كما نقلتها، وليس فتوى ولا ترجيحًا. ما كتبه الذكاء الاصطناعي معلَّم بذلك.", "This report shows where texts are found in the sources and what scholars' rulings they record. It is not a fatwa and prefers no opinion. Anything the AI wrote is labelled.")}</p>`;
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
      const tip = $("typeTip"), tp = typeOf(store.type).tip;
      tip.hidden = !(needs && tp); tip.textContent = tp || "";
    };
    const hl = $("headline"); if (hl) hl.focus({ preventScroll: true });  // keyboard and screen-reader users land on the verdict
    const db = $("draftBox"); if (db) db.addEventListener("input", () => { db.dataset.edited = "1"; });
    // A re-check of the corrected text, or a badge link: the badge is given only when nothing needs changing.
    // The badge comes from the server, signed, and only when no unresolved findings remained in this automated review (services/badge.py).
    if (data.badge) { store.verifiedText = data.original_text; showBadge(data); }
    else if (store.recheck && needs) rv.insertAdjacentHTML("afterbegin", `<div class="notice" role="status">${L(`بقي ما يحتاج مراجعة (${AR_DIGITS(needs)}). عالجه ثم أعد الفحص.`, `Findings still need review (${needs}). Handle them, then re-check.`)}</div>`);
    store.recheck = false;
    dorarSummaries();
  }

  function markedText(text) {
    const spans = store.entries.map(e => ({ s: e.it.start, e: e.it.end, en: e })).sort((a, b) => a.s - b.s);
    let out = "", pos = 0;
    for (const sp of spans) {
      if (sp.s < pos) continue;
      out += esc(text.slice(pos, sp.s));
      // The number sits inside the mark, so it never ends up alone at the end of the previous line.
      out += `<button class="mk k-${sp.en.v.k}" data-goto="${sp.en.n}" aria-label="${L("النتيجة", "Result")} ${sp.en.n}: ${esc(sp.en.v.label)}"><span class="num" aria-hidden="true">${N(sp.en.n)}</span>${esc(text.slice(sp.s, sp.e))}</button>`;
      pos = sp.e;
    }
    return out + esc(text.slice(pos));
  }

  function cardHtml(e) {
    const v = e.v, it = e.it, lvl = it.content_level;
    const quoteText = isQuoteish(v) ? shownQuote(it.text) : it.text;
    const isScripture = isQuoteish(v);
    return `<article class="card ${v.k === "bad" ? "k-bad-b" : ""}" id="card-${e.n}" data-k="${v.k}" style="--i: ${e.n}">
      <div class="head">
        <div><span class="num" style="vertical-align: baseline">${N(e.n)}</span><span class="chip k-${v.k}">${esc(v.label)}</span>${lvl ? `<span class="lv" title="${esc(P(LEVEL_TITLE[lvl]) || "")}">${lvlTag(lvl)}</span>` : ""}</div>
        <span class="cap">${esc(P(TYPE_L[v.t]))}</span>
      </div>
      <div class="${isScripture ? "quote" : ""}" dir="auto" style="${isScripture ? "" : "font-size: 16px; line-height: 1.8"}">${esc(quoteText)}</div>
      ${it.translated_ar ? `<p class="cap tr-ar">${L("ترجمة آلية بُحث بها في المصادر", "Machine translation used to search the sources")} <span class="gen">${L("مولَّد بالذكاء الاصطناعي", "AI-generated")}</span>: <span dir="rtl">${esc(it.translated_ar)}</span></p>` : ""}
      ${v.why ? `<p class="why">${esc(v.why)}</p>` : ""}
      ${v.fiqh ? schoolsRow(v.fiqh) : ""}
      ${v.next ? `<div class="next"><b>${L("الخطوة التالية", "Next step")}: ${esc(v.next)}</b>${v.copy ? `<div class="${v.copyLtr ? "tr-copy" : "q"}" dir="auto" style="font-size: ${v.copyLtr ? 16 : 19}px; line-height: 2">${esc(v.copy)}</div>` : ""}</div>` : ""}
      ${fixBar(e)}
      <div class="actions no-print">
        <button class="btn small" data-open="${e.n}" aria-expanded="false">${L("التفاصيل والمصادر", "Details and sources")}</button>
        ${v.copy ? `<button class="btn small" data-copy="${e.n}">${L("نسخ النص الصحيح", "Copy the correct text")}</button>` : ""}
      </div>
      <div class="more" id="more-${e.n}" hidden></div>
    </article>`;
  }

  // ---------- applying the fixes: a corrected draft, a re-check, and a badge only when the re-check is clean ----------
  // A fix is offered only where it can be made safely from the sources: a verse is replaced by the Mushaf's text, an
  // approved translation by its official wording, an unfounded hadith is removed, a claimed consensus or a wrong school
  // becomes the schools the encyclopedia names. Anything else is the reviewer's to handle ("I handled it myself").
  const CONSENSUS_RE = /\s*(?:بالإجماع|بالاجماع|إجماعًا|إجماعا|بلا خلاف|باتفاق العلماء|باتفاق الفقهاء)|(?:أجمع|اتفق)\s+(?:العلماء|الفقهاء|المسلمون|الأمة)\s+على\s+(?:أن\s+)?/g;
  const RULING_JS = [["غير واجب", /لا يجب|لا تجب|ليس بواجب|غير واجب/], ["واجب", /واجب|يجب|تجب|فرض/], ["سنة", /سنة|مستحب|يستحب|مسنون/], ["حرام", /حرام|يحرم|محرم|لا يجوز/], ["مكروه", /مكروه|يكره/], ["جائز", /يجوز|جائز|مباح/], ["لا ينقض", /لا ينقض/], ["ينقض", /ينقض/]];
  const rulingIn = t => { for (const [k, re] of RULING_JS) if (re.test(t)) return k; return null; };
  const SAME_R = { "لا يجوز": "حرام", "حرام": "حرام" };
  const joinAr = xs => xs.length < 2 ? (xs[0] || "") : xs.slice(0, -1).join("، ") + " و" + xs[xs.length - 1];
  // The words of the verse that the quote was reaching for ("وأحل الله البيع وحرم الزنا" -> "وَأَحَلَّ ٱللَّهُ ٱلْبَيْعَ وَحَرَّمَ ٱلرِّبَوٰا۟"),
  // not the whole verse, when most of the quote's words line up with a stretch of it.
  function versePart(verse, quote) {
    const vw = verse.split(/\s+/).filter(w => normAr(w).trim()), qw = normAr(quote).split(/\s+/).filter(Boolean), n = qw.length;
    if (!n || vw.length <= n + 2) return verse;
    let best = -1, at = 0;
    for (let i = 0; i + n <= vw.length; i++) {
      let sc = 0; for (let j = 0; j < n; j++) if (normAr(vw[i + j]).trim() === qw[j]) sc++;
      if (sc > best) { best = sc; at = i; }
    }
    return best * 2 >= n ? vw.slice(at, at + n).join(" ") : verse;
  }
  function fixPlan(e) {
    if (store.manualDraft !== undefined) return null;
    const plan = sourceFixPlan(e);
    if (!plan || !plan.find) return null;
    const original = store.data.original_text;
    // Anchor to this finding, never the first identical wording elsewhere.
    let at = original.indexOf(plan.find, e.it.start);
    if (at < 0 || at >= e.it.end) at = original.lastIndexOf(plan.find, e.it.start);
    if (at < 0 || at + plan.find.length < e.it.start || at > e.it.end) return null;
    return Object.assign(plan, { start: at, end: at + plan.find.length });
  }
  function sourceFixPlan(e) {
    const v = e.v, it = e.it, sg = v.seg, src = store.data.original_text.slice(it.start, it.end);
    if (!needsAction(e)) return null;
    if (sg && sg.translation && (sg.differences || []).some(d => /^the reference given/.test(d))) return null; // correct the reference manually too
    if (sg && sg.translation && sg.status === "semantic_variant") {
      const q = quoteOf(src); return { find: q, to: sg.translation.text.replace(/^\d+\.\s*/, ""), label: L("ضع الترجمة المعتمدة", "Insert the approved translation") };
    }
    if (sg && sg.status === "semantic_variant" && sg.source && isQuran(sg.source)) {
      const q = shownQuote(src);
      return { find: q, to: `﴿${versePart(sg.source.matched_text, quoteOf(q))}﴾`, label: L("ضع نص المصحف", "Insert the Mushaf text") };
    }
    if (v.t === "hadith" && v.k === "bad") {
      // remove the quote with the words that attribute it ("وقد قال رسول الله ﷺ:"), not the sentence around it
      const q = shownQuote(src), k = src.indexOf(q), lead = k < 0 ? "" : (src.slice(0, k).match(/[،,]?\s*(?:و\s*)?(?:قد\s+)?(?:قال|يقول|ورد عن|روي عن|جاء عن|عن)\s*(?:رسول الله|النبي|الرسول)?\s*(?:ﷺ|صلى الله عليه وسلم)?\s*:?\s*$/) || [""])[0];
      return { find: lead + q, to: "", label: L("احذف الحديث من النص", "Remove the hadith from the text") };
    }
    const f = v.fiqh;
    if (f && f.status && it.kind === "claim") {
      if (f.matched_by !== "model" || f.error || f.status === "partly_disputed") return null; // keyword candidates need human review
      // "أجمع العلماء على أن" often sits just before the claim's span: it goes with the fix.
      const pre = (store.data.original_text.slice(Math.max(0, it.start - 40), it.start).match(/(?:أجمع|اتفق)\s+(?:العلماء|الفقهاء|المسلمون|الأمة)\s+على\s+(?:أن\s+)?$/) || [""])[0];
      const claim = src.replace(/[.،؛]+\s*$/, ""), whole = pre + src;
      const after = store.data.original_text.slice(it.end), tail = src.slice(claim.length);
      const want = rulingIn(claim.replace(CONSENSUS_RE, " "));
      const holders = (f.schools || []).filter(x => x.schools[0] !== "الجمهور" && want && (x.ruling === want || SAME_R[x.ruling] === SAME_R[want] && SAME_R[want])).map(x => x.schools[0]);
      const jumhur = (f.schools || []).find(x => x.schools[0] === "الجمهور" && x.ruling === want);
      const who = holders.length ? joinAr(holders) : jumhur ? "الجمهور" : "";
      if (f.status === "school_differs" && f.attribution) {
        if (!who) return null;
        return { find: whole, to: claim.replace(f.attribution.school, who) + tail, label: L(`انسب القول إلى ${who}`, `Attribute it to the ${who}`) };
      }
      if (f.status === "consensus_claim_disputed" || f.status === "stated_as_certain_disputed" || (f.status === "partly_disputed" && who)) {
        const bare = claim.replace(CONSENSUS_RE, " ").replace(/\s+/g, " ").trim();
        return { find: whole, to: `${bare}${who ? ` عند ${who}، وفي المسألة خلاف` : "، على خلاف بين الفقهاء"}${tail || (/^\s*[.،؛!؟?:]/.test(after) ? "" : ".")}`, label: L(who ? `انسب القول إلى ${who} واذكر الخلاف` : "اذكر الخلاف", who ? "Attribute it to its schools and note the disagreement" : "Note the disagreement") };
      }
    }
    return null;
  }
  function fixBar(e) {
    if (!needsAction(e)) return "";
    const st = (store.fixes || {})[e.n], plan = fixPlan(e);
    if (st) return `<div class="fixbar done no-print"><span>✓ ${st === "applied" ? L("طُبّق التصحيح في النص المصحح", "Applied to the corrected text") : L("عالجتَه بنفسك", "Handled by you")}</span>${store.manualDraft === undefined ? `<button class="link" data-unfix="${e.n}">${L("تراجع", "Undo")}</button>` : ""}</div>`;
    return `<div class="fixbar no-print">${plan ? `<button class="btn small primary" data-fix="${e.n}">${esc(plan.label)}</button><span class="cap fix-prev" dir="auto">${plan.to ? L("سيصبح:", "Becomes:") + " " + esc(plan.to.length > 90 ? plan.to.slice(0, 90) + "…" : plan.to) : L("يُحذف من النص", "Removed from the text")}</span>` : ""}
      <button class="btn small" data-manual="${e.n}">${L("عالجتُه بنفسي", "I handled it myself")}</button></div>`;
  }
  function draftNow() {
    if (store.manualDraft !== undefined) return store.manualDraft;
    let t = store.data.original_text, boundary = t.length;
    const plans = store.entries.filter(e => store.fixes[e.n] === "applied").map(fixPlan).filter(Boolean).sort((a, b) => b.start - a.start);
    for (const plan of plans) {
      if (plan.end > boundary) continue;
      t = t.slice(0, plan.start) + plan.to + t.slice(plan.end);
      boundary = plan.start;
    }
    return t.replace(/[ \t]{2,}/g, " ").replace(/\s+([.،])/g, "$1").replace(/([،.!؟?])(?:\s*\.)+/g, (m, a) => a === "،" ? "." : a).replace(/^[\s.،]+/, "").trim();
  }
  function progressHtml() {
    const todo = store.entries.filter(needsAction), done = todo.filter(e => store.fixes[e.n]).length;
    if (!todo.length) return "";
    const all = done === todo.length || store.manualDraft !== undefined, left = todo.length - done, auto = todo.filter(e => !store.fixes[e.n] && fixPlan(e)).length;
    return `<section class="fixpanel no-print" id="fixpanel" aria-label="${L("تطبيق التصحيحات", "Applying the fixes")}">
      <div class="row-between"><b>${L("طبّق التصحيحات واحصل على شارة مَنبَع", "Apply the fixes and earn the Manba badge")}</b><span class="cap">${L(`${AR_DIGITS(done)} من ${AR_DIGITS(todo.length)}`, `${done} of ${todo.length}`)}</span></div>
      <div class="fixprog"><i style="width: ${Math.round(100 * done / todo.length)}%"></i></div>
      <details ${done ? "open" : ""}><summary class="cap" style="cursor: pointer">${L("النص المصحح (يمكنك تحريره)", "The corrected text (you can edit it)")}</summary>
        <textarea id="draftBox" dir="auto">${esc(draftNow())}</textarea></details>
      <div class="actions">${auto ? `<button class="btn primary" id="applyAll">${auto === left ? L("طبّق كل التصحيحات وأعد الفحص", "Apply every fix and re-check") : L(`طبّق التصحيحات المقترحة (${AR_DIGITS(auto)})`, `Apply the suggested fixes (${auto})`)}</button>` : ""}
        <button class="btn ${all ? "primary" : ""}" id="recheckBtn" ${all ? "" : "disabled"}>${L("أعد الفحص لنيل الشارة", "Re-check to earn the badge")}</button>
        <button class="btn" id="copyDraft">${L("انسخ النص المصحح", "Copy the corrected text")}</button>
        <span class="cap">${store.manualDraft !== undefined ? L("تعديلاتك محفوظة. أعد الفحص للتحقق منها.", "Your edits are preserved. Re-check to validate them.") : all ? L("كل المواضع عولجت: أعد الفحص للتأكد.", "Every place is handled: re-check to confirm.") : auto < left ? L(`${AR_DIGITS(left - auto)} من المواضع لا تصحيح آليًا لها: عدّلها في النص المصحح ثم اضغط «عالجتُه بنفسي».`, `${left - auto} of the places have no automatic fix: edit them in the corrected text, then press "I handled it myself".`) : L("الشارة تُمنح فقط إذا جاء الفحص الجديد نظيفًا.", "The badge is given only if the new check comes back clean.")}</span></div>
    </section>`;
  }
  // Every fix the sources give, in one go; when nothing is left to handle by hand, the corrected text is re-checked at once.
  function applyAll() {
    if (store.manualDraft !== undefined) return;
    store.entries.forEach(e => { if (needsAction(e) && !store.fixes[e.n] && fixPlan(e)) store.fixes[e.n] = "applied"; });
    const box = $("draftBox"); if (box) delete box.dataset.edited;
    refreshFixes();
    const left = store.entries.filter(e => needsAction(e) && !store.fixes[e.n]);
    if (!left.length) { $("recheckBtn").click(); return; }
    const c = $("card-" + left[0].n); if (c) { c.scrollIntoView({ behavior: "smooth", block: "center" }); c.classList.add("flash"); setTimeout(() => c.classList.remove("flash"), 1600); }
  }
  function refreshFixes() {
    const box = $("draftBox"), edited = box && box.dataset.edited === "1" ? box.value : null;
    const panel = $("fixpanel"); if (panel) panel.outerHTML = progressHtml();
    if (edited !== null && $("draftBox")) { $("draftBox").value = edited; $("draftBox").dataset.edited = "1"; }
    store.entries.forEach(e => { const c = $("card-" + e.n); if (!c) return; const fb = c.querySelector(".fixbar"); if (fb) fb.outerHTML = fixBar(e); c.classList.toggle("is-fixed", !!store.fixes[e.n]); });
  }
  // Share links carry the text itself (compressed), so the report is rebuilt from the sources when the link is opened.
  async function packText(text) {
    const bytes = new TextEncoder().encode(text);
    if (!window.CompressionStream) return "u" + btoa(unescape(encodeURIComponent(text))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
    const z = await new Response(new Blob([bytes]).stream().pipeThrough(new CompressionStream("deflate-raw"))).arrayBuffer();
    let bin = ""; new Uint8Array(z).forEach(b => { bin += String.fromCharCode(b); });
    return "z" + btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }
  async function unpackText(packed) {
    const b64 = packed.slice(1).replace(/-/g, "+").replace(/_/g, "/"), bin = atob(b64), bytes = Uint8Array.from(bin, c => c.charCodeAt(0));
    if (packed[0] === "u") return decodeURIComponent(escape(bin));
    return await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream("deflate-raw"))).text();
  }
  async function shareLink(text) { return `${location.origin}/#s=${await packText(text)}`; }
  // The badge's own link: the serial, and the reviewed text so the verifier can confirm it is the same text.
  async function badgeLink(code, text) { return `${location.origin}/#v=${code}${text ? "&t=" + await packText(text) : ""}`; }

  // The badge is the Manba mark itself: the eight-pointed star, with the statement and the serial written inside it.
  function badgeSvg(code, date) {
    const star = (r, attrs) => `<rect x="${130 - r}" y="${130 - r}" width="${2 * r}" height="${2 * r}" rx="10" ${attrs}/><rect x="${130 - r}" y="${130 - r}" width="${2 * r}" height="${2 * r}" rx="10" transform="rotate(45 130 130)" ${attrs}/>`;
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="-12 -12 284 284" width="284" height="284" direction="ltr" style="direction: ltr" role="img" aria-label="${esc(L(`تم التحقق منه باستخدام مَنبَع، الرقم التسلسلي ${code}`, `Verified with Manba, serial ${code}`))}">
      ${star(96, 'fill="#0B6E5C"')}
      ${star(88, 'fill="none" stroke="#E3F5EC" stroke-opacity=".55" stroke-width="1.5"')}
      <circle cx="130" cy="130" r="84" fill="#0E7F6A"/>
      <circle cx="130" cy="130" r="78" fill="none" stroke="#E3F5EC" stroke-opacity=".5" stroke-width="1"/>
      <text x="130" y="88" text-anchor="middle" font-family="IBM Plex Sans Arabic, Tahoma, sans-serif" font-size="12.5" fill="#E3F5EC">تم التحقق منه باستخدام</text>
      <text x="130" y="127" text-anchor="middle" font-family="Amiri, 'Traditional Arabic', serif" font-size="34" font-weight="700" fill="#FFFFFF">مَنبَع</text>
      <text x="130" y="159" text-anchor="middle" font-family="IBM Plex Sans, Arial, sans-serif" font-size="10" letter-spacing="1.2" fill="#E3F5EC">VERIFIED WITH MANBA</text>
      <line x1="88" y1="167" x2="172" y2="167" stroke="#E3F5EC" stroke-opacity=".45"/>
      ${(code.match(/.{1,20}/g) || []).map((line, i) => `<text x="130" y="${175 + i * 9}" text-anchor="middle" font-family="Menlo, Consolas, monospace" font-size="6.5" fill="#FFFFFF">${esc(line)}</text>`).join("")}
      <text x="130" y="218" text-anchor="middle" font-family="Menlo, Consolas, monospace" font-size="9" fill="#E3F5EC">${esc(date)}</text></svg>`;
  }
  window.ManbaBadge = badgeSvg;  // the How page's tour shows the same seal
  async function showBadge(data) {
    const b = data.badge, text = data.original_text;
    store.badge = Object.assign({}, b, { link: await badgeLink(b.code, text), svg: badgeSvg(b.code, b.date) });
    const rv = $("reportView");
    rv.insertAdjacentHTML("afterbegin", `<section class="badgebox" id="badgebox" role="status">
      <div class="seal">${store.badge.svg}</div>
      <div class="badge-txt"><b>${L("نال النص شارة مَنبَع", "The text earned the Manba badge")}</b>
        <div class="serial"><span class="cap">${L("الرقم التسلسلي", "Serial")}</span><code dir="ltr">${esc(b.code)}</code></div>
        <span class="cap">${L(`فُحص النص المصحح من جديد بتاريخ ${b.date} فلم تظهر مواضع غير محسومة في هذه المراجعة الآلية (${AR_DIGITS(b.items)} من النصوص والأحكام). الرقم موقَّع من خادم مَنبَع: يمكن لأي أحد التحقق منه في صفحة «تحقق من شارة»، ومعه النص يتأكد أنه هو النص نفسه.`, `The corrected text was checked again on ${b.date} and no unresolved findings remained in this automated review (${b.items} texts and rulings). The serial is signed by the Manba server: anyone can check it on the "Verify a badge" page, and with the text, confirm it is the very same text.`)}${b.mode === "matching" ? L(" هذه المراجعة جرت بالمطابقة المباشرة دون الذكاء الاصطناعي.", " This review used direct matching only, without the AI.") : ""}</span>
        <div class="actions"><button class="btn primary" id="dlBadge">${L("نزّل الشارة", "Download the badge")}</button><button class="btn" id="copyBadgeLink">${L("انسخ رابط التحقق", "Copy the verification link")}</button><button class="btn" id="copySerial">${L("انسخ الرقم", "Copy the serial")}</button><button class="btn" id="copyDraft2">${L("انسخ النص المصحح", "Copy the corrected text")}</button></div></div>
    </section>`);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  // ---------- verifying a badge: the serial's signature, and (optionally) that the text is the one reviewed ----------
  const VERIFY_WHY = { legacy_serial: ["هذه شارة بالإصدار القديم؛ أعد مراجعة النص للحصول على شارة جديدة.", "This badge uses the retired format. Re-check the text for a new badge."],
    signing_unavailable: ["توقيع الشارات غير مهيأ على الخادم؛ تعذر التحقق.", "Badge signing is not configured; verification is unavailable."], malformed: ["هذا ليس رقمًا تسلسليًا لمَنبَع. انسخ رمز MNB2 كاملًا من الشارة.", "This is not a Manba serial. Copy the complete MNB2 code from the badge."],
    not_issued: ["لم يصدر هذا الرقم عن مَنبَع: التوقيع لا يطابق.", "This serial was not issued by Manba: the signature does not match."] };
  async function verifyBadge() {
    const code = $("vCode").value.trim(), text = $("vText").value, out = $("vOut");
    if (!code) { $("vCode").focus(); return; }
    out.hidden = false; out.className = "vout"; out.textContent = L("نتحقق…", "Checking…");
    try {
      const res = await fetch("/api/badge/verify", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code, text: text.length ? text : null }) });
      const r = await res.json();
      if (!r.valid) { out.className = "vout bad"; out.innerHTML = `<b>${L("رقم غير صالح", "Not a valid serial")}</b><span>${esc(P(VERIFY_WHY[r.reason] || VERIFY_WHY.not_issued))}</span>`; return; }
      const mode = r.mode === "full" ? L("مراجعة كاملة: الاقتباسات والادعاءات والأحكام، بمساعدة الذكاء الاصطناعي، والحكم للمصادر", "Full review: quotes, claims and rulings, with the AI's help; the sources decide")
        : L("مراجعة بالمطابقة المباشرة فقط (دون الذكاء الاصطناعي)", "Direct matching only (without the AI)");
      const match = r.text_matches === true ? `<span class="ok">✓ ${L("النص المرفق هو النص نفسه الذي رُوجع، حرفًا بحرف.", "The text given is the very text that was reviewed, letter for letter.")}</span>`
        : r.text_matches === false ? `<span class="badtxt">✕ ${L("النص المرفق ليس النص الذي رُوجع: تغيّر فيه شيء بعد المراجعة.", "The text given is not the one reviewed: something changed after the review.")}</span>`
        : `<span class="cap">${L("أرفق النص للتأكد من أنه النص نفسه الذي رُوجع.", "Add the text to confirm it is the very text that was reviewed.")}</span>`;
      out.className = "vout " + (r.text_matches === false ? "warn" : "good");
      out.innerHTML = `<div class="seal">${badgeSvg(r.code, r.date)}</div><div><b>${L("رقم صادر عن مَنبَع", "Issued by Manba")}</b>
        <span>${L(`رُوجع بتاريخ ${r.date}، ولم تظهر مواضع غير محسومة في تلك المراجعة الآلية.`, `Reviewed on ${r.date}, with no unresolved findings in that automated review.`)}</span><span class="cap">${mode}</span>${match}
        ${text ? `<button class="btn small" id="vRerun" type="button">${L("أعد مراجعة النص الآن", "Review the text again now")}</button>` : ""}</div>`;
    } catch (e) { out.className = "vout bad"; out.textContent = L("تعذر الاتصال بالخادم.", "Could not reach the server."); }
  }

  // ---------- the printable report (PDF) ----------
  const K_EXPLAIN = { bad: ["لا يُنشر كما هو: لم يثبت، أو نُسب إلى غير قائله", "cannot be published as it is: not established, or misattributed"],
    fix: ["لفظ محرّف أو إحالة خطأ أو درجة غير مبيّنة", "altered wording, a wrong reference, or no grading"],
    khl: ["تُنسب الأقوال إلى أصحابها ولا يُقطع بأحدها", "attribute the views to their holders, state none as settled"],
    ref: ["يُحال إلى مختص", "refer to a scholar"], neu: ["لم نجد ما نحكم به: تحقق منه", "nothing found to judge it by: verify it"], ok: ["ثابت في مصدره كما نُقل", "found in its source as quoted"] };
  function printableReport() {
    const data = store.data, counts = {}; store.entries.forEach(e => { counts[e.v.k] = (counts[e.v.k] || 0) + 1; });
    const needs = store.entries.filter(needsAction).length, byN = [...store.entries].sort((a, b) => a.n - b.n);
    const today = new Date().toISOString().slice(0, 10), t = typeOf(store.type);
    const row = e => `<tr class="pk-${e.v.k}"><td class="pn">${N(e.n)}</td><td><div class="${isQuoteish(e.v) ? "pq" : ""}" dir="auto">${esc(isQuoteish(e.v) ? shownQuote(e.it.text) : e.it.text)}</div></td>
      <td><span class="pchip">${esc(e.v.label)}</span>${store.fixes[e.n] ? `<div class="pfixed">✓ ${store.fixes[e.n] === "applied" ? L("طُبّق التصحيح", "Fix applied") : L("عولج", "Handled")}</div>` : ""}</td>
      <td>${esc(e.v.why || "")}</td><td>${e.v.next ? esc(e.v.next) : "—"}${(() => { const pl = e.v.k !== "ok" ? fixPlan(e) : null, to = pl ? pl.to : e.v.copy; return to ? `<div class="pcopy" dir="auto">${esc(to.length > 220 ? to.slice(0, 220) + "…" : to)}</div>` : pl ? `<div class="pcopy">${L("يُحذف من النص", "Remove it from the text")}</div>` : ""; })()}</td></tr>`;
    const table = (rows, title) => rows.length ? `<h2>${title}</h2><table><colgroup><col style="width: 4%"><col style="width: 22%"><col style="width: 14%"><col style="width: 32%"><col style="width: 28%"></colgroup><thead><tr><th>#</th><th>${L("الموضع في النص", "In the text")}</th><th>${L("النتيجة", "Result")}</th><th>${L("السبب والمصدر", "Why, and the source")}</th><th>${L("ما العمل", "What to do")}</th></tr></thead><tbody>${rows.map(row).join("")}</tbody></table>` : "";
    const must = store.entries.filter(needsAction), rest = store.entries.filter(e => !needsAction(e));
    let marked = "", pos = 0; const text = data.original_text;
    for (const e of byN) { if (e.it.start < pos) continue; marked += esc(text.slice(pos, e.it.start)) + `<span class="pm pk-${e.v.k}"><sup>${N(e.n)}</sup>${esc(text.slice(e.it.start, e.it.end))}</span>`; pos = e.it.end; }
    marked += esc(text.slice(pos));
    const b = store.badge;
    return `<header class="ph"><div class="pbrand"><svg width="34" height="34" viewBox="0 0 40 40" fill="none" stroke="#0B6E5C" stroke-width="2.6"><rect x="9" y="9" width="22" height="22" rx="2"/><rect x="9" y="9" width="22" height="22" rx="2" transform="rotate(45 20 20)"/><circle cx="20" cy="20" r="4" fill="#0B6E5C" stroke="none"/></svg>
        <div><b>${L("مَنبَع", "Manba")}</b><span>${L("تقرير مراجعة المحتوى الشرعي", "Islamic content review report")}</span></div></div>
        <dl><div><dt>${L("التاريخ", "Date")}</dt><dd>${today}</dd></div><div><dt>${L("نوع النص", "Kind of text")}</dt><dd>${esc(t.label)}</dd></div><div><dt>${L("الكلمات", "Words")}</dt><dd>${N(data.word_count)}</dd></div><div><dt>${L("المواضع المفحوصة", "Places checked")}</dt><dd>${N(store.entries.length)}</dd></div></dl></header>
      <section class="pverdict ${needs ? "pv-bad" : "pv-ok"}">${b ? `<div class="pseal">${b.svg}</div>` : ""}<div><p class="phead">${esc(headline(needs, counts))}</p>
        <p class="pcounts">${["bad", "fix", "khl", "ref", "neu", "ok"].filter(k => counts[k]).map(k => `<span class="pchip pk-${k}">${N(counts[k])} ${P(K_LABEL[k])}</span>`).join(" ")}</p>
        ${b ? `<p class="pserial">${L("الرقم التسلسلي", "Serial")}: <code dir="ltr">${esc(b.code)}</code> · ${L("للتحقق", "Verify at")}: <span dir="ltr">${esc(location.host)}/#verify</span></p>` : ""}
        ${data.skipped_claims || data.truncated || (data.llm && data.llm.error) ? `<p class="pnote">${L("المراجعة غير مكتملة؛ قسّم النص وأعد الفحص. لا يمكن تأكيد جاهزيته للنشر.", "Review incomplete; split the text and re-check. Publishing readiness is unconfirmed.")}</p>` : ""}
        ${data.llm && !data.llm.used ? `<p class="pnote">${L("جرت هذه المراجعة بالمطابقة المباشرة دون الذكاء الاصطناعي، فقد لا تظهر فيها الادعاءات غير المقتبسة.", "This review used direct matching without the AI, so unquoted claims may be missing.")}</p>` : ""}</div></section>
      <section class="plegend"><h2>${L("كيف تقرأ التقرير", "How to read this report")}</h2><ul>${["bad", "fix", "khl", "ok"].map(k => `<li><span class="pdot pk-${k}"></span><b>${P(K_LABEL[k])}</b>: ${P(K_EXPLAIN[k])}</li>`).join("")}</ul>
        <p>${L("الأرقام تتبع ترتيب المواضع في النص. الاقتباسات وأحكام المحدثين من المصادر. تقييم علاقة الأدلة بالادعاءات آلي ويحتاج مراجعة بشرية.", "Numbers follow the order of the text. Quotes and scholar gradings come from the sources. AI assessments of how evidence relates to a claim need human review.")}</p></section>
      ${table(must, L("ما يجب تعديله قبل النشر", "What must change before publishing"))}
      ${table(rest, L("بقية المواضع", "The other places"))}
      <h2>${L("النص مع المواضع المرقّمة", "The text, with the places numbered")}</h2><div class="ptext" dir="${data.language && data.language !== "ar" && data.language !== "ur" ? "ltr" : "rtl"}">${marked}</div>
      ${Object.keys(store.fixes || {}).length ? `<h2>${L("النص المصحح", "The corrected text")}</h2><div class="ptext" dir="auto">${esc(($("draftBox") && $("draftBox").value) || draftNow())}</div>` : ""}
      <footer class="pf">${L("هذا التقرير يبيّن مواضع النصوص في المصادر وأحكام العلماء كما نقلتها، وليس فتوى ولا ترجيحًا. ما كتبه الذكاء الاصطناعي معلَّم بذلك في الواجهة.", "This report shows where texts are found in the sources and what scholars' rulings they record. It is not a fatwa and prefers no opinion.")} · ${L("المصادر: Tanzil · الكتب التسعة · الدرر السنية · الموسوعة الفقهية الكويتية · QuranEnc", "Sources: Tanzil · the nine hadith books · Dorar · Kuwaiti Fiqh Encyclopedia · QuranEnc")}</footer>`;
  }
  function preparePrint() {
    if (!store.data || $("reportView").hidden || !store.entries.length) { document.body.classList.remove("printing"); return; }
    $("printDoc").innerHTML = printableReport(); document.body.classList.add("printing");
  }
  window.addEventListener("beforeprint", preparePrint);
  window.addEventListener("afterprint", () => document.body.classList.remove("printing"));


  // Each school the encyclopedia's ruling paragraph names, with the ruling it gives; the school the text named is marked.
  function schoolsRow(f) {
    const xs = f.schools || []; if (!xs.length) return "";
    const named = f.attribution && f.attribution.school;
    return `<div class="schools-row" aria-label="${L("أقوال المذاهب في الموسوعة", "The schools' views in the encyclopedia")}"><span class="cap">${L("أقوال المذاهب في الموسوعة:", "The schools in the encyclopedia:")}</span>${xs.map(x => {
      const sc = x.schools[0], mark = sc === named ? (f.attribution.status === "differs" ? " sch-bad" : " sch-ok") : "";
      return `<span class="sch${mark}">${esc(L(sc, SCHOOL_EN[sc] || sc))} · ${esc(L(x.ruling || "", RULING_EN[x.ruling] || x.ruling || ""))}</span>`;
    }).join("")}</div>`;
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
    return d.length ? `<div class="src"><span class="cap">${L("مواضع الاختلاف", "Differences")}</span><ul style="margin: 0; padding-inline-start: 18px; line-height: 1.9">${d.map(x => `<li>${esc(x)}</li>`).join("")}</ul></div>` : "";
  }
  function fiqhBlock(f) {
    const ps = f.passages || [];
    if (!ps.length) return `<p class="why">${esc(L(f.summary_ar, f.summary_en))}</p>`;
    return ps.slice(0, 2).map(p => `<div class="src">
      <div class="row-between"><b>${esc([p.entry, p.heading].filter(Boolean).join(" · "))}</b><span class="chip ${p.agreement === "agreement" ? "k-ok" : p.agreement === "none" ? "k-neu" : "k-khl"}">${P({ agreement: ["تنقل الاتفاق", "Reports agreement"], disagreement: ["تنقل الخلاف", "Reports disagreement"], both: ["اتفاق وخلاف", "Agreement and disagreement"], none: ["دون تصريح", "Not stated"] }[p.agreement] || "")}</span></div>
      ${p.ruling_sentence ? `<div class="ruling">${esc(p.ruling_sentence)}</div>` : ""}
      ${(p.positions || []).length ? `<div class="schools">${p.positions.slice(0, 4).map(x => `<div><span class="cap">${esc(x.schools.map(sc => L(sc, SCHOOL_EN[sc] || sc)).join(L("، ", ", ")))}${x.ruling ? ` · ${esc(L(x.ruling, RULING_EN[x.ruling] || x.ruling))}` : ""}</span><div class="q" style="font-size: 17px">${esc(x.text)}</div></div>`).join("")}</div>` : ""}
      <details><summary class="cap" style="cursor: pointer">${L("نص الفقرة كاملًا", "The full paragraph")}</summary><div class="q" style="font-size: 17px; line-height: 2; margin-top: 6px">${esc(p.text)}</div></details>
      <span class="cap">${esc(citeOf(p))}${p.same_issue === null ? L(" · مطابقة بالكلمات، تأكد أنها في المسألة نفسها", " · keyword match: confirm it is the same question") : ""}</span>
    </div>`).join("") + `<span class="cap">${esc(L(f.notice_ar, f.notice_en))}</span>`;
  }
  const gradeChips = (s, text) => window.ManbaGrades ? ManbaGrades.chips(s, k => "k-" + k, { text, lang: LANG }) : "";
  // One evidence text: where it is, its grading (hadith) or its tafsir line (verse), and the text itself.
  const evItem = (it, lab) => {
    const g = gradeChips(it.source, it.source.matched_text);
    return `<div class="src"><span class="cap">${lab ? lab + " · " : ""}${esc(where(it.source))}</span><div class="q">${esc(it.source.matched_text)}</div>${g ? `<div class="counts">${g}</div>` : ""}${window.ManbaGrades ? ManbaGrades.context(it, LANG) : ""}</div>`;
  };
  function evidenceBlock(r) {
    const sup = (r.supporting || []).slice(0, 3), con = (r.contradicting || []).slice(0, 3);
    const side = [...(r.partial || []), ...(r.related || [])].slice(0, 6);
    return (sup.length ? `<b style="font-size: 14px">${L("نصوص تؤيده", "Texts that support it")}</b>` + sup.map(x => evItem(x, L("يؤيد", "Supports"))).join("") : "")
      + (con.length ? `<b style="font-size: 14px">${L("نصوص تخالفه", "Texts that contradict it")}</b>` + con.map(x => evItem(x, L("يخالف", "Contradicts"))).join("") : "")
      // Texts found by words or meaning that the judge did not count for or against: kept closed and labelled, because a verse
      // on fighting listed under a claim about violence reads as evidence when it is shown bare.
      + (side.length ? `<details class="related"><summary class="cap" style="cursor: pointer">${L(`${AR_DIGITS(side.length)} نصوص قريبة من موضوع العبارة، لم يُحكم بأنها تؤيدها أو تخالفها`, `${side.length} texts on the same topic, not judged for or against the statement`)}</summary>
          <p class="cap" style="margin: 6px 0">${L("تُعرض للاطلاع فقط. اقرأ كل آية مع سياقها، ولا تُنسب إليها العبارة.", "Shown for reference only. Read each verse in its context; do not attribute the statement to it.")}</p>${side.map(x => evItem(x, "")).join("")}</details>` : "");
  }
  function detailsHtml(e) {
    const v = e.v, it = e.it;
    let h = "";
    const sg = v.seg;
    if (v.trans) h += `<div class="src"><span class="cap">${L("الترجمة المعتمدة", "Approved translation")}: ${esc(v.trans.title)}${v.trans.version ? ` · ${L("الإصدار", "version")} ${esc(v.trans.version)}` : ""}${v.trans.source_url ? ` · <a href="${esc(v.trans.source_url)}" target="_blank" rel="noopener">${v.trans.kind === "quran" ? "QuranEnc" : L("المصدر", "Source")}</a>` : ""}</span><div dir="auto" style="line-height: 1.9">${esc(v.trans.text)}</div></div>`;
    if (sg && sg.source) h += sourceBlock(sg.source, v.trans ? `${L("الأصل العربي", "Arabic original")}: ${where(sg.source)}` : sg.status === "verified" ? where(sg.source) : `${L("النص في المصدر", "The text in the source")}: ${where(sg.source)}`) + (v.trans ? "" : diffBlock(sg));
    if (v.simItem) h += sourceBlock(v.simItem.source);
    if (v.fiqh) h += fiqhBlock(v.fiqh);
    if (it.kind === "claim" && !v.fiqh && it.result.outcome !== "quote_checked") h += evidenceBlock(it.result);
    if (it.kind === "claim" && v.fiqh && (it.result.supporting || []).length) h += `<details><summary class="cap" style="cursor: pointer">${L("نصوص من القرآن والسنة ذُكرت لأحد الأقوال", "Quran and Sunnah texts cited for one of the views")}</summary>${evidenceBlock(it.result)}</details>`;
    const s = (sg && sg.source) || (v.simItem && v.simItem.source);
    if (isQuran(s) && /^\d+:\d+/.test(s.number)) h += `<div class="actions"><button class="btn small" data-tafsir="${esc(s.number)}">${L("التفسير الميسر والسعدي", "Tafsir (al-Muyassar, al-Saadi)")}</button></div><div class="tafsir-out"></div>`;
    if (v.dorar) h += `<div class="dorar" data-q="${esc(quoteOf((sg && sg.segment_text) || it.text))}"><span class="cap">${L("جارٍ جلب أحكام المحدثين من الدرر السنية…", "Loading the scholars' rulings from Dorar…")}</span></div>`;
    h += `<div class="explain"><button class="btn small" data-explain="${e.n}">${L("اشرح النتيجة بالعربية", "Explain the result (Arabic)")}</button> <span class="gen">${L("مولَّد بالذكاء الاصطناعي", "AI-generated")}</span><div class="explain-out"></div></div>`;
    return h;
  }
  function openCard(e, card) {
    const more = card.querySelector(".more"), btn = card.querySelector("[data-open]");
    const open = more.hidden;
    if (open && !more.dataset.built) { more.innerHTML = detailsHtml(e); more.dataset.built = "1"; const d = more.querySelector(".dorar"); if (d) loadDorar(d); }
    more.hidden = !open; if (btn) { btn.setAttribute("aria-expanded", String(open)); btn.textContent = open ? L("إخفاء التفاصيل", "Hide details") : L("التفاصيل والمصادر", "Details and sources"); }
  }

  // The words inside «…», ﴿…﴾ or "…" when the sentence quotes them, else the sentence itself.
  function quoteOf(t) { const m = /[«"“﴿]([^»"”﴾]{4,})[»"”﴾]/.exec(t || ""); return (m ? m[1] : t || "").trim(); }
  // On a card, the quote with its marks ("«اطلبوا العلم ولو في الصين»"), not the sentence around it ("الحمد لله، أما بعد…").
  function shownQuote(t) { const m = /[«"“﴿][^»"”﴾]{4,}[»"”﴾]/.exec(t || ""); return m ? m[0] : t; }
  const isQuoteish = v => v.t === "quran" || v.t === "hadith" || v.t === "quote";
  const normAr = t => (t || "").replace(/[\u064B-\u065F\u0670\u0640]/g, "").replace(/[إأآٱ]/g, "ا").replace(/ى/g, "ي").replace(/ة/g, "ه").replace(/[^\u0621-\u064A\s]/g, " ");
  // Share of the quoted words found in a narration's text: Dorar's search also returns other hadiths on the same theme.
  function wordingScore(q, text) {
    const qs = normAr(q).split(/\s+/).filter(w => w.length > 1), ts = new Set(normAr(text).split(/\s+/));
    if (!qs.length) return 0;
    return qs.filter(w => ts.has(w) || ts.has(w.replace(/^(و|ف|ب|ل|ال)/, "")) || ts.has("ال" + w)).length / qs.length;
  }
  const CAT_L = { sahih: [["صحيح أو ثابت", "authentic"], "k-ok"], hasan: [["حسن", "hasan"], "k-ref"], daif: [["ضعيف أو فيه علة", "weak"], "k-fix"], fabricated: [["موضوع أو لا أصل له", "fabricated or baseless"], "k-bad"], other: [["حكم آخر", "other"], "k-neu"] };
  const CAT = new Proxy({}, { get: (_, k) => CAT_L[k] ? [P(CAT_L[k][0]), CAT_L[k][1]] : undefined });
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
        const parts = ["sahih", "hasan", "daif", "fabricated", "other"].filter(k => c[k]).map(k => `${N(c[k])} ${CAT[k][0]}`);
        const p = document.createElement("p"); p.className = "why dorar-sum";
        p.textContent = L(`أحكام المحدثين على هذا اللفظ في الدرر السنية: ${parts.join("، ")}.`, `Scholars' rulings on this wording in Dorar: ${parts.join(", ")}.`);
        const why = card.querySelector(".why"); (why || card.querySelector(".head")).after(p);
      } catch (err) { /* the details still offer the Dorar link */ }
    }));
  }
  async function loadDorar(el) {
    try {
      const d = await fetchDorar(el.dataset.q);
      if (!d.items.length) { el.innerHTML = `<span class="cap">${L("لم تُرجع الدرر السنية نتائج لهذا اللفظ.", "Dorar returned nothing for this wording.")} <a href="https://dorar.net/hadith/search?q=${encodeURIComponent(d.query)}" target="_blank" rel="noopener">${L("ابحث في الدرر", "Search Dorar")}</a></span>`; return; }
      const order = ["sahih", "hasan", "daif", "fabricated", "other"];
      const same = d.items.filter(i => wordingScore(el.dataset.q, i.text) >= 0.6);
      const near = d.items.filter(i => !same.includes(i));
      const counts = {}; same.forEach(i => { counts[i.category] = (counts[i.category] || 0) + 1; });
      const mixed = (counts.sahih || counts.hasan) && (counts.daif || counts.fabricated);
      const row = (i, hide) => `<div class="dorar-row" ${hide ? "data-extra hidden" : ""}><div class="row-between"><b>${esc(i.scholar)}</b><span class="chip ${CAT[i.category][1]}">${esc(i.grade || "—")}</span></div><span class="dtext">${esc(i.text.length > 140 ? i.text.slice(0, 140) + "…" : i.text)}</span><span class="cap">${esc(i.source)}${i.page ? " · " + esc(i.page) : ""}${i.narrator ? L(" · الراوي: ", " · narrator: ") + esc(i.narrator) : ""}</span></div>`;
      let h = `<div class="src"><b style="font-size: 14px">${L("أحكام المحدثين كما في الدرر السنية", "Scholars' rulings as recorded in Dorar")}</b>`;
      if (same.length) {
        h += `<span class="cap">${L(`${AR_DIGITS(same.length)} رواية بهذا اللفظ:`, `${same.length} narrations with this wording:`)}</span><div class="counts">${order.filter(c => counts[c]).map(c => `<span class="chip ${CAT[c][1]}">${N(counts[c])} ${CAT[c][0]}</span>`).join("")}</div>
        ${mixed ? `<span class="cap">${L("الأحكام مختلفة؛ تُعرض كما هي دون ترجيح.", "The rulings differ; they are shown as they are, without preference.")}</span>` : ""}
        <div>${same.map((i, k) => row(i, k >= 4)).join("")}</div>
        ${same.length > 4 ? `<button class="link" data-allrows>${L("عرض الأحكام كلها", "Show all rulings")} (${N(same.length)})</button>` : ""}`;
      } else {
        h += `<span class="cap">${L("لم نجد هذا اللفظ بعينه في نتائج الدرر.", "This exact wording is not in Dorar's results.")}</span>`;
      }
      if (near.length) h += `<details><summary class="cap" style="cursor: pointer">${L(`${AR_DIGITS(near.length)} حديث بألفاظ قريبة، ليست هذا النص بعينه`, `${near.length} hadith with similar wording, not this text`)}</summary><div>${near.map(i => row(i, false)).join("")}</div></details>`;
      h += `<span class="cap">${L("المصدر: الموسوعة الحديثية، الدرر السنية", "Source: Dorar hadith encyclopedia")} · <a href="https://dorar.net/hadith/search?q=${encodeURIComponent(d.query)}" target="_blank" rel="noopener">${L("افتح البحث في الدرر", "Open the search in Dorar")}</a></span></div>`;
      el.innerHTML = h;
    } catch (e) {
      el.innerHTML = `<span class="cap">${L("تعذر جلب أحكام المحدثين الآن.", "The scholars' rulings could not be loaded right now.")} <a href="https://dorar.net/hadith/search?q=${encodeURIComponent(el.dataset.q)}" target="_blank" rel="noopener">${L("ابحث في الدرر السنية مباشرة", "Search Dorar directly")}</a></span>`;
    }
  }

  async function loadTafsir(btn) {
    const out = btn.parentElement.nextElementSibling;
    btn.disabled = true; out.innerHTML = `<span class="cap">${L("جارٍ التحميل…", "Loading…")}</span>`;
    try {
      const res = await fetch("/api/tafsir/" + encodeURIComponent(btn.dataset.tafsir), { headers: headers(false) });
      const d = await res.json(); if (!res.ok) throw new Error();
      out.innerHTML = d.verses.flatMap(vv => vv.entries.map(en => `<details class="src" open><summary style="cursor: pointer"><b>${esc(en.name_ar)}</b> <span class="cap">${esc(en.author_ar)}</span></summary><div class="q" style="font-size: 18px; line-height: 2">${esc(en.text)}</div></details>`)).join("") || `<span class="cap">${L("لا يتوفر تفسير لهذه الآية في مصادرنا.", "No tafsir for this verse in our sources.")}</span>`;
      btn.remove();
    } catch (e) { out.innerHTML = `<span class="cap">${L("تعذر تحميل التفسير.", "The tafsir could not be loaded.")}</span>`; btn.disabled = false; }
  }

  async function explain(btn) {
    const e = store.entries.find(x => x.n === +btn.dataset.explain), out = btn.parentElement.querySelector(".explain-out");
    const payload = e.it.kind === "claim" ? { claim: e.it.text, result: e.it.result } : e.it.kind === "quote" ? { claim: e.it.text, segment: e.it.quote } : null;
    if (!payload) { out.innerHTML = `<span class="cap">${L("لا يتوفر شرح لهذا النوع.", "No explanation for this kind of result.")}</span>`; return; }
    btn.disabled = true; out.innerHTML = `<span class="cap">${L("جارٍ كتابة الشرح…", "Writing the explanation…")}</span>`;
    try {
      const res = await fetch("/api/explain", { method: "POST", headers: headers(true), body: JSON.stringify(payload) });
      const d = await res.json(); if (!res.ok) throw new Error();
      out.innerHTML = `<div class="src" style="border-style: dashed"><span class="gen" style="align-self: flex-start">${d.ai_written ? L("كتبه الذكاء الاصطناعي من النصوص المعروضة فقط، وليس من نصوص المصادر", "Written by the AI from the texts shown only; not a source text") : L("شرح مبسّط مولَّد آليًا من النتيجة", "A plain explanation generated from the result")}</span>
        ${d.summary_ar ? `<b>${esc(d.summary_ar)}</b>` : ""}${(d.points || []).map(p => `<p style="margin: 0; line-height: 1.9">${esc(p.text)}</p>`).join("")}${d.caution ? `<span class="cap">${esc(d.caution)}</span>` : ""}</div>`;
      btn.remove();
    } catch (err) { out.innerHTML = `<span class="cap">${L("تعذر كتابة الشرح الآن.", "The explanation could not be written right now.")}</span>`; btn.disabled = false; }
  }

  function summaryText() {
    const hl = document.getElementById("headline");
    const lines = [L("تقرير مراجعة مَنبَع", "Manba review report"), hl ? hl.textContent : "", ""];
    for (const e of store.entries) {
      lines.push(`${e.n}. [${e.v.label}] ${e.it.text}`);
      if (e.v.why) lines.push(`   ${e.v.why}`);
      if (e.v.next) lines.push(`   ${L("الخطوة التالية", "Next step")}: ${e.v.next}`);
      if (e.v.copy) lines.push(`   ${L("النص الصحيح", "Correct text")}: ${e.v.copy}`);
    }
    lines.push("", L("بيان لمواضع النصوص في المصادر وليس فتوى. المصادر: المصحف، الكتب التسعة، الدرر السنية، الموسوعة الفقهية الكويتية.", "Shows where texts are found in the sources; not a fatwa. Sources: the Mushaf, the nine hadith books, Dorar, the Kuwaiti Fiqh Encyclopedia."));
    return lines.join("\n");
  }
  async function copy(text, btn) {
    try { await navigator.clipboard.writeText(text); const t = btn.textContent; btn.textContent = L("نُسخ", "Copied"); setTimeout(() => { btn.textContent = t; }, 1500); }
    catch (e) { window.prompt(L("انسخ النص:", "Copy the text:"), text); }
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
  $("reportView").addEventListener("input", ev => { if (ev.target.id === "draftBox") {
    store.manualDraft = ev.target.value; ev.target.dataset.edited = "1";
    const btn = $("recheckBtn"); if (btn) btn.disabled = false;
    const apply = $("applyAll"); if (apply) apply.hidden = true;
    $("reportView").querySelectorAll("[data-fix], [data-unfix]").forEach(b => { b.disabled = true; });
  } });
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
    if (t.dataset.fix || t.dataset.manual) { if (t.dataset.fix && store.manualDraft !== undefined) return; store.fixes[+(t.dataset.fix || t.dataset.manual)] = t.dataset.fix ? "applied" : "manual"; refreshFixes(); return; }
    if (t.dataset.unfix) { delete store.fixes[+t.dataset.unfix]; refreshFixes(); return; }
    if (t.id === "copyDraft" || t.id === "copyDraft2") { copy($("draftBox") ? $("draftBox").value : (store.verifiedText || draftNow()), t); return; }
    if (t.id === "recheckBtn") { const text = $("draftBox").value.trim(); store.recheck = true; $("text").value = text; updateCount(); run(); return; }
    if (t.id === "shareBtn") { shareLink(store.data.original_text).then(link => copy(link, t)); return; }
    if (t.id === "copyBadgeLink") { copy(store.badge.link, t); return; }
    if (t.id === "dlBadge") { const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([store.badge.svg], { type: "image/svg+xml" })); a.download = `manba-badge-${store.badge.code}.svg`; a.click(); return; }
    if (t.id === "printBtn") { preparePrint(); window.print(); return; }
    if (t.id === "copySerial") { copy(store.badge.code, t); return; }
    if (t.id === "applyAll") { applyAll(); return; }
    if (t.id === "editBtn" || t.id === "newBtn") { newReview(); return; }
  });

  // ---------- theme: dark is the default; the button switches to light and back, and the choice is remembered ----------
  const root = document.documentElement, themeBtn = $("themeBtn");
  const isLight = () => root.dataset.theme === "light";
  function labelTheme() { const t = isLight() ? L("الوضع الداكن", "Dark mode") : L("الوضع الفاتح", "Light mode"); themeBtn.setAttribute("aria-label", t); themeBtn.title = t; }
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
  let serverCfg = null;
  function cfgNote() {
    const c = serverCfg; if (!c) return;
    const k = c.server_keys || {}, has = Object.keys(k).filter(x => k[x]);
    $("cfgNote").textContent = L(`تبقى المفاتيح في متصفحك فقط. ${has.length ? "لدى الخادم مفتاح جاهز، فلا حاجة لإدخال مفتاحك." : "لا يوجد مفتاح على الخادم: أدخل مفتاحك ليعمل تقييم الادعاءات."}${c.access_required ? " الخادم يطلب رمز دخول." : ""}`,
      `Keys stay in your browser only. ${has.length ? "The server has a key, so you do not need to enter yours." : "The server has no key: enter yours for claims to be judged."}${c.access_required ? " The server asks for an access code." : ""}`);
  }
  fetch("/api/config").then(r => r.json()).then(c => { serverCfg = c; cfgNote(); }).catch(() => {});

  // ---------- sections: review, how it works, who it is for ----------
  const VIEWS = { how: "howView", who: "whoView", verify: "verifyView" };
  function showView(name, push) {
    const page = VIEWS[name];
    for (const id of Object.values(VIEWS)) $(id).hidden = id !== page;
    if (page) { $("inputView").hidden = true; $("reportView").hidden = true; $("loadingView").hidden = true; }
    else if (store.data && store.onReport) { $("reportView").hidden = false; $("inputView").hidden = true; }
    else { $("reportView").hidden = true; $("inputView").hidden = false; $("inputView").classList.remove("wait"); }
    document.querySelectorAll(".view-tab").forEach(a => { if ((a.dataset.view === name) || (!page && a.dataset.view === "review")) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); });
    if (push) history.pushState({}, "", page ? "#" + name : store.onReport ? "#report" : "#");
    window.scrollTo({ top: 0 });
    if (!page) placePill();
    document.dispatchEvent(new CustomEvent("manba:view", { detail: name }));
  }
  document.addEventListener("click", ev => {
    const a = ev.target.closest("[data-view]"); if (!a) return;
    ev.preventDefault(); showView(a.dataset.view === "review" ? "review" : a.dataset.view, true);
  });
  window.addEventListener("popstate", () => { const h = location.hash.slice(1); if (VIEWS[h]) showView(h, false); else if (!h.includes("report")) showView("review", false); });
  // Each person on "who it is for" opens the reviewer with their scenario.
  const SCENARIOS = {
    khutbah: SAMPLES[0][1],
    post: SAMPLES[1][1],
    lesson: SAMPLES[4][1],
    english: SAMPLES[5][1],
    reviewer: "ومن الأدلة على فضل الرحمة قوله ﷺ: «الراحمون يرحمهم الرحمن، ارحموا من في الأرض يرحمكم من في السماء». وقد أجمع العلماء على أن قراءة الفاتحة خلف الإمام واجبة. وقال تعالى: «وأحل الله البيع وحرم الزنا». ولحديث: «اختلاف أمتي رحمة».",
  };
  document.querySelectorAll(".persona[data-scenario]").forEach(card => card.querySelector("button").addEventListener("click", () => {
    showView("review", true); $("text").value = SCENARIOS[card.dataset.scenario] || ""; showTab("paste"); updateCount(); run();
  }));

  // ---------- language ----------
  function applyLang() {
    const en = LANG === "en", html = document.documentElement;
    html.lang = LANG; html.dir = en ? "ltr" : "rtl";
    document.querySelectorAll("[data-en]").forEach(el => { if (el.dataset.ar === undefined) el.dataset.ar = el.innerHTML; el.innerHTML = en ? el.dataset.en : el.dataset.ar; });
    for (const attr of ["placeholder", "aria-label", "aria-roledescription", "title"]) {
      document.querySelectorAll(`[data-en-${attr}]`).forEach(el => {
        const keep = "ar" + attr.replace(/-./g, m => m[1].toUpperCase()).replace(/^./, m => m.toUpperCase());
        if (el.dataset[keep] === undefined) el.dataset[keep] = el.getAttribute(attr) || "";
        el.setAttribute(attr, en ? el.getAttribute(`data-en-${attr}`) : el.dataset[keep]);
      });
    }
    document.title = L("مَنبَع · مراجعة المحتوى الشرعي قبل النشر", "Manba · review Islamic content before publishing");
    renderSamples(); updateCount(); labelTheme(); cfgNote(); placePill();
    if (store.data && !$("reportView").hidden) renderReport(store.data);
    document.dispatchEvent(new CustomEvent("manba:lang", { detail: LANG }));
  }
  $("langBtn").onclick = () => { LANG = LANG === "en" ? "ar" : "en"; try { localStorage.setItem("manba_lang", LANG); } catch (e) {} applyLang(); };
  if (LANG === "en") applyLang();
  { const h = location.hash.slice(1); if (VIEWS[h]) showView(h, false); }
  // A shared report (#s=): the text is unpacked and checked again from the sources.
  { const m = /^#s=(.+)$/.exec(location.hash);
    if (m) unpackText(m[1]).then(text => { $("text").value = text; updateCount(); showTab("paste"); run(); }).catch(() => alertInline(L("تعذر فتح الرابط المشارَك.", "The shared link could not be opened."))); }
  // A badge link (#v=SERIAL&t=TEXT): the verify page, filled in and checked at once. It needs no access token.
  { const m = /^#v=([^&]+)(?:&t=(.+))?$/.exec(location.hash);
    if (m) { showView("verify", false); $("vCode").value = decodeURIComponent(m[1]);
      (m[2] ? unpackText(m[2]).then(t => { $("vText").value = t; }).catch(() => {}) : Promise.resolve()).then(verifyBadge); } }
  $("vCode").addEventListener("keydown", e => { if (e.key === "Enter") verifyBadge(); });
  $("verifyView").addEventListener("click", ev => {
    const t = ev.target.closest("button"); if (!t) return;
    if (t.id === "vGo") verifyBadge();
    if (t.id === "vRerun") { $("text").value = $("vText").value; updateCount(); showView("review", true); showTab("paste"); run(); }
  });

  updateCount();
})();
