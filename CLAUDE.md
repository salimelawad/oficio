# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync                              # install / sync dependencies
uv run uvicorn app:app --reload      # start dev server at http://localhost:8000
uv run python -c "from pdf_generator import generate_pdf; ..."  # test PDF generation directly
```

## Architecture

Three files do all the work:

**`app.py`** — FastAPI app with two routes. `GET /` serves the SPA. `POST /generate` receives a `DocumentRequest` JSON body and streams back a PDF. `pdf_generator` is imported inside the route to keep startup fast.

**`pdf_generator.py`** — All PDF layout logic using ReportLab's low-level canvas API (not Platypus). The pipeline is:
1. `extract_word_spans(html)` — walks the BeautifulSoup tree to produce `list[tuple[word, is_bold, is_italic]]`, preserving inline formatting from Quill's HTML output.
2. `generate_pdf(req)` — paginates the word spans greedily. On each iteration it calls `get_page_config(page_num)` to get the correct `(top_margin, left_margin, max_lines)` for that page type, then fills lines up to that limit.
3. `draw_page(...)` — draws one page: the lawyer/INPREABOGADO block (page 1 only), line numbers on both sides, justified text via `_draw_line`, and the page folio at the bottom.

**`static/index.html`** — Self-contained SPA (no build step). Quill.js loaded from CDN. On every `text-change` or form `input` event the full draft is serialised to `localStorage` under key `oficio_draft` with a timestamp; on load it is restored if under 24 h old. The "Generar PDF" button POSTs JSON to `/generate` and triggers a blob download.

## Page format constants (Venezuelan legal spec)

| Page | top | left | right | lines |
|------|-----|------|-------|-------|
| Anverso page 1 | 5 cm | 2.5 cm | 3 cm | 30 |
| Anverso pages 3+ | 2 cm | 1.5 cm | 3 cm | 30 |
| Reverso (even pages) | 2 cm | 1.5 cm | 3 cm | 34 |

Page size: **8.5 × 13 inches** (612 × 936 pt) — Venezuelan oficio standard. The spec mentions "33 × 21.75 cm" but those are rounded approximations; use inches for accuracy. Font: Times-Roman 12 pt, justified. Line numbers printed at both left and right edges. Page folio format: `"1 / UNO"`.

Legal basis: Ley de Timbres Fiscales (Gaceta Oficial N° 6, 18/11/2014), Cap. II, Art. 31, Parágrafo Primero.

## Key constraints
- No try/except unless absolutely necessary.
- Keep it simple — no framework layers beyond FastAPI + ReportLab canvas.
- `wrap_word_spans` / the inline pagination loop both enforce a hard 16-word-per-line cap in addition to the pixel-width cap.
- `_draw_line` handles justified spacing by computing inter-word gaps from `pdfmetrics.stringWidth`; the last line of each paragraph is left-aligned.
