"""Generate the branded question-paper and answer-key PDFs for a saved
paper (Tier 14).

Pipeline: question text + options may contain LaTeX (``$...$`` inline,
``$$...$$`` display). We split each string into text/math runs, render
math runs to PNGs via :mod:`latex_render`, and assemble an HTML fragment
that interleaves escaped text with ``<img>`` tags. PyMuPDF's Story engine
then lays the HTML out into a paginated PDF — no system TeX or browser
needed, so it runs the same on Windows dev and the Linux prod image.

Math is rendered at 3x DPI and downscaled in CSS so it stays crisp while
sitting at roughly the surrounding font size (a tall fraction therefore
renders taller than an inline ``x^2`` instead of being squashed to a
fixed height)."""

import html
import io
import re
import struct

import fitz

from app.modules.tests.services.latex_render import render_math_png

# Render math oversized for crispness, then scale back down in the HTML.
_MATH_SCALE = 3
_BODY_PT = 11
_DISPLAY_PT = 13

# $$display$$ first, then $inline$. DOTALL so simple multi-line math works.
_SEG = re.compile(r"\$\$(.+?)\$\$|\$(.+?)\$", re.DOTALL)


def _png_size(data: bytes) -> tuple[int, int]:
    """(width, height) from a PNG's IHDR — avoids decoding the image."""
    w, h = struct.unpack(">II", data[16:24])
    return w, h


class _MathImages:
    """Collects rendered math PNGs into a fitz.Archive, de-duping by
    expression so the same formula is embedded once per document."""

    def __init__(self) -> None:
        self.archive = fitz.Archive()
        self._names: dict[tuple[str, int], str] = {}
        self._n = 0

    def tag(self, expr: str, *, display: bool) -> str:
        """Return an <img> tag for ``expr`` (or escaped raw source if the
        LaTeX won't parse)."""
        fontsize = (_DISPLAY_PT if display else _BODY_PT) * _MATH_SCALE
        key = (expr, fontsize)
        name = self._names.get(key)
        if name is None:
            png = render_math_png(expr, fontsize=fontsize)
            if png is None:
                # Unparseable — show the literal source so nothing is lost.
                raw = html.escape(f"${expr}$" if not display else f"$${expr}$$")
                return raw
            name = f"m{self._n}.png"
            self._n += 1
            self.archive.add(png, name)
            self._names[key] = name
        png = render_math_png(expr, fontsize=fontsize)  # cached
        w, h = _png_size(png)
        cw, ch = w / _MATH_SCALE, h / _MATH_SCALE
        valign = "" if display else "vertical-align:middle;"
        return (
            f'<img src="{name}" width="{cw:.0f}" height="{ch:.0f}" '
            f'style="{valign}">'
        )


def _render_runs(text: str, imgs: _MathImages) -> str:
    """Emit the question/option text verbatim (with $...$ visible).

    Math rendering is intentionally disabled: Gemini-ingested questions
    routinely wrap plain values like ``$100\\%$`` in math markers, and
    PyMuPDF Story treats CSS px as pt, which fought the supersample
    factor and made rendered math come out roughly 3x oversized.
    Surfacing the source verbatim matches what the admin sees on the
    Question Bank and is readable for students. Leaving the math
    pipeline (latex_render, _MathImages) intact so it can be turned
    back on once the sizing is reworked."""
    if not text:
        return ""
    return html.escape(text)


_CSS = """
body { font-family: sans-serif; color: #111; }
h1 { font-size: 16pt; margin: 0; }
.sub { font-size: 9.5pt; color: #555; margin: 2pt 0 0 0; }
hr { border: none; border-top: 1px solid #999; margin: 8pt 0; }
.q { font-size: 11pt; margin: 0 0 9pt 0; }
.opts { font-size: 10.5pt; color: #222; margin: 2pt 0 0 14pt; }
.opt { margin: 1pt 0; }
.akrow { font-size: 10.5pt; margin: 0 0 6pt 0; }
.ans { font-weight: bold; }
.expl { font-size: 9.5pt; color: #555; margin: 1pt 0 0 14pt; }
"""

_OPTION_ORDER = ["A", "B", "C", "D", "E", "F"]


def _header_html(brand_name: str, test, n_questions: int, subtitle: str) -> str:
    return (
        f"<h1>{html.escape(brand_name)}</h1>"
        f'<p class="sub">{html.escape(test.name)} &middot; '
        f"{html.escape(test.paper_type)} &middot; {n_questions} questions "
        f"&middot; Max marks {test.total_marks:.0f} &middot; {subtitle}</p>"
        "<hr>"
    )


def _options_html(options: dict | None, imgs: _MathImages) -> str:
    if not options:
        return ""
    rows = []
    keys = [k for k in _OPTION_ORDER if k in options] or list(options.keys())
    for k in keys:
        rows.append(
            f'<div class="opt">({html.escape(str(k))}) '
            f"{_render_runs(str(options[k]), imgs)}</div>"
        )
    return f'<div class="opts">{"".join(rows)}</div>'


def _story_to_pdf(html_body: str, archive: fitz.Archive) -> bytes:
    story = fitz.Story(html=html_body, user_css=_CSS, archive=archive)
    out = io.BytesIO()
    writer = fitz.DocumentWriter(out)
    mediabox = fitz.paper_rect("a4")
    where = mediabox + (50, 50, -50, -50)
    more = 1
    while more:
        dev = writer.begin_page(mediabox)
        more, _ = story.place(where)
        story.draw(dev)
        writer.end_page()
    writer.close()
    return out.getvalue()


def build_question_paper_pdf(test, questions: list[dict], brand_name: str) -> bytes:
    """Branded student question paper: header + numbered questions + options.

    ``questions`` are the formatted dicts from
    ``test_service.get_test_question_details``."""
    imgs = _MathImages()
    parts = [_header_html(brand_name, test, len(questions), "Question paper")]
    for i, q in enumerate(questions, start=1):
        parts.append(
            f'<div class="q"><b>{i}.</b> '
            f'{_render_runs(q.get("content", ""), imgs)}'
            f'{_options_html(q.get("options"), imgs)}</div>'
        )
    body = f"<body>{''.join(parts)}</body>"
    return _story_to_pdf(body, imgs.archive)


def build_answer_key_pdf(test, questions: list[dict], brand_name: str) -> bytes:
    """Internal answer key: correct option + explanation per question."""
    imgs = _MathImages()
    parts = [_header_html(brand_name, test, len(questions), "Answer key (internal)")]
    for i, q in enumerate(questions, start=1):
        ans = html.escape(str(q.get("correct_answer") or "—"))
        row = (
            f'<div class="akrow"><b>{i}.</b> '
            f'<span class="ans">Answer: {ans}</span>'
        )
        expl = q.get("explanation")
        if expl:
            row += f'<div class="expl">{_render_runs(str(expl), imgs)}</div>'
        row += "</div>"
        parts.append(row)
    body = f"<body>{''.join(parts)}</body>"
    return _story_to_pdf(body, imgs.archive)
