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
      d: ["خطبة أو مقال أو منشور أو درس: تكتبه، أو ترفع ملفًا، أو صورة وPDF. بالعربية أو بالإنجليزية أو بلغات أخرى. قد تعالج النص ذاكرة مؤقتة ومزوّدو الذكاء الاصطناعي؛ اقرأ تفاصيل الخصوصية أدناه.",
        "A khutbah, article, post or lesson: type it, upload a file, or a photo or PDF. Arabic, English or other languages. Temporary caches and AI providers may process your text; see the privacy details below."],
      scene: () => `<div class="ts-compose"><div class="ts-tabs"><span class="on">${L("كتابة", "Type")}</span><span>${L("ملف", "File")}</span><span>${L("صورة أو PDF", "Image or PDF")}</span></div>
        <div class="ts-area">${khutbah(false)}<span class="caret" aria-hidden="true"></span></div>
        <div class="ts-row"><span class="cap">${L(`${D(WORDS)} كلمة`, `${WORDS} words`)}</span><span class="btn small primary ts-pulse">${L("راجع النص", "Review the text")}</span></div></div>`,
    },
    {
      t: ["نعلّم كل ما يحتاج تحققًا", "Everything to check is marked"],
      d: ["نبحث عن الآيات والأحاديث والادعاءات الشرعية، ولو بلا علامات تنصيص. يساعد النموذج في العثور على الادعاءات وتقدير صلة الأدلة؛ وقد تفوت المراجعة بعض المواضع.",
        "We look for verses, hadith and religious claims, including unquoted wording. AI helps find claims and assess evidence relevance; the review may miss some passages."],
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
      d: ["يُفحص النص المصحح من جديد. تتطلب الشارة مراجعة مكتملة بلا نتائج عالقة، ومفتاح توقيع مهيّأ. صفحة التحقق تفحص توقيع الرقم ومطابقة النص حرفيًا؛ ولا تعيد الحكم على مضمونه. الشارة هنا مثال توضيحي.",
        "The corrected text is checked again. A badge requires a complete review with no unresolved findings and configured signing. Verification checks the receipt's signature and exact text match; it does not review the content again. This badge is an illustration."],
      scene: () => `<div class="ts-badge"><div class="seal">${window.ManbaBadge ? window.ManbaBadge("MNB2-" + Array(13).fill("AAAA").concat("AAA").join("-"), "2026-10-05") : ""}</div>
        <b>${L("مثال توضيحي لشارة مَنبَع", "Illustration of a Manba badge")}</b>
        <div class="ts-row"><span class="btn small primary">${L("نزّل الشارة", "Download the badge")}</span><span class="btn small">${L("انسخ رابط التحقق", "Copy the verification link")}</span><span class="btn small">${L("مشاركة التقرير", "Share the report")}</span></div></div>`,
    },
  ];

  // The tour plays by itself, one step every few seconds, and loops; Back and Next move it by hand and the clock restarts.
  let at = 0, shown = null, landing = false, timer = null, paused = reduced;   // landing: the new circle is drawn empty, a drop is on its way
  const DWELL = 6500, active = () => !$("howView").hidden && !document.hidden;

  function renderSteps() {
    $("tourSteps").innerHTML = STEPS.map((s, i) => `<li class="${i === at ? "on" : i < at ? "past" : ""}">
      <button type="button" data-step="${i}" aria-current="${i === at ? "step" : "false"}"><span class="fi${i === at && landing ? " waiting" : ""}">${D(i + 1)}</span><b>${L(...s.t)}</b></button>
      ${i === at ? `<p>${L(...s.d)}</p>` : ""}</li>`).join("");
    $("tourDots").innerHTML = STEPS.map((s, i) => `<button type="button" class="dot${i === at ? " on" : ""}" data-step="${i}" aria-label="${L(`الخطوة ${D(i + 1)}: `, `Step ${i + 1}: `)}${L(...s.t)}" aria-current="${i === at ? "step" : "false"}"><i style="animation-duration: ${DWELL}ms"></i></button>`).join("");
  }
  // The step circles hang on a thin rail. When the tour moves to another step a drop swells on the old circle, falls down the rail (stretching as it speeds up),
  // lands on the new circle and splashes there; going back, a bubble rises instead.
  const steps = () => $("tourSteps");
  const centerOf = el => { const o = steps().getBoundingClientRect(), r = el.getBoundingClientRect(); return r.width ? { x: r.left + r.width / 2 - o.left, y: r.top + r.height / 2 - o.top } : null; };
  function rail() {
    const ol = steps(); ol.querySelectorAll(".tour-rail").forEach(r => r.remove());
    const f = ol.querySelectorAll(".fi"); if (f.length < 2) return;
    const a = centerOf(f[0]), b = centerOf(f[f.length - 1]); if (!a || !b) return;   // a narrow screen shows only the current step: no rail
    const r = document.createElement("span"); r.className = "tour-rail"; r.setAttribute("aria-hidden", "true");
    r.style.left = a.x + "px"; r.style.top = a.y + "px"; r.style.height = Math.max(0, b.y - a.y) + "px"; ol.prepend(r);
  }
  function splash(fi) {
    fi.classList.remove("waiting", "splash"); void fi.offsetWidth; fi.classList.add("splash");   // the circle fills with colour only now, as the drop lands
    setTimeout(() => fi.classList.remove("splash"), 900);
  }
  function dropTo(a, b, falling, target) {
    const ol = steps(), d = document.createElement("span"); d.className = "tour-drop" + (falling ? "" : " up"); d.setAttribute("aria-hidden", "true"); d.innerHTML = "<i></i>";
    d.style.left = a.x + "px"; ol.appendChild(d);
    const at = (y, sx, sy) => `translate(-50%, calc(-50% + ${y}px)) scale(${sx}, ${sy})`, dist = Math.abs(b.y - a.y), duration = Math.round(Math.min(1300, 650 + dist * 1.2));
    const frames = falling
      ? [{ transform: at(a.y, .15, .15), opacity: 0, offset: 0, easing: "ease-out" },
         { transform: at(a.y + 4, 1, 1.15), opacity: 1, offset: .24, easing: "cubic-bezier(.6, 0, 1, .55)" },     // it swells and hangs, then lets go and speeds up
         { transform: at(b.y - 8, .8, 1.8), opacity: 1, offset: .93, easing: "ease-out" },                          // stretched by the speed
         { transform: at(b.y, 1.6, .25), opacity: 0, offset: 1 }]                                                  // squashed flat on landing
      : [{ transform: at(a.y, .15, .15), opacity: 0, offset: 0, easing: "ease-out" },
         { transform: at(a.y - 2, 1, 1), opacity: 1, offset: .2, easing: "cubic-bezier(.3, 0, .45, 1)" },
         { transform: at(b.y, .9, 1), opacity: 1, offset: .92, easing: "ease-out" },
         { transform: at(b.y, 1.5, 1.5), opacity: 0, offset: 1 }];
    const anim = d.animate(frames, { duration, fill: "forwards" });
    anim.onfinish = () => { d.remove(); if (target.isConnected) splash(target); };   // a step chosen again meanwhile has redrawn the list: nothing to land on
    anim.oncancel = () => d.remove();
  }
  function render(animate) {
    const sc = $("tourScene");
    const oldFi = document.querySelector("#tourSteps li.on .fi"), from = shown, a = oldFi && centerOf(oldFi);
    landing = !!(animate && !reduced && from !== null && from !== at && a);
    sc.innerHTML = `<div class="ts-step${animate && !reduced ? " enter" : ""}"><span class="ts-n">${L(`الخطوة ${D(at + 1)} من ${D(STEPS.length)}`, `Step ${at + 1} of ${STEPS.length}`)}</span>${STEPS[at].scene()}</div>`;
    renderSteps(); rail();
    if (landing) {
      const b = document.querySelector("#tourSteps li.on .fi"), to = b && centerOf(b);
      if (to) dropTo(a, to, at > from, b);   // the new circle was drawn empty (in renderSteps) and fills only when the drop reaches it
      else if (b) b.classList.remove("waiting");
    }
    landing = false;
    shown = at;
    const last = at === STEPS.length - 1;
    $("tourNext").textContent = last ? L("جرّبه على نصك", "Try it on your text") : L("التالي", "Next");
    $("tourBack").textContent = at === 0 ? L("الخطوة الأخيرة", "Last step") : L("السابق", "Back");
  }
  function restart() {
    clearInterval(timer); timer = null;
    if (reduced || paused) return;  // no motion asked for: the steps change only by hand
    timer = setInterval(() => { if (active()) go((at + 1) % STEPS.length); }, DWELL);
  }
  function go(i, animate = true) { at = (i + STEPS.length) % STEPS.length; render(animate); }

  $("tour").addEventListener("click", ev => {
    const b = ev.target.closest("[data-step]");
    if (b) { go(+b.dataset.step); restart(); }
  });
  const pause = $("tourPause");
  const pauseLabel = () => { pause.textContent = paused ? L("شغّل الجولة", "Play tour") : L("أوقف الجولة", "Pause tour"); pause.setAttribute("aria-pressed", String(paused)); };
  pause.onclick = () => { paused = !paused; pauseLabel(); restart(); };
  pauseLabel();
  $("tour").addEventListener("focusin", () => { paused = true; pauseLabel(); restart(); });
  $("tourBack").onclick = () => { go(at - 1); restart(); };
  $("tourNext").onclick = () => {
    if (at === STEPS.length - 1) { const a = document.querySelector('[data-view="review"]'); if (a) a.click(); return; }
    go(at + 1); restart();
  };
  $("tour").addEventListener("keydown", ev => {
    const fwd = en() ? "ArrowRight" : "ArrowLeft", back = en() ? "ArrowLeft" : "ArrowRight";
    if (ev.key === fwd) { go(at + 1); restart(); ev.preventDefault(); }
    if (ev.key === back) { go(at - 1); restart(); ev.preventDefault(); }
  });

  window.addEventListener("resize", () => rail());
  document.addEventListener("manba:lang", () => { render(false); pauseLabel(); });
  document.addEventListener("manba:view", ev => { if (ev.detail === "how") { go(0, false); restart(); } else { clearInterval(timer); timer = null; } });
  render(false);
  if (!$("howView").hidden) restart();
})();
