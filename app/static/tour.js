/* The How page: one real khutbah taken through Manba in six steps (paste, highlights, sources, report, fixes, badge).
   Each step is a still of the real interface, drawn here so the tour works without a key or a network call. */
(() => {
  const $ = id => document.getElementById(id);
  if (!$("tour")) return;
  const en = () => document.documentElement.lang === "en";
  const L = (ar, e) => (en() ? e : ar);
  const D = n => (en() ? String(n) : String(n).replace(/\d/g, d => "٠١٢٣٤٥٦٧٨٩"[d]));
  const reduced = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;

  // The khutbah used in every step, and its three findings.
  const OPEN = "الحمد لله، أما بعد: عباد الله، إن طلب العلم من أعظم القربات، ";
  const HADITH = "وقد قال رسول الله ﷺ: «اطلبوا العلم ولو في الصين»";
  const VERSE = "«وأحل الله البيع وحرم الزنا»";
  const CLAIM = "وزكاة الحلي المستعمل واجبة بالإجماع";
  const WORDS = (OPEN + HADITH + ". ومن ثمرات العلم معرفة الحلال والحرام؛ قال تعالى: " + VERSE + ". " + CLAIM).split(/\s+/).filter(Boolean).length;
  const mark = (k, n, t) => `<mark class="tm tm-${k}"><sup>${D(n)}</sup>${t}</mark>`;
  const khutbah = marked => `<p class="tq" dir="rtl">${OPEN}${marked ? mark("bad", 1, HADITH) : HADITH}. ومن ثمرات العلم معرفة الحلال والحرام؛ قال تعالى: ${marked ? mark("fix", 2, VERSE) : VERSE}. ${marked ? mark("bad", 3, CLAIM) : CLAIM}.</p>`;
  const fixed = `<p class="tq" dir="rtl">${OPEN.replace(/، $/, ".")} ومن ثمرات العلم معرفة الحلال والحرام؛ قال تعالى: <ins>﴿وَأَحَلَّ ٱللَّهُ ٱلْبَيْعَ وَحَرَّمَ ٱلرِّبَوٰا۟﴾ [البقرة: ٢٧٥]</ins>. <ins>وزكاة الحلي المستعمل واجبة عند الحنفية، وفي المسألة خلاف</ins>.</p>`;
  const chip = (k, t) => `<span class="chip k-${k}">${t}</span>`;

  const STEPS = [
    {
      t: ["الصق نصك", "Paste your text"],
      d: ["خطبة أو مقال أو منشور أو درس: تكتبه، أو ترفع ملفًا، أو صورة وPDF. بالعربية أو بالإنجليزية أو بلغات أخرى. النص يُفحص ولا يُحفظ.",
        "A khutbah, article, post or lesson: type it, upload a file, or a photo or PDF. Arabic, English or other languages. Your text is checked, never stored."],
      scene: () => `<div class="ts-compose"><div class="ts-tabs"><span class="on">${L("كتابة", "Type")}</span><span>${L("ملف", "File")}</span><span>${L("صورة أو PDF", "Image or PDF")}</span></div>
        <div class="ts-area">${khutbah(false)}<span class="caret" aria-hidden="true"></span></div>
        <div class="ts-row"><span class="cap">${L(`${D(WORDS)} كلمة`, `${WORDS} words`)}</span><span class="btn small primary ts-pulse">${L("راجع النص", "Review the text")}</span></div></div>`,
    },
    {
      t: ["نعلّم كل ما يحتاج تحققًا", "Everything to check is marked"],
      d: ["كل آية وحديث مقتبس، وكل جملة فيها حكم شرعي ولو بلا علامات تنصيص. الذكاء الاصطناعي يدلّ على المواضع فقط، ولا يحكم عليها.",
        "Every quoted verse and hadith, and every sentence that states a ruling, even without quotation marks. The AI only points at them; it does not judge them."],
      scene: () => `<div class="ts-doc"><div class="ts-head"><b>${L("النص كما أُدخل", "The text as entered")}</b><span class="cap">${L("٣ مواضع", "3 places")}</span></div>${khutbah(true)}
        <div class="ts-legend">${chip("bad", L("١ حديث و١ حكم فقهي", "1 hadith, 1 fiqh ruling"))}${chip("fix", L("١ آية", "1 verse"))}<span class="cap">${L("اللون من نتيجة الفحص، والرقم يفتح تفاصيله", "The colour is the result; the number opens its details")}</span></div></div>`,
    },
    {
      t: ["نرجع بكل موضع إلى مصدره", "Each one goes back to its source"],
      d: ["الآية تُطابق بالمصحف حرفًا بحرف، والحديث يُبحث عنه في الكتب التسعة وأحكام المحدثين والدرر السنية، والحكم يُقرأ من الموسوعة الفقهية الكويتية مذهبًا مذهبًا. الحكم هنا للمصدر، لا للنموذج.",
        "The verse is matched to the Mushaf letter by letter, the hadith is searched in the nine books, the scholars' gradings and Dorar, and the ruling is read from the Kuwaiti Fiqh Encyclopedia school by school. The source decides, not the model."],
      scene: () => `<div class="ts-src">
        <div class="ts-s"><span class="num">${D(2)}</span><div><b>${L("المصحف، سورة البقرة، الآية ٢٧٥", "The Mushaf, al-Baqarah 2:275")}</b>
          <p class="tq" dir="rtl">وَأَحَلَّ ٱللَّهُ ٱلْبَيْعَ وَحَرَّمَ <ins>ٱلرِّبَوٰا۟</ins> <del>الزنا</del></p><span class="cap">${L("كلمة واحدة مبدّلة", "One word changed")}</span></div></div>
        <div class="ts-s"><span class="num">${D(1)}</span><div><b>${L("الكتب التسعة والدرر السنية", "The nine books and Dorar")}</b>
          <p>${chip("bad", L("لم يوجد في الكتب التسعة", "Not in the nine books"))} ${chip("bad", L("الدرر: ضعيف وموضوع", "Dorar: weak and fabricated"))}</p></div></div>
        <div class="ts-s"><span class="num">${D(3)}</span><div><b>${L("الموسوعة الفقهية الكويتية: زكاة الحلي", "Kuwaiti Fiqh Encyclopedia: zakat on jewellery")}</b>
          <p class="ts-sch"><span class="sch sch-ok">${L("الحنفية · واجب", "Hanafi · obligatory")}</span><span class="sch">${L("المالكية · غير واجب", "Maliki · not obligatory")}</span><span class="sch">${L("الشافعية · غير واجب", "Shafi'i · not obligatory")}</span><span class="sch">${L("الحنابلة · غير واجب", "Hanbali · not obligatory")}</span></p></div></div></div>`,
    },
    {
      t: ["تقرير يقول لك ما تفعل", "A report that tells you what to do"],
      d: ["يبدأ التقرير بما يمنع النشر، ويخاطبك بحسب نوع النص: خطبة أو منشور أو درس. لكل موضع سببه ومصدره وخطوته التالية.",
        "The report starts with what blocks publishing and speaks to the kind of text: a khutbah, a post or a lesson. Each place has its reason, its source and a next step."],
      scene: () => `<div class="ts-report"><span class="cap">${L("تقرير المراجعة · خطبة", "Review report · khutbah")}</span>
        <h3>${L("هذه الخطبة تحتاج تعديلًا قبل الإلقاء", "This khutbah needs changes before it is delivered")}</h3>
        <div class="ts-bar"><i class="b" style="flex: 1"></i><i class="f" style="flex: 1"></i><i class="b" style="flex: 1"></i></div>
        <p>${chip("bad", L("١ لا يُنسب إلى النبي ﷺ", "1 not attributable to the Prophet ﷺ"))} ${chip("fix", L("١ آية نُقلت بخطأ", "1 misquoted verse"))} ${chip("bad", L("١ إجماع مدّعى غير ثابت", "1 claimed consensus not established"))}</p>
        <div class="ts-card"><div>${chip("bad", L("لم يوجد في كتب الحديث", "Not found in the hadith books"))}</div><p class="tq" dir="rtl">«اطلبوا العلم ولو في الصين»</p>
          <p class="next"><b>${L("الخطوة التالية: لا يُنسب إلى النبي ﷺ حتى يثبت، احذفه أو تحقق منه", "Next step: do not attribute it to the Prophet ﷺ until it is established; remove or verify it")}</b></p></div></div>`,
    },
    {
      t: ["طبّق التصحيحات بنقرة", "Apply the fixes in one click"],
      d: ["حيث يمكن التصحيح من المصدر نفسه يقترحه مَنبَع: نص المصحف مكان الآية المحرّفة، وحذف الحديث الذي لا يثبت، ونسبة القول إلى مذهبه مع ذكر الخلاف. وما سوى ذلك تعالجه بنفسك وتعلّمه.",
        "Where the source itself gives the fix, Manba offers it: the Mushaf's wording for a misquoted verse, removing a hadith that is not established, and attributing a ruling to its school with the disagreement noted. Anything else you handle yourself and tick off."],
      scene: () => `<div class="ts-fix"><div class="row-between"><b>${L("طبّق التصحيحات واحصل على شارة مَنبَع", "Apply the fixes and earn the Manba badge")}</b><span class="cap">${L("٣ من ٣", "3 of 3")}</span></div>
        <div class="fixprog"><i style="width: 100%"></i></div>
        <div class="ts-done">✓ ${L("حُذف الحديث", "Hadith removed")}</div><div class="ts-done">✓ ${L("وُضع نص المصحف", "Mushaf text inserted")}</div><div class="ts-done">✓ ${L("نُسب القول إلى الحنفية مع ذكر الخلاف", "Attributed to the Hanafis, disagreement noted")}</div>
        <div class="ts-draft">${fixed}</div></div>`,
    },
    {
      t: ["أعد الفحص وانل الشارة", "Re-check and earn the badge"],
      d: ["يُفحص النص المصحح من جديد، ولا تُمنح الشارة إلا إذا جاء نظيفًا. رابط الشارة يعيد التحقق من النص نفسه عند فتحه، ورمزها يتغيّر إن تغيّر حرف منه. ويمكنك مشاركة التقرير برابط واحد.",
        "The corrected text is checked again, and the badge is given only if it comes back clean. The badge link re-verifies the same text when opened, and its code changes if a single letter changes. The report can be shared with one link."],
      scene: () => `<div class="ts-badge"><div class="seal">${window.ManbaBadge ? window.ManbaBadge("6C1F0A93D2", "2026-10-05") : ""}</div>
        <b>${L("نال النص شارة مَنبَع", "The text earned the Manba badge")}</b>
        <div class="ts-row"><span class="btn small primary">${L("نزّل الشارة", "Download the badge")}</span><span class="btn small">${L("انسخ رابط التحقق", "Copy the verification link")}</span><span class="btn small">${L("مشاركة التقرير", "Share the report")}</span></div></div>`,
    },
  ];

  let at = 0, timer = null, playing = false;
  const DWELL = 7000;

  function renderSteps() {
    $("tourSteps").innerHTML = STEPS.map((s, i) => `<li class="${i === at ? "on" : i < at ? "past" : ""}">
      <button type="button" data-step="${i}" aria-current="${i === at ? "step" : "false"}"><span class="fi">${D(i + 1)}</span><b>${L(...s.t)}</b></button>
      ${i === at ? `<p>${L(...s.d)}</p>` : ""}</li>`).join("");
    $("tourDots").innerHTML = STEPS.map((s, i) => `<button type="button" class="dot${i === at ? " on" : ""}" data-step="${i}" aria-label="${L(`الخطوة ${D(i + 1)}: `, `Step ${i + 1}: `)}${L(...s.t)}" aria-current="${i === at ? "step" : "false"}"></button>`).join("");
  }
  function render(animate) {
    const sc = $("tourScene");
    sc.innerHTML = `<div class="ts-step${animate && !reduced ? " enter" : ""}"><span class="ts-n">${L(`الخطوة ${D(at + 1)} من ${D(STEPS.length)}`, `Step ${at + 1} of ${STEPS.length}`)}</span>${STEPS[at].scene()}</div>`;
    renderSteps();
    $("tourBack").disabled = at === 0;
    const last = at === STEPS.length - 1;
    $("tourNext").textContent = last ? L("جرّبه على نصك", "Try it on your text") : L("التالي", "Next");
    $("tourPlay").textContent = playing ? L("إيقاف", "Pause") : L("تشغيل تلقائي", "Autoplay");
    $("tourPlay").setAttribute("aria-pressed", String(playing));
  }
  function go(i, animate = true) { at = Math.max(0, Math.min(STEPS.length - 1, i)); render(animate); }
  function stop() { playing = false; clearInterval(timer); timer = null; render(false); }
  function play() {
    playing = true; clearInterval(timer);
    timer = setInterval(() => { if (at === STEPS.length - 1) { stop(); return; } go(at + 1); }, DWELL);
    render(false);
  }

  $("tour").addEventListener("click", ev => {
    const b = ev.target.closest("[data-step]");
    if (b) { if (playing) stop(); go(+b.dataset.step); }
  });
  $("tourBack").onclick = () => { if (playing) stop(); go(at - 1); };
  $("tourNext").onclick = () => {
    if (playing) stop();
    if (at === STEPS.length - 1) { const a = document.querySelector('[data-view="review"]'); if (a) a.click(); return; }
    go(at + 1);
  };
  $("tourPlay").onclick = () => (playing ? stop() : play());
  $("tour").addEventListener("keydown", ev => {
    if (ev.target.closest("textarea, input")) return;
    const fwd = en() ? "ArrowRight" : "ArrowLeft", back = en() ? "ArrowLeft" : "ArrowRight";
    if (ev.key === fwd) { if (playing) stop(); go(at + 1); ev.preventDefault(); }
    if (ev.key === back) { if (playing) stop(); go(at - 1); ev.preventDefault(); }
  });

  document.addEventListener("manba:lang", () => render(false));
  document.addEventListener("manba:view", ev => {
    if (ev.detail === "how") { go(0, false); if (!reduced) play(); }
    else if (playing) stop();
  });
  render(false);
  if (!$("howView").hidden && !reduced) play();
})();
