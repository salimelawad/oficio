from reportlab.pdfgen import canvas
from reportlab.lib.units import cm, inch
from reportlab.pdfbase import pdfmetrics
from bs4 import BeautifulSoup, NavigableString
import io

PAGE_W = 8.5 * inch   # Venezuelan oficio standard (8.5 × 13 in)
PAGE_H = 13.0 * inch
FONT_SIZE = 12
FONT_NORMAL = "Times-Roman"
FONT_BOLD = "Times-Bold"
FONT_ITALIC = "Times-Italic"
FONT_BOLD_ITALIC = "Times-BoldItalic"
RIGHT_MARGIN = 3.0 * cm
LIST_INDENT = 0.8 * cm

PAGE_CONFIGS = {
    "anverso_first": (5.0 * cm, 2.5 * cm, 30),
    "anverso":       (2.0 * cm, 1.5 * cm, 30),
    "reverso":       (2.0 * cm, 1.5 * cm, 34),
}

NUMBERS_TO_WORDS = {
    1: "UNO", 2: "DOS", 3: "TRES", 4: "CUATRO", 5: "CINCO",
    6: "SEIS", 7: "SIETE", 8: "OCHO", 9: "NUEVE", 10: "DIEZ",
    11: "ONCE", 12: "DOCE", 13: "TRECE", 14: "CATORCE", 15: "QUINCE",
    16: "DIECISÉIS", 17: "DIECISIETE", 18: "DIECIOCHO", 19: "DIECINUEVE",
    20: "VEINTE",
}


