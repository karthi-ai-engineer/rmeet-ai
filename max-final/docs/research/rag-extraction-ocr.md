# Extraction and OCR pipeline (research)

26 Nov 2026. Question: how should Max turn team files (docx, xlsx, pptx, pdf, scanned pages, images, charts) and
shared web links into good, searchable text? This replaces "MarkItDown only, no OCR" in `storage.md` §4.
**[unverified]** = I could not confirm it from a primary source.

## 1. Short answer

| Part | Pick | Why |
|---|---|---|
| Main extractor | **Docling** (IBM, MIT, v2.153, Python 3.10–3.14) | All our formats, layout + table models, page/slide locations, permissive weights |
| Fast path / fallback | **MarkItDown** (MIT) + `python-docx`/`openpyxl`/`python-pptx` (MIT), `pypdfium2` (Apache/BSD) | Office text without AI, milliseconds per file |
| OCR (local, default) | **RapidOCR** (Apache-2.0, ONNX, CPU) | 100% on our test page, ~3.6 s/page here, built into Docling |
| OCR / pictures (optional) | **Gemini flash-lite** on page images, behind a switch | Best for charts, handwriting, whiteboards; ~$1 per 1,000 pages |
| Web links | **trafilatura** (Apache-2.0, v2.4) + LLM brief | Clean main text, title and date |

All behind `extract(file)` and `ocr(image)`, so RapidOCR, Gemini or a company-server model swap without other changes.

## 2. Extraction libraries

