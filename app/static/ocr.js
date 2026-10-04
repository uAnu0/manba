/* Scan a PDF or image into the text box (used by the reviewer page "/" in Arabic and by the test console "/claim" in English).
   - A PDF page that has its own text layer is read directly in the browser (pdf.js): no OCR, nothing uploaded.
   - Any other page (a scan, a photo, an image file) is shrunk in the browser and sent to /api/ocr, where two different models read it.
     Words on which the two readings differ are listed so the person can check them against the page.
   - Up to 10 pages are shown as thumbnails and the person ticks the ones to keep; only ticked pages are read (a scanned page goes to the
     models when it is ticked, so unticked pages cost nothing). The 500-word limit stays the real limit: ticking stops when it is reached
     (a page that would pass it is refused, with its words shown), then the person edits the text freely.
   Nothing is stored. Usage: Ocr.mount(container, { textarea, headers: () => ({...}), lang: "ar" | "en", onReview: () => {...} }). */
const Ocr = (() => {
  const MAX_PAGES = 10, MAX_SIDE = 1800, WORD_LIMIT = 500, MIN_LAYER_LETTERS = 15;
  const PDFJS = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js";
  const PDFJS_WORKER = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";
  const arDigits = n => String(n).replace(/\d/g, d => "٠١٢٣٤٥٦٧٨٩"[d]);

  // Every sentence the person reads, in both languages. The warning is the one the team asked for, shown next to the box and on the results.
  const WARNING_EN = "Read from a scan; the reader may have filled in unclear words from context; check every word against the picture.";
  const WARNING_AR = "قُرئ هذا النص من مسح ضوئي؛ وقد يكون القارئ أكمل كلمات غير واضحة من السياق، فتحقّق من كل كلمة بمقارنتها بالصورة.";
  const STR = {
    en: {
      pick: "Scan a PDF or image · مسح ملف", firstPage: "first page", clear: "Clear scan", edit: "View and edit the text",
      help: () => `Up to ${MAX_PAGES} pages are shown. Tick the pages you want: a scanned page is read only when you tick it, until the ${WORD_LIMIT}-word limit is reached. Then edit the text.`,
      count: n => `Selected: ${n} of ${WORD_LIMIT} words`, pickPages: n => `${n} pages found: tick the pages you want to check (a scanned page is read when you tick it).`,
      scanChip: "scanned page · read when ticked", busyPage: "Reading this page…", preparing: l => `Preparing ${l}…`,
      refused: w => `This page has ${w} words and does not fit in the ${WORD_LIMIT}-word limit with the pages already ticked: untick another page first.`,
      full: "The limit is reached: untick another page first.", over: `This page alone is over ${WORD_LIMIT} words: keep it, then cut the text in the box.`,
      thumb: "Click to enlarge or shrink", ocrChip: "OCR · read by two models", layerChip: "text layer", words: n => `${n} words`,
      keep: "keep this page in the box", reread: "Read it as an image instead",
      diffs: n => `${n} place(s) where the two readings differ: check them against the page`, nothing: "(nothing)", useB: "use the second reading",
      pdfFail: "Could not load the PDF reader (pdf.js): check the connection.", noAccess: "The server needs an access code: enter it in Settings.",
      unreadable: c => `The page could not be read (${c}).`, opening: "Opening the PDF…", choose: "Choose a PDF or an image (PNG, JPEG, WebP).",
      page: (name, n) => `${name} · page ${n}`, reading: l => `Reading ${l}…`, rereading: l => `Reading ${l} as an image…`,
      garbled: "The PDF has a text layer but it is garbled, so the page was read as an image.", done: "Done. Check the text, then press Check claim.",
      info: (name, total, a, b) => `${name}: ${total} pages in all; showing ${a}–${b} (up to ${MAX_PAGES} pages are shown at once: change “first page” for others).`,
      confirmEdits: "You edited the text in the box. Changing the pages will replace your edits. Continue?",
      cantReplace: "That part of the text was edited, so it can't be replaced automatically.", warning: WARNING_EN, warningOther: WARNING_AR, warningOtherDir: "rtl",
    },
    ar: {
      pick: "مسح ملف PDF أو صورة", firstPage: "أول صفحة", clear: "إزالة المسح", edit: "عرض النص وتعديله",
      help: () => `تُعرض حتى ${arDigits(MAX_PAGES)} صفحات. حدّد الصفحات التي تريدها: لا تُقرأ الصفحة الممسوحة إلا عند تحديدها، إلى أن يكتمل حدّ ${arDigits(WORD_LIMIT)} كلمة. ثم عدّل النص.`,
      count: n => `المحدَّد: ${arDigits(n)} من ${arDigits(WORD_LIMIT)} كلمة`, pickPages: n => `وُجدت ${arDigits(n)} صفحات: حدّد الصفحات التي تريد مراجعتها (تُقرأ الصفحة الممسوحة عند تحديدها).`,
      scanChip: "صفحة ممسوحة · تُقرأ عند تحديدها", busyPage: "جارٍ قراءة هذه الصفحة…", preparing: l => `جارٍ تجهيز ${l}…`,
      refused: w => `في هذه الصفحة ${arDigits(w)} كلمة ولا تتّسع مع الصفحات المحدَّدة في حدّ ${arDigits(WORD_LIMIT)} كلمة: ألغِ تحديد صفحة أخرى أولًا.`,
      full: "اكتمل الحد: ألغِ تحديد صفحة أخرى أولًا.", over: `هذه الصفحة وحدها أكثر من ${arDigits(WORD_LIMIT)} كلمة: أبقها ثم اقتطع من النص في الخانة.`,
      thumb: "اضغط للتكبير أو التصغير", ocrChip: "قراءة آلية بنموذجين", layerChip: "نص مضمَّن في الملف", words: n => `${arDigits(n)} كلمة`,
      keep: "إبقاء هذه الصفحة في النص", reread: "قراءتها كصورة بدلًا من ذلك",
      diffs: n => `${arDigits(n)} موضع اختلفت فيه القراءتان: قارنه بالصفحة`, nothing: "(لا شيء)", useB: "اعتمد القراءة الثانية",
      pdfFail: "تعذّر تحميل قارئ PDF (pdf.js). تحقق من الاتصال.", noAccess: "الخادم يطلب رمز دخول: أدخله من الإعدادات.",
      unreadable: c => `تعذّرت قراءة الصفحة (${arDigits(c)}).`, opening: "جارٍ فتح ملف PDF…", choose: "اختر ملف PDF أو صورة (PNG أو JPEG أو WebP).",
      page: (name, n) => `${name} · صفحة ${arDigits(n)}`, reading: l => `جارٍ قراءة ${l}…`, rereading: l => `جارٍ قراءة ${l} كصورة…`,
      garbled: "في ملف PDF طبقة نصية لكنها مشوّهة، فقُرئت الصفحة كصورة.", done: "تمّ. راجع النص ثم اضغط «راجع النص».",
      info: (name, total, a, b) => `${name}: ${arDigits(total)} صفحة في الملف؛ تُعرض الصفحات ${arDigits(a)}–${arDigits(b)} (تُعرض حتى ${arDigits(MAX_PAGES)} صفحات دفعة واحدة: غيّر «أول صفحة» لعرض غيرها).`,
      confirmEdits: "عدّلتَ النص في الخانة. تغيير الصفحات سيستبدل تعديلاتك. أتتابع؟",
      cantReplace: "عُدِّل هذا الموضع من النص، فلا يمكن استبداله تلقائيًا.", warning: WARNING_AR, warningOther: WARNING_EN, warningOtherDir: "ltr",
    },
  };
  let lang = "en";
  const warningHtml = () => { const t = STR[lang]; return `<div class="banner scan-warning" role="note"><b>${t.warning}</b><span dir="${t.warningOtherDir}" style="display:block;margin-top:4px">${t.warningOther}</span></div>`; };

  // true while the text in the box still comes (mostly) from a page that a model read from an image; see active()
  let scanActive = false, composed = new Set(), boxEl = null;
  const wordList = t => String(t || "").split(/\s+/).filter(Boolean);
  const active = () => {
    if (!scanActive || !boxEl) return false;
    const w = wordList(boxEl.value); if (!w.length) return false;
    return w.filter(x => composed.has(x)).length / w.length >= 0.5;  // a sample or a text file loaded afterwards replaces the text: no stale warning
  };

  const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const words = t => wordList(t).length;
  const short = t => { const w = wordList(t); return w.length > 14 ? w.slice(0, 14).join(" ") + " … (" + w.length + ")" : t; };  // display only: replacing uses the full text

  let pdfLoading = null;
  function loadPdfJs() {
    if (window.pdfjsLib) return Promise.resolve();
    return pdfLoading || (pdfLoading = new Promise((resolve, reject) => {
      const s = document.createElement("script"); s.src = PDFJS;
      s.onload = () => { window.pdfjsLib.GlobalWorkerOptions.workerSrc = PDFJS_WORKER; resolve(); };
      s.onerror = () => { pdfLoading = null; reject(new Error(STR[lang].pdfFail)); };
      document.head.appendChild(s);
    }));
  }

  // ---- getting a page as text or as a picture ----
  const tidy = t => t.normalize("NFKC").replace(/[ \t ]+/g, " ").replace(/ ?\n ?/g, "\n").replace(/\n{3,}/g, "\n\n").trim();  // NFKC folds Arabic presentation forms back to letters
  async function layerText(page) {
    const tc = await page.getTextContent(); let out = "";
    for (const it of tc.items) out += it.str + (it.hasEOL ? "\n" : " ");
    return tidy(out);
  }
  // A text layer is trusted only if it reads like text. Some Arabic PDFs (old fonts, scans passed through a bad OCR) carry a layer of single
  // spaced letters or stray glyphs ("إ ن م ا ا ƾ ع م ا ل"): that is read as an image instead.
  function hasLayer(t) {
    const rng = (a, b) => String.fromCharCode(a) + "-" + String.fromCharCode(b);   // ranges built from numbers: no invisible characters in the source
    const arabic = new RegExp("[" + rng(0x600, 0x6FF) + "]", "g");
    const stray = new RegExp("[" + rng(0x100, 0x24F) + rng(0x1E00, 0x1EFF) + rng(0xE000, 0xF8FF) + String.fromCharCode(0xFFFD) + "]", "g");  // Latin Extended, private use, replacement char
    const letters = (t.match(arabic) || []).length, latin = (t.match(/[A-Za-z]/g) || []).length;
    if (letters < MIN_LAYER_LETTERS && latin < 40) return false;
    const tokens = t.split(/\s+/).filter(Boolean), single = tokens.filter(w => w.length === 1).length / Math.max(1, tokens.length);
    return single < 0.35 && (t.match(stray) || []).length / Math.max(1, t.length) < 0.01;
  }
  function blank(w, h) { const c = document.createElement("canvas"); c.width = Math.max(1, Math.round(w)); c.height = Math.max(1, Math.round(h)); const x = c.getContext("2d"); x.fillStyle = "#fff"; x.fillRect(0, 0, c.width, c.height); return c; }
  async function pdfCanvas(page) {
    const v0 = page.getViewport({ scale: 1 }), scale = Math.min(3, MAX_SIDE / Math.max(v0.width, v0.height)), vp = page.getViewport({ scale });
    const c = blank(vp.width, vp.height);
    // intent "print" does not wait for animation frames, which a background tab never gets: the scan keeps going if the person switches tabs
    await page.render({ canvasContext: c.getContext("2d"), viewport: vp, intent: "print" }).promise; return c;
  }
  async function imageCanvas(file) {
    const bmp = await createImageBitmap(file), k = Math.min(1, MAX_SIDE / Math.max(bmp.width, bmp.height));
    const c = blank(bmp.width * k, bmp.height * k); c.getContext("2d").drawImage(bmp, 0, 0, c.width, c.height); return c;
  }
  const thumbOf = c => { const k = Math.min(1, 360 / c.width), t = blank(c.width * k, c.height * k); t.getContext("2d").drawImage(c, 0, 0, t.width, t.height); return t.toDataURL("image/jpeg", 0.7); };
  function jpeg(c) { let q = 0.85, d = c.toDataURL("image/jpeg", q); while (d.length * 0.75 > 2.8e6 && q > 0.4) { q -= 0.15; d = c.toDataURL("image/jpeg", q); } return d; }

  function mount(root, opts) {
    const ta = opts.textarea; boxEl = ta; lang = opts.lang === "ar" ? "ar" : "en"; const T = STR[lang];
    let pages = [], busy = false, edited = false, composing = false;
    root.classList.add("ocr");
    root.innerHTML = `<div class="ocr-bar"><button type="button" class="ocr-pick btn">${T.pick}</button>
      <label class="small cap">${T.firstPage} <input type="number" class="ocr-first" min="1" value="1" style="width:4.5em"></label>
      <button type="button" class="ocr-clear btn small" hidden>${T.clear}</button>${opts.onReview ? `<button type="button" class="ocr-edit btn small" hidden>${T.edit}</button>` : ""}<span class="small cap ocr-status" role="status"></span></div>
      <input type="file" class="ocr-file" accept="application/pdf,.pdf,image/png,image/jpeg,image/webp" multiple hidden>
      <div class="small cap ocr-help">${T.help()}</div><div class="small cap ocr-count" role="status"></div><div class="ocr-pages"></div>`;
    const $ = sel => root.querySelector(sel), list = $(".ocr-pages"), input = $(".ocr-file"), status = $(".ocr-status");
    const headers = () => Object.assign({ "Content-Type": "application/json" }, opts.headers ? opts.headers() : {});
    ta.addEventListener("input", () => { if (!composing && pages.length) edited = true; if (!ta.value.trim()) scanActive = false; });

    function compose() {
      const parts = pages.filter(p => p.include && p.text).map(p => p.text), text = parts.join("\n\n");
      composing = true; ta.value = text; ta.dispatchEvent(new Event("input")); composing = false; edited = false;
      composed = new Set(wordList(text));
      scanActive = pages.some(p => p.include && p.text && p.source === "ocr");
    }

    // words in the pages that are ticked; a page can be ticked only while the total stays within the limit (a page alone over it is allowed when nothing else is ticked, so it can be trimmed)
    const picked = () => pages.filter(p => p.include && p.text).reduce((n, p) => n + words(p.text), 0);
    const fits = p => p.include || picked() === 0 || (p.text ? picked() + words(p.text) <= WORD_LIMIT : picked() < WORD_LIMIT);  // an unread scan has no word count yet: it is checked once read

    function draw() {
      $(".ocr-clear").hidden = !pages.length;
      const n = picked(); $(".ocr-count").innerHTML = pages.length ? `<b>${T.count(n)}</b>` : "";
      if ($(".ocr-edit")) $(".ocr-edit").hidden = !pages.some(p => p.text);
      list.innerHTML = (pages.some(p => p.source === "ocr" && p.text) ? warningHtml() : "") + pages.map((p, i) => `<div class="ocr-page${p.big ? " big" : ""}" data-i="${i}">
        <img class="ocr-thumb" src="${p.thumb}" alt="${esc(p.label)}" title="${T.thumb}">
        <div class="ocr-main"><div><b>${esc(p.label)}</b> <span class="chip ${p.source === "ocr" || p.source === "scan" ? "warn" : "blue"}">${p.source === "ocr" ? T.ocrChip : p.source === "layer" ? T.layerChip : p.source === "scan" ? T.scanChip : "…"}</span>
          <span class="small cap">${p.text ? T.words(words(p.text)) : ""}</span></div>
          ${p.error ? `<div class="err">${esc(p.error)}</div>` : ""}
          ${p.error || p.source === "…" ? "" : `<label class="small cap"><input type="checkbox" class="ocr-include" ${p.include ? "checked" : ""} ${fits(p) && !p.loading ? "" : "disabled"}> ${T.keep}</label>${p.loading ? ` <span class="small cap">${T.busyPage}</span>` : fits(p) || p.refused ? "" : ` <span class="small cap">${T.full}</span>`}${p.include && words(p.text) > WORD_LIMIT ? ` <span class="small cap">${T.over}</span>` : ""}`}
          ${p.refused ? `<div class="small cap">${T.refused(words(p.text))}</div>` : ""}
          ${p.source === "layer" ? `<button type="button" class="ocr-reread btn small">${T.reread}</button>` : ""}
          ${p.note ? `<div class="small cap">${esc(p.note)}</div>` : ""}
          ${(p.diffs || []).length ? `<details open class="ocr-diffs"><summary class="small cap">${T.diffs(p.diffs.length)}</summary>${p.diffs.map((d, k) => `<div class="ocr-diff" dir="rtl" data-k="${k}"><span class="small cap">…${esc(d.before)}</span> <mark>${esc(short(d.a)) || T.nothing}</mark> <span class="small cap">|</span> <mark class="b">${esc(short(d.b)) || T.nothing}</mark> <span class="small cap">${esc(d.after)}…</span> <button type="button" class="ocr-useb btn small">${T.useB}</button></div>`).join("")}</details>` : ""}
        </div></div>`).join("");
    }

    // the full-size picture is made only when a page is read, then dropped: ten pages are never held in memory at once
    async function canvasOf(p) { return p.pdf ? pdfCanvas(await p.pdf.getPage(p.n)) : imageCanvas(p.file); }
    async function ocr(p) {
      p.source = "ocr"; p.error = null; draw();
      const res = await fetch("/api/ocr", { method: "POST", headers: headers(), body: JSON.stringify({ image: jpeg(await canvasOf(p)), page: p.n || 1 }) });
      const d = await res.json().catch(() => ({}));
      if (res.status === 401) throw new Error(T.noAccess);
      if (!res.ok) throw new Error(typeof d.detail === "string" ? d.detail : T.unreadable(res.status));
      p.text = d.text; p.diffs = d.diffs || []; p.note = d.note || null;
    }

    // a scanned page is read when it is ticked; if it does not fit with the pages already ticked it is un-ticked (its text is kept, so ticking it again later costs nothing)
    async function tick(p, on) {
      p.include = on; p.refused = false;
      if (on && !p.text && p.source === "scan") {
        p.loading = true; draw();
        try { await ocr(p); } catch (e) { p.error = e.message; p.include = false; p.source = "scan"; }
        p.loading = false;
        if (p.include && picked() - words(p.text) > 0 && picked() > WORD_LIMIT) { p.include = false; p.refused = true; }
      }
      compose(); draw();
    }

    async function run(files) {
      if (busy) return; busy = true; pages = []; edited = false; draw();
      try {
        const start = Math.max(1, parseInt($(".ocr-first").value, 10) || 1), jobs = []; let info = "";
        for (const f of files) {
          if (jobs.length >= MAX_PAGES) break;
          if (f.type === "application/pdf" || /\.pdf$/i.test(f.name)) {
            status.textContent = T.opening; await loadPdfJs();
            const pdf = await window.pdfjsLib.getDocument({ data: await f.arrayBuffer() }).promise;
            const last = Math.min(pdf.numPages, start + (MAX_PAGES - jobs.length) - 1);
            for (let n = start; n <= last; n++) jobs.push({ kind: "pdf", pdf, n, name: f.name });
            if (pdf.numPages > last || start > 1) info = T.info(f.name, pdf.numPages, start, Math.max(start, last));
          } else if (/^image\//.test(f.type)) jobs.push({ kind: "image", file: f, name: f.name });
        }
        if (!jobs.length) throw new Error(T.choose);
        for (const j of jobs) {
          const p = { label: j.kind === "pdf" ? T.page(j.name, j.n) : j.name, n: j.n || 1, pdf: j.pdf, file: j.file, thumb: "", text: "", source: "…", include: false, loading: false, refused: false, diffs: [], note: null, error: null };
          pages.push(p); status.textContent = T.preparing(p.label); draw();
          try {   // only a thumbnail and the page's own text layer (if it has one) are made here: nothing is sent anywhere yet
            if (j.kind === "pdf") {
              const page = await j.pdf.getPage(j.n); p.thumb = thumbOf(await pdfCanvas(page));
              const t = await layerText(page);
              if (hasLayer(t)) { p.text = t; p.source = "layer"; } else { if (t.trim()) p.note = T.garbled; p.source = "scan"; }
            } else { p.thumb = thumbOf(await imageCanvas(j.file)); p.source = "scan"; }
          } catch (e) { p.error = e.message; p.source = "scan"; }
          draw();
        }
        // a single page, or text-layer pages that all fit in the limit, are ticked for the person; otherwise the person chooses from the thumbnails
        const layered = pages.every(p => p.source === "layer"), all = pages.reduce((n, p) => n + words(p.text), 0), ask = pages.length > 1 && !(layered && all <= WORD_LIMIT);
        status.textContent = [info, ask ? T.pickPages(pages.length) : T.done].filter(Boolean).join(" ");
        if (!ask) { for (const p of pages.filter(q => !q.error)) await tick(p, true); } else draw();
      } catch (e) { status.textContent = ""; list.innerHTML = `<div class="err">${esc(e.message)}</div>`; }
      finally { busy = false; input.value = ""; }
    }

    $(".ocr-pick").onclick = () => input.click();
    input.onchange = () => run([...input.files]);
    $(".ocr-clear").onclick = () => { pages = []; scanActive = false; draw(); list.innerHTML = ""; status.textContent = ""; };
    if ($(".ocr-edit")) $(".ocr-edit").onclick = () => opts.onReview();
    list.addEventListener("click", async ev => {
      const el = ev.target.closest(".ocr-page"); if (!el) return; const p = pages[+el.dataset.i];
      if (ev.target.closest(".ocr-thumb")) { p.big = !p.big; el.classList.toggle("big", p.big); return; }
      if (ev.target.closest(".ocr-include")) {
        if (edited && !confirm(T.confirmEdits)) { draw(); return; }
        await tick(p, ev.target.closest(".ocr-include").checked); return;
      }
      if (ev.target.closest(".ocr-reread")) {
        try { status.textContent = T.rereading(p.label); await ocr(p); } catch (e) { p.error = e.message; }
        if (p.include) compose(); draw(); status.textContent = ""; return;
      }
      const use = ev.target.closest(".ocr-useb");
      if (use) {
        const d = p.diffs[+use.closest(".ocr-diff").dataset.k], base = [d.before, d.a, d.after].filter(Boolean).join(" "), repl = [d.before, d.b, d.after].filter(Boolean).join(" ");
        const swap = s => s.indexOf(base) >= 0 ? s.replace(base, repl) : null, a = swap(ta.value);
        if (a == null) { alert(T.cantReplace); return; }
        composing = true; ta.value = a; ta.dispatchEvent(new Event("input")); composing = false;
        wordList(a).forEach(w => composed.add(w));
        const b = swap(p.text); if (b != null) p.text = b;
        use.closest(".ocr-diff").style.opacity = .5; use.disabled = true;
      }
    });
  }
  return { mount, active, warningHtml };
})();