def page_word(n: int) -> str:
    if n in NUMBERS_TO_WORDS:
        return NUMBERS_TO_WORDS[n]
    if n < 100:
        tens = {
            30: "TREINTA", 40: "CUARENTA", 50: "CINCUENTA",
            60: "SESENTA", 70: "SETENTA", 80: "OCHENTA", 90: "NOVENTA",
        }
        t = (n // 10) * 10
        u = n % 10
        return tens[t] if u == 0 else tens[t] + " Y " + NUMBERS_TO_WORDS[u]
    return str(n)


def _font_for(bold: bool, italic: bool) -> str:
    if bold and italic:
        return FONT_BOLD_ITALIC
    if bold:
        return FONT_BOLD
    if italic:
        return FONT_ITALIC
    return FONT_NORMAL


# ── HTML parsing ──────────────────────────────────────────────────────────────

WordSpan = tuple[str, bool, bool]  # (word, bold, italic)


def _word_spans_from(node, bold=False, italic=False) -> list[WordSpan]:
    if isinstance(node, NavigableString):
        return [(w, bold, italic) for w in str(node).split()]
    tag = getattr(node, "name", None)
    if tag in ("strong", "b"):
        bold = True
    if tag in ("em", "i"):
        italic = True
    if tag == "br":
        return []
    spans = []
    for child in node.children:
        spans.extend(_word_spans_from(child, bold, italic))
    return spans


def extract_blocks(html: str) -> list:
    """Return a list of block descriptors:
      ('blank',)
      ('para',  [WordSpan, ...])
      ('bullet', [WordSpan, ...])
      ('ordered', n, [WordSpan, ...])
    """
    soup = BeautifulSoup(html, "html.parser")
    blocks = []

    def handle(node):
        tag = getattr(node, "name", None)
        if tag is None:
            return
        if tag == "p":
            spans = _word_spans_from(node)
            blocks.append(('para', spans) if spans else ('blank',))
        elif tag in ("ul", "ol"):
            for i, li in enumerate(node.find_all("li", recursive=False), 1):
                spans = _word_spans_from(li)
                if tag == "ul":
                    blocks.append(('bullet', spans))
                else:
                    blocks.append(('ordered', i, spans))
        else:
            for child in node.children:
                handle(child)

    for child in soup.children:
        handle(child)

    return blocks


# ── Line drawing ──────────────────────────────────────────────────────────────

def _draw_line(c: canvas.Canvas, words: list[WordSpan], x: float, y: float,
               width: float, is_block_last: bool):
    if not words:
        return
    space_w = pdfmetrics.stringWidth(" ", FONT_NORMAL, FONT_SIZE)
    if is_block_last or len(words) == 1:
        cx = x
        for word, bold, italic in words:
            font = _font_for(bold, italic)
            c.setFont(font, FONT_SIZE)
            c.drawString(cx, y, word)
            cx += pdfmetrics.stringWidth(word, font, FONT_SIZE) + space_w
        return
    total_w = sum(pdfmetrics.stringWidth(w, _font_for(b, i), FONT_SIZE) for w, b, i in words)
    gap = (width - total_w) / (len(words) - 1)
    cx = x
    for word, bold, italic in words:
        font = _font_for(bold, italic)
        c.setFont(font, FONT_SIZE)
        c.drawString(cx, y, word)
        cx += pdfmetrics.stringWidth(word, font, FONT_SIZE) + gap


# ── Page layout ───────────────────────────────────────────────────────────────

def get_page_config(page_num: int):
    if page_num == 1:
        return PAGE_CONFIGS["anverso_first"]
    return PAGE_CONFIGS["anverso"] if page_num % 2 == 1 else PAGE_CONFIGS["reverso"]


def draw_page(c: canvas.Canvas, page_num: int,
              lines_on_page: list,  # each: (indent, prefix, words|None, is_block_last)
              lawyer_name: str, inpreabogado: str, title: str, city: str, date: str,
              show_line_numbers: bool, show_page_numbers: bool):
    top_margin, left_margin, max_lines = get_page_config(page_num)
    bottom_margin = 1.0 * cm
    text_width = PAGE_W - left_margin - RIGHT_MARGIN
    line_height = (PAGE_H - top_margin - bottom_margin) / max_lines

    line_num_x_left = left_margin - 0.5 * cm
    line_num_x_right = PAGE_W - RIGHT_MARGIN + 0.3 * cm

    if page_num == 1:
        c.setFont(FONT_NORMAL, 9)
        lx = 0.5 * cm
        c.drawString(lx, PAGE_H - 1.2 * cm, f"Abog. {lawyer_name}")
        c.drawString(lx, PAGE_H - 1.8 * cm, f"INPREABOGADO N° {inpreabogado}")
        c.line(lx, PAGE_H - 2.4 * cm, lx + 5 * cm, PAGE_H - 2.4 * cm)
        c.setFont(FONT_NORMAL, 7)
        c.drawString(lx, PAGE_H - 2.7 * cm, "(Firma y sello)")
        c.setFont(FONT_BOLD, 11)
        c.drawCentredString(PAGE_W / 2, PAGE_H - 3.5 * cm, title.upper())
        c.setFont(FONT_NORMAL, 10)
        c.drawCentredString(PAGE_W / 2, PAGE_H - 4.2 * cm, f"{city}, {date}")

    for i, (indent, prefix, words, is_block_last) in enumerate(lines_on_page):
        y = PAGE_H - top_margin - (i * line_height) - line_height * 0.75

        if show_line_numbers:
            c.setFont(FONT_NORMAL, 9)
            c.drawRightString(line_num_x_left, y, str(i + 1))
            c.drawString(line_num_x_right, y, str(i + 1))

        if words is None:
            continue  # blank line — slot consumed, nothing drawn

        if prefix:
            c.setFont(FONT_NORMAL, FONT_SIZE)
            c.drawString(left_margin, y, prefix)

        text_x = left_margin + indent
        avail_w = text_width - indent
        _draw_line(c, words, text_x, y, avail_w, is_block_last)

    if show_page_numbers:
        c.setFont(FONT_NORMAL, 9)
        c.drawCentredString(PAGE_W / 2, bottom_margin / 2, f"{page_num} / {page_word(page_num)}")


# ── PDF generation ────────────────────────────────────────────────────────────

def generate_pdf(req) -> bytes:
    blocks = extract_blocks(req.content)
    if not blocks:
        blocks = [('para', [("(Sin", False, False), ("contenido)", False, False)])]

    # Build a list of mutable pending items so we can consume words lazily per page.
    # Each item: {'kind': 'blank'} or
    #            {'kind': 'text', 'indent': float, 'prefix': str, 'words': [WordSpan], 'first': bool}
    pending = []
    for block in blocks:
        if block[0] == 'blank':
            pending.append({'kind': 'blank'})
        elif block[0] == 'para':
            pending.append({'kind': 'text', 'indent': 0.0, 'prefix': '', 'words': list(block[1]), 'first': True})
        elif block[0] == 'bullet':
            pending.append({'kind': 'text', 'indent': LIST_INDENT, 'prefix': '\u2022 ', 'words': list(block[1]), 'first': True})
        elif block[0] == 'ordered':
            pending.append({'kind': 'text', 'indent': LIST_INDENT, 'prefix': f'{block[1]}. ', 'words': list(block[2]), 'first': True})

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(PAGE_W, PAGE_H))
    space_w = pdfmetrics.stringWidth(" ", FONT_NORMAL, FONT_SIZE)

    page_num = 0
    while pending:
        page_num += 1
        top_margin, left_margin, max_lines = get_page_config(page_num)
        text_width = PAGE_W - left_margin - RIGHT_MARGIN
        lines_on_page = []

        while pending and len(lines_on_page) < max_lines:
            item = pending[0]

            if item['kind'] == 'blank':
                pending.pop(0)
                lines_on_page.append((0.0, '', None, True))
                continue

            # Wrap one line worth of words from this text item
            words = item['words']
            avail_w = text_width - item['indent']
            current: list[WordSpan] = []
            current_w = 0.0

            while words:
                word, bold, italic = words[0]
                font = _font_for(bold, italic)
                word_w = pdfmetrics.stringWidth(word, font, FONT_SIZE)
                needed = word_w + (space_w if current else 0.0)
                if current and (current_w + needed > avail_w or len(current) >= 16):
                    break
                current.append(words.pop(0))
                current_w += needed

            if not current and words:
                current.append(words.pop(0))  # force single overlong word

            is_block_last = len(words) == 0
            prefix = item['prefix'] if item['first'] else ''
            lines_on_page.append((item['indent'], prefix, current, is_block_last))
            item['first'] = False

            if is_block_last:
                pending.pop(0)

        draw_page(c, page_num, lines_on_page,
                  req.lawyer_name, req.inpreabogado, req.title, req.city, req.date,
                  show_line_numbers=req.show_line_numbers,
                  show_page_numbers=req.show_page_numbers)

        if pending:
            c.showPage()

    c.save()
    return buf.getvalue()