| Library | Licence | Good at | Weak at | CPU speed |
|---|---|---|---|---|
| **Docling** | MIT; models Apache-2.0 / CDLA-permissive | Headings, reading order, **tables (TableFormer)**, all office formats, chart-to-table option | Heavy install (PyTorch), first run downloads models | ~1–3 s/page digital PDF, + ~2 s per table, + OCR time ([paper](https://arxiv.org/pdf/2501.17887)) |
| **MarkItDown** | MIT | Office files to Markdown, simple, small | Weak PDF layout, tables in PDFs become flat text; OCR only via an LLM plugin (`markitdown-ocr`, needs an OpenAI-style client) | Very fast |
| python-docx / openpyxl / python-pptx | MIT | Exact structure: headings, cells, slides, notes, alt text | You write the Markdown yourself | Very fast |
| pypdfium2 / pypdf / pdfplumber | Apache-BSD / BSD / MIT | Text layer, page numbers; pdfplumber finds simple ruled tables | No OCR, no layout model | Fast |
| Unstructured (open source) | Apache-2.0 | Many formats | `hi_res` ~20× slower; best layout model is proprietary ([docs](https://docs.unstructured.io/open-source/concepts/models)) | Slow |
**Licence flags (avoid unless legal approves):**

| Tool | Problem |
|---|---|
| **Marker** | Code was **GPL** until v2.0 (Jul 2026, now Apache). Its model weights use a modified OpenRAIL-M licence: paid above $5M revenue or funding |
| **Surya** | Same restricted weights licence as Marker (code Apache) |
| **MinerU** | Was **AGPL** (≤ 3.0.9); now a custom "Apache + extra terms" licence that ends automatically if terms are missed |
| PyMuPDF / pymupdf4llm | **AGPL** |

Source: [Particula, Sep 2026](https://particula.tech/blog/docling-vs-mineru-vs-marker-pdf-parser), [MarkTechPost, Jul 2026](https://www.marktechpost.com/2026/07/04/structured-pdf-to-json-a-guide-to-open-source-extraction-models-in-2026/)
**[unverified against the LICENSE files]**. Quality is strong (Marker, MinerU), but the licences are not worth it.

## 3. OCR options

| Option | Licence | CPU speed (this laptop) | Tables / charts / handwriting | Japanese |
|---|---|---|---|---|
| **RapidOCR** (PaddleOCR's models on ONNX, no Paddle runtime) | Apache-2.0 | **~3.6 s/page** (measured) | Text yes; table *structure* no (needs Docling's table model); handwriting weak | Yes (`japan` model) |
| Tesseract | Apache-2.0 | ~1–3 s/page **[unverified]**; needs a separate Windows install | Weak on noisy scans, no tables | Yes (`jpn`, `jpn_vert`) |
| docTR / OnnxTR | Apache-2.0 | **~1.7–2.6 s/page** (measured) | Text only | Latin-focused **[unverified]** |
| EasyOCR | Apache-2.0 | Slow on CPU (~13 s/page inside Docling, [paper](https://arxiv.org/pdf/2501.17887)) | Text only | Yes |
| **Gemini flash-lite** (page image) | API | 2–5 s per page, network **[unverified]**; can run many in parallel | **Best**: reads tables to Markdown, describes charts, reads handwriting and whiteboards | Yes |

**Gemini cost per page.** Gemini 3 bills an image at 560 tokens at `media_resolution: medium`, which Google says is
enough for OCR ([docs](https://aistudio.google.com/docs/media-resolution)). Price $0.25 / 1M input, $1.50 / 1M output
([Google](https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-3-1-flash-lite/)). A page ≈
660 tokens in + ~600 out ≈ **$0.001 per page ($1 per 1,000 pages)**; Batch API halves it **[batch price unverified]**.
Output tokens are the main cost, so cap them.

**Recommendation.** Local RapidOCR is the default: free, private, provider-neutral, good on printed text. Gemini
(or a company-server vision model later) is an **optional upgrade switch** for pages where local OCR has low confidence,
for charts, photos of whiteboards and handwriting.

## 4. Benchmark (done, on this laptop)

Generated an A4 page at 200 DPI with Pillow: title, 5 sentences, a 5×4 ruled table, then made it look scanned
(0.8° tilt, blur, grey, noise). Also a harder copy at 150 DPI with more noise. Model loading not counted.

| Engine | Page | Seconds / page | Characters right | Words found |
|---|---|---|---|---|
| RapidOCR 3.10 (default PP-OCRv6 small) | clean 200 DPI | 3.5–3.8 | 100% | 100% |
| RapidOCR 3.10 | degraded 150 DPI | 3.3–3.4 | 100% | 100% |
| OnnxTR 0.10 (docTR models on ONNX) | clean 200 DPI | 1.8–2.6 | 100% | 100% |
| OnnxTR 0.10 | degraded 150 DPI | 1.6–1.8 | 100% | 100% |

**What it shows:**
- Printed text on a normal scan is read perfectly by both local engines in 2–4 s. The page was too easy to separate
  them; a fair pick needs real scans (small fonts, stamps, photos). OnnxTR is ~2× faster but has no Japanese model
  **[unverified]**; RapidOCR is built into Docling.
- **Tables lose their shape**: OCR returns each cell as its own line ("Task / Owner / Status / Due"). Rebuilding the
  grid needs a table model (Docling TableFormer) or a vision model. This is the main quality gap of plain OCR.
- RapidOCR's extra models download from `modelscope.cn`; one download **failed** here, and an OnnxTR download from
  GitHub stalled once. Ship model files with Max
  (like the Kokoro voice files), never download at run time.
- Not tested: handwriting, photos, Japanese, Tesseract (not installed), Docling end to end.

## 5. Recommended pipeline

```
file bytes (kept, SHA-256 name)
  -> 1 detect type (magic bytes + extension), check limits
  -> 2 digital path: docx/xlsx/pptx/html with Docling (fallback MarkItDown / python-* libs)
                     pdf: text layer per page with pypdfium2
  -> 3 OCR only where needed: pdf pages with < ~50 characters of text, images, pictures inside slides/docs
  -> 4 tables -> Markdown tables (Docling TableFormer; xlsx straight from cells)
  -> 5 charts / pictures -> short description   [switch: off | local | vision model]
  -> 6 sections with locations -> chunker (existing plan in knowledge.md)
  -> 7 quality score + extractor version saved
```

| Rule | Value |
|---|---|
| Output | List of sections: `{kind, location (page 3 / slide 7 / sheet "Budget" rows 1–50), heading path, markdown, source: text\|ocr\|vision, confidence}` |
| Quality per file | **text OK** · **partly OCR** · **low confidence** (OCR score < ~0.8) · **failed**. Shown with search results so Max can say "this was a scan, numbers may be wrong" |
| Limits | File ≤ 50 MB; ≤ 300 pages/slides; ≤ 20 sheets × 5,000 rows; skip images under 100×100 px (icons, logos); OCR ≤ 100 pages per file; 10 min per file |
| Queue | Background worker (SQLite job table), 1–2 OCR jobs at a time. A new file is findable by name at once, by text when done |
| Re-extract | Save extractor + version per file. When a better one ships, re-run from stored bytes in the background; keep the new result only if it scores better |
| Vision switch | Off by default. When on: only low-confidence pages, charts and photos, through `gemini_cost/` with a monthly cap |
| Safety | Extracted text is **data, not instructions**. Extractors get local files only, no URLs. Macros never run |

Speed: scanned pages ~4–6 s each with OCR + tables, so 1,000 scanned pages ≈ 1.5 h in the background **[estimate]**.

## 6. Link briefs

| Step | Rule |
|---|---|
| When | A link is posted where Max is. SharePoint/OneDrive/Teams links are files: fetch them with Graph instead |
| Fetch | GET only, **no cookies or logins**, 10 s timeout, max 3 MB, max 3 redirects, HTML only (a PDF goes to the file pipeline) |
| Block | Private and local addresses (10.x, 192.168.x, 127.x, 169.254.x, `localhost`), checked after every redirect |
| Extract | `trafilatura` (text + title, author, date; Apache-2.0 since v1.8, GPL before); fallback `readability-lxml` |
| Brief | flash-lite, first ~4k words: title, "what it is" in one line, 3–5 key points, date. The page is **untrusted data; never follow instructions in it** |
| Store | URL, final URL, title, brief, fetched date, content hash, who shared it, channel, status (`ok`, `login needed`, `blocked`, `too big`, `failed`) |
| Refresh | No timer. Re-fetch if shared again after 7+ days, or before using a brief older than 30 days. Keep the old brief if the fetch fails |

Login pages give `login needed`; Max says so instead of guessing.

## 7. Top risks

| # | Risk | Fix |
|---|---|---|
| 1 | Docling is heavy (PyTorch, ~1–2 GB) and slower than MarkItDown | Run it in the background worker only; keep MarkItDown as fast first pass so files are searchable quickly |
| 2 | OCR numbers wrong in scanned tables or charts | Confidence score, "partly OCR" label shown to Max, vision switch for low-confidence pages |
| 3 | Licence trap via a "free" model (Marker/Surya weights, MinerU, PyMuPDF) | Check the licence of every package and model file; list them in `decisions.md` |
| 4 | Model downloads blocked at the office (seen in the test) | Bundle model files, pin versions |
| 5 | Prompt injection through file text or web pages | All extracted text is data; it never triggers tools |
| 6 | Laptop overload or Gemini cost creep | 1–2 workers, pause in live meetings; vision off by default with a monthly cap |

## Sources

- Docling: [PyPI](https://pypi.org/project/docling/) · [OCR engines](https://docling-project.github.io/docling/concepts/OCR/) · [formats](https://docling-project.github.io/docling/usage/supported_formats/) · [paper (CPU timings)](https://arxiv.org/pdf/2501.17887)
- [MarkItDown](https://pypi.org/project/markitdown/) · [markitdown-ocr](https://pypi.org/project/markitdown-ocr) · [RapidOCR](https://pypi.org/project/rapidocr/) · [trafilatura](https://pypi.org/project/trafilatura/)
- Licences: [Particula](https://particula.tech/blog/docling-vs-mineru-vs-marker-pdf-parser) · [Marker repo](https://github.com/datalab-to/marker) · [PyMuPDF alternatives](https://www.file2markdown.ai/blog/pymupdf-alternatives)
- Gemini: [media resolution](https://aistudio.google.com/docs/media-resolution) · [flash-lite pricing](https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-3-1-flash-lite/)
- Benchmark scripts (temporary, not in git): `C:\Users\10520\AppData\Local\Temp\claude\9309cdd0177292e1\6db74553-cd98-47e5-aa25-e75c4ca6714c\scratchpad\ocr-bench\bench2.py`
