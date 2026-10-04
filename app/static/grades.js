/* Shared by the reviewer page (app.js) and the developer pages (cards.js): how a hadith's grading and a verse's context are
   shown. Nothing here grades a hadith: it renders the gradings the dataset holds (fawazahmed0/hadith-api, the Unlicense),
   names the grader, and says plainly when our data has no grading. */
(() => {
  const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const GRADER = {
    "Al-Albani": "الألباني", "Zubair Ali Zai": "زبير علي زئي", "Shuaib Al Arnaut": "شعيب الأرناؤوط", "Abu Ghuddah": "عبد الفتاح أبو غدة",
    "Muhammad Muhyi Al-Din Abdul Hamid": "محمد محيي الدين عبد الحميد", "Muhammad Fouad Abd al-Baqi": "محمد فؤاد عبد الباقي",
    "Ahmad Muhammad Shakir": "أحمد شاكر", "Bashar Awad Maarouf": "بشار عواد معروف", "Salim al-Hilali": "سليم الهلالي",
  };

  // "Isnaad Sahih" -> "إسناده صحيح", "Sahih Lighairihi" -> "صحيح لغيره", "Mauquf Daif" -> "ضعيف · موقوف",
  // "Sahih - Agreed Upon" -> "صحيح · متفق عليه". Anything not recognised is shown as written.
  function gradeAr(g) {
    const t = String(g || "").toLowerCase();
    const core = /mawdu|fabricat/.test(t) ? "موضوع" : /batil/.test(t) ? "باطل" : /very da/.test(t) ? "ضعيف جدًا"
      : /munkar/.test(t) ? "منكر" : /shadh/.test(t) ? "شاذ" : /hasan sahih/.test(t) ? "حسن صحيح"
      : /da[ie]i?f/.test(t) ? "ضعيف" : /sahih/.test(t) ? "صحيح" : /hasan/.test(t) ? "حسن" : "";
    if (!core) return String(g || "").trim() || "—";
    let head = /isnaa?d|sanad/.test(t) ? `إسناده ${core}` : core;
    if (/lighairihi/.test(t)) head += " لغيره";
    const mods = [];
    if (/mauquf|muquf|mawquf/.test(t)) mods.push("موقوف");
    if (/maqtu/.test(t)) mods.push("مقطوع");
    if (/mursal/.test(t)) mods.push("مرسل");
    if (/mutawatir/.test(t)) mods.push("متواتر");
    if (/agreed upon|bukhari and muslim|bukhari.*muslim/.test(t)) mods.push("متفق عليه");
    else if (/bukhari/.test(t)) mods.push("أصله في البخاري");
    else if (/muslim/.test(t)) mods.push("أصله في مسلم");
    return [head, ...mods].join(" · ");
  }
  const kindOf = g => { const t = String(g || "").toLowerCase();
    return /mawdu|batil|very da|munkar/.test(t) ? "bad" : /da[ie]i?f|shadh/.test(t) ? "fix" : /sahih|hasan/.test(t) ? "ok" : "neu"; };

  const SAHIHAYN = new Set(["صحيح البخاري", "صحيح مسلم"]);
  const NO_GRADES = new Set(["مسند أحمد", "سنن الدارمي"]);
  const dorarLink = text => `https://dorar.net/hadith/search?q=${encodeURIComponent(String(text || "").slice(0, 120))}`;

  // cls(k): the page's CSS class for a verdict kind (ok | fix | bad | neu).
  function chips(s, cls, opts) {
    if (!s || s.book === "القرآن الكريم" || s.strength === "quran") return "";
    opts = opts || {};
    if (SAHIHAYN.has(s.book) || s.strength === "sahihayn")
      return `<span class="chip ${cls("ok")}" title="أحاديث الصحيحين تلقتها الأمة بالقبول، فلا يُذكر لها حكم محدّث فردي">في الصحيحين</span>`;
    const gs = (s.grades || []).filter(g => /[a-z\u0600-\u06FF]/i.test(g.grade || ""));
    if (!gs.length) {
      const why = NO_GRADES.has(s.book) ? `لا حكم في بياناتنا لأحاديث ${s.book}` : "لا حكم عليه في بياناتنا";
      return `<span class="chip ${cls("neu")}">${esc(why)}</span>${opts.text ? ` <a class="cap" href="${dorarLink(opts.text)}" target="_blank" rel="noopener">ابحث عن أحكامه في الدرر السنية</a>` : ""}`;
    }
    const shown = gs.slice(0, opts.max || 3);
    return shown.map(g => `<span class="chip ${cls(kindOf(g.grade))}" title="${esc(g.grade)} (${esc(g.name)})">${esc(gradeAr(g.grade))} · ${esc(GRADER[g.name] || g.name)}</span>`).join(" ")
      + (gs.length > shown.length ? ` <span class="cap">و${gs.length - shown.length} أحكام أخرى</span>` : "");
  }

  // A verse listed as evidence, with the tafsir line the API attached (context_ar), clamped with a "more" toggle.
  function context(item) {
    if (!item || !item.context_ar) return "";
    const t = item.context_ar, long = t.length > 260;
    return `<div class="ctx"><span class="cap">سياق الآية من ${esc(item.context_source || "التفسير")}:</span> <span class="ctx-t">${esc(long ? t.slice(0, 260) + "…" : t)}</span>${long ? ` <button class="link ctx-more" type="button" data-full="${esc(t)}">المزيد</button>` : ""}</div>`;
  }
  document.addEventListener("click", ev => {
    const b = ev.target.closest(".ctx-more");
    if (!b) return;
    b.previousElementSibling.textContent = b.dataset.full;
    b.remove();
  });

  window.ManbaGrades = { gradeAr, chips, context, GRADER };
})();
