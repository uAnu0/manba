/* Scan a PDF or image into the claim box (test console).
   - A PDF page that has its own text layer is read directly in the browser (pdf.js): no OCR, nothing uploaded.
   - Any other page (a scan, a photo, an image file) is shrunk in the browser and sent to /api/ocr, where two different models read it.
     Words on which the two readings differ are listed so the person can check them against the page.
   - At most 3 pages; the 500-word limit stays the real limit: the person chooses which pages to keep, then edits the text freely.
   Nothing is stored. Usage: Ocr.mount(container, { textarea, headers: () => ({...}) }). */
const Ocr = (() => {
  const MAX_PAGES = 3, MAX_SIDE = 1800, WORD_LIMIT = 500, MIN_LAYER_LETTERS = 15;
  const PDFJS = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js";
  const PDFJS_WORKER = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";
  const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const words = t => (String(t || "").trim().match(/\S+/g) || []).length;
  const short = t => { const w = String(t || "").split(/\s+/).filter(Boolean); return w.length > 14 ? w.slice(0, 14).join(" ") + " … (" + w.length + " words)" : t; };  // display only: replacing uses the full text

  let pdfLoading = null;
  function loadPdfJs() {
    if (window.pdfjsLib) return Promise.resolve();
    return pdfLoading || (pdfLoading = new Promise((resolve, reject) => {
      const s = document.createElement("script"); s.src = PDFJS;
      s.onload = () => { window.pdfjsLib.GlobalWorkerOptions.workerSrc = PDFJS_WORKER; resolve(); };
      s.onerror = () => { pdfLoading = null; reject(new Error("Could not load the PDF reader (pdf.js): check the connection.")); };
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
    const ta = opts.textarea; let pages = [], busy = false, edited = false, composing = false;
    root.classList.add("ocr");
    root.innerHTML = `<div class="ocr-bar"><button type="button" class="ocr-pick">Scan a PDF or image · مسح ملف</button>
      <label class="small">first page <input type="number" class="ocr-first" min="1" value="1" style="width:4.5em"></label>
      <button type="button" class="ocr-clear" hidden>Clear scan</button><span class="small ocr-status"></span></div>
      <input type="file" class="ocr-file" accept="application/pdf,.pdf,image/png,image/jpeg,image/webp" multiple hidden>
      <div class="small ocr-help">Up to ${MAX_PAGES} pages. The ${WORD_LIMIT}-word limit still applies: keep the pages you want, then edit the text.</div><div class="ocr-pages"></div>`;
    const $ = sel => root.querySelector(sel), list = $(".ocr-pages"), input = $(".ocr-file"), status = $(".ocr-status");
    const headers = () => Object.assign({ "Content-Type": "application/json" }, opts.headers ? opts.headers() : {});
    ta.addEventListener("input", () => { if (!composing && pages.length) edited = true; });

    function compose() {
      const parts = pages.filter(p => p.include && p.text).map(p => p.text);
      composing = true; ta.value = parts.join("\n\n"); ta.dispatchEvent(new Event("input")); composing = false; edited = false; summary();
    }
    function summary() {
      const n = words(ta.value), el = $(".ocr-total"); if (!el) return;
      el.textContent = `In the box: ${n} / ${WORD_LIMIT} words`; el.style.color = n > WORD_LIMIT ? "#b00020" : "";
    }
    ta.addEventListener("input", summary);

    function draw() {
      $(".ocr-clear").hidden = !pages.length;
      list.innerHTML = pages.map((p, i) => `<div class="ocr-page" data-i="${i}">
        <img class="ocr-thumb" src="${p.thumb}" alt="page ${p.label}" title="Click to enlarge or shrink">
        <div class="ocr-main"><div><b>${esc(p.label)}</b> <span class="chip ${p.source === "ocr" ? "warn" : "blue"}">${p.source === "ocr" ? "OCR · read by two models" : p.source === "layer" ? "text layer" : "…"}</span>
          <span class="small">${p.text ? words(p.text) + " words" : ""}</span></div>
          ${p.error ? `<div class="err">${esc(p.error)}</div>` : ""}
          ${p.text ? `<label class="small"><input type="checkbox" class="ocr-include" ${p.include ? "checked" : ""}> keep this page in the box</label>` : ""}
          ${p.source === "layer" ? `<button type="button" class="ocr-reread small">Read it as an image instead</button>` : ""}
          ${p.note ? `<div class="small">${esc(p.note)}</div>` : ""}
          ${(p.diffs || []).length ? `<details open class="ocr-diffs"><summary class="small">${p.diffs.length} place(s) where the two readings differ: check them against the page</summary>${p.diffs.map((d, k) => `<div class="ocr-diff" dir="rtl" data-k="${k}"><span class="small">…${esc(d.before)}</span> <mark>${esc(short(d.a)) || "(nothing)"}</mark> <span class="small">|</span> <mark class="b">${esc(short(d.b)) || "(nothing)"}</mark> <span class="small">${esc(d.after)}…</span> <button type="button" class="ocr-useb small">use the second reading</button></div>`).join("")}</details>` : ""}
        </div></div>`).join("") + (pages.length ? `<div class="small">This text was read from a scan: a word that differs from a verse or hadith may be a reading error, not a misquote.</div>` : "");
      summary();
    }

    async function ocr(p) {
      p.source = "ocr"; p.error = null; draw();
      const res = await fetch("/api/ocr", { method: "POST", headers: headers(), body: JSON.stringify({ image: jpeg(p.canvas), page: p.n || 1 }) });
      const d = await res.json().catch(() => ({}));
      if (res.status === 401) throw new Error("The server needs an access code: enter it in Settings.");
      if (!res.ok) throw new Error(typeof d.detail === "string" ? d.detail : "The page could not be read (" + res.status + ").");
      p.text = d.text; p.diffs = d.diffs || []; p.note = d.note || null;
    }

    async function run(files) {
      if (busy) return; busy = true; pages = []; edited = false; draw();
      try {
        const start = Math.max(1, parseInt($(".ocr-first").value, 10) || 1), jobs = []; let info = "";
        for (const f of files) {
          if (jobs.length >= MAX_PAGES) break;
          if (f.type === "application/pdf" || /\.pdf$/i.test(f.name)) {
            status.textContent = "Opening the PDF…"; await loadPdfJs();
            const pdf = await window.pdfjsLib.getDocument({ data: await f.arrayBuffer() }).promise;
            const last = Math.min(pdf.numPages, start + (MAX_PAGES - jobs.length) - 1);
            for (let n = start; n <= last; n++) jobs.push({ kind: "pdf", pdf, n, name: f.name });
            if (pdf.numPages > last || start > 1) info = `${f.name}: ${pdf.numPages} pages in all; reading ${start}–${Math.max(start, last)} (the limit is ${MAX_PAGES} pages: change “first page” for others).`;
          } else if (/^image\//.test(f.type)) jobs.push({ kind: "image", file: f, name: f.name });
        }
        if (!jobs.length) throw new Error("Choose a PDF or an image (PNG, JPEG, WebP).");
        for (const j of jobs) {
          const p = { label: j.kind === "pdf" ? `${j.name} · page ${j.n}` : j.name, n: j.n || 1, thumb: "", text: "", source: "…", include: false, diffs: [], note: null, error: null };
          pages.push(p); status.textContent = `Reading ${p.label}…`; draw();
          try {
            if (j.kind === "pdf") {
              const page = await j.pdf.getPage(j.n); p.canvas = await pdfCanvas(page); p.thumb = thumbOf(p.canvas);
              const t = await layerText(page);
              if (hasLayer(t)) { p.text = t; p.source = "layer"; }
              else { if (t.trim()) p.note = "The PDF has a text layer but it is garbled, so the page was read as an image."; await ocr(p); }
            } else { p.canvas = await imageCanvas(j.file); p.thumb = thumbOf(p.canvas); await ocr(p); }
          } catch (e) { p.error = e.message; if (!p.thumb && p.canvas) p.thumb = thumbOf(p.canvas); p.source = p.source === "…" ? "ocr" : p.source; }
          draw();
        }
        // keep pages, in order, while they fit the limit (the first page is always kept so it can be trimmed)
        let total = 0;
        pages.forEach((p, i) => { const w = words(p.text); if (p.text && (i === 0 || total + w <= WORD_LIMIT)) { p.include = true; total += w; } });
        compose(); draw(); status.textContent = info || "Done. Check the text, then press Check claim.";
      } catch (e) { status.textContent = ""; list.innerHTML = `<div class="err">${esc(e.message)}</div>`; }
      finally { busy = false; input.value = ""; }
    }

    $(".ocr-pick").onclick = () => input.click();
    input.onchange = () => run([...input.files]);
    $(".ocr-clear").onclick = () => { pages = []; draw(); list.innerHTML = ""; status.textContent = ""; };
    list.addEventListener("click", async ev => {
      const el = ev.target.closest(".ocr-page"); if (!el) return; const p = pages[+el.dataset.i];
      if (ev.target.closest(".ocr-thumb")) { el.classList.toggle("big"); return; }
      if (ev.target.closest(".ocr-include")) {
        if (edited && !confirm("You edited the text in the box. Changing the pages will replace your edits. Continue?")) { draw(); return; }
        p.include = ev.target.closest(".ocr-include").checked; compose(); return;
      }
      if (ev.target.closest(".ocr-reread")) {
        try { status.textContent = "Reading " + p.label + " as an image…"; await ocr(p); } catch (e) { p.error = e.message; }
        if (p.include) compose(); draw(); status.textContent = ""; return;
      }
      const use = ev.target.closest(".ocr-useb");
      if (use) {
        const d = p.diffs[+use.closest(".ocr-diff").dataset.k], base = [d.before, d.a, d.after].filter(Boolean).join(" "), repl = [d.before, d.b, d.after].filter(Boolean).join(" ");
        const swap = s => s.indexOf(base) >= 0 ? s.replace(base, repl) : null, a = swap(ta.value);
        if (a == null) { alert("That part of the text was edited, so it can't be replaced automatically."); return; }
        composing = true; ta.value = a; ta.dispatchEvent(new Event("input")); composing = false; summary();
        const b = swap(p.text); if (b != null) p.text = b;
        use.closest(".ocr-diff").style.opacity = .5; use.disabled = true;
      }
    });
  }
  return { mount };
})();
