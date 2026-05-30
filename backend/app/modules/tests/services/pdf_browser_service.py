"""Render paper PDFs via a headless Chromium so the output matches the
Question Bank preview pane byte-for-byte — same KaTeX, same CSS, same
DOM. Replaces the regex-based pdf_service for paper / answer-key PDFs.

Trade-off: Chromium adds ~280MB to the prod image and a paper PDF takes
~1–3s to render (vs ~100ms before). In exchange we get the exact math
rendering admins see in the preview, with no edge cases to chase.
"""

import html
import logging
import re
from types import SimpleNamespace
from typing import Any

from playwright.async_api import async_playwright


_LATEX_CMD_RE = re.compile(r"\\[a-zA-Z]+")
# Bare command sequence: \word optionally followed by 1-2 brace groups.
# The brace pattern allows one level of nested braces so spans like
# \sqrt{mkt^{-1/2}} (with the inner ^{-1/2} braces) match as a unit.
_BRACE_GROUP = r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"
_BARE_CMD_SPAN_RE = re.compile(r"\\[a-zA-Z]+(?:" + _BRACE_GROUP + r"){0,2}")

# Ingested questions often store fractional or negative exponents
# unbraced — "t^-1/2" rather than the standard "t^{-1/2}". KaTeX is
# strict about this: ^ takes one token, so t^-1/2 renders as t with
# only "-" as the exponent (and "1/2" as regular text). Brace these
# before KaTeX sees them so the whole "-1/2" sits in the exponent.
_EXPONENT_NORMALIZERS = [
    # ^-N/M (negative fraction) and ^-N (negative integer)
    (re.compile(r"\^-(\d+/\d+)"), r"^{-\1}"),
    (re.compile(r"\^-(\d+)"), r"^{-\1}"),
    # ^N/M (positive fraction)
    (re.compile(r"\^(\d+/\d+)"), r"^{\1}"),
]


def _normalize_exponents(text: str) -> str:
    """Brace bare fractional / signed exponents so KaTeX takes the whole
    thing as the superscript instead of just the first token."""
    if not text or "^" not in text:
        return text
    for pat, repl in _EXPONENT_NORMALIZERS:
        text = pat.sub(repl, text)
    return text


def _ensure_math_wrap(text: str) -> str:
    """Wrap LaTeX-looking spans in ``$...$`` so KaTeX auto-render picks
    them up, and brace unbraced fractional / signed exponents so they
    render as the whole exponent rather than just the first token.

    Many ingested questions store options as bare LaTeX (no delimiters):
    e.g. ``\\sqrt{mkt^-1/2}`` rather than ``$\\sqrt{mkt^{-1/2}}$``. KaTeX
    only renders inside ``$...$`` / ``$$...$$`` markers, so without this
    pre-pass the raw command leaks into the PDF.
    """
    if not text:
        return text
    text = _normalize_exponents(text)
    if "$" in text:
        return text
    if not _LATEX_CMD_RE.search(text):
        return text
    # Pure-math fields (option content typical) start with a backslash —
    # wrap the whole string so even multi-level nested braces survive
    # to KaTeX intact.
    if text.lstrip().startswith("\\"):
        return f"${text}$"
    # Mixed prose: wrap each command run individually so the prose around
    # it stays as normal text.
    return _BARE_CMD_SPAN_RE.sub(lambda m: f"${m.group(0)}$", text)

log = logging.getLogger(__name__)

# KaTeX assets pinned to the same version we ship in the frontend
# (react-katex ~0.16). Loaded from a public CDN so we don't have to
# vendor a static-files mount in the backend.
_KATEX_VER = "0.16.11"
_KATEX_BASE = f"https://cdn.jsdelivr.net/npm/katex@{_KATEX_VER}/dist"
_KATEX_CSS = f"{_KATEX_BASE}/katex.min.css"
_KATEX_JS = f"{_KATEX_BASE}/katex.min.js"
_AUTO_RENDER_JS = f"{_KATEX_BASE}/contrib/auto-render.min.js"

_PAGE_CSS = """
@page { size: A4; margin: 18mm 14mm; }
* { box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica,
               Arial, sans-serif;
  color: #111;
  font-size: 11pt;
  line-height: 1.5;
  margin: 0;
}
.brand { font-size: 17pt; font-weight: 700; margin: 0; }
.sub { font-size: 9.5pt; color: #555; margin: 2pt 0 0 0; }
.divider { border: none; border-top: 1px solid #999; margin: 10pt 0 14pt; }
.q { margin: 0 0 14pt; break-inside: avoid; page-break-inside: avoid; }
.q-num { font-weight: 700; margin-right: 4pt; }
.opts { margin: 6pt 0 0 18pt; font-size: 10.5pt; color: #222; }
.opt { margin: 4pt 0; display: flex; gap: 6pt; align-items: baseline; }
.opt-key { font-weight: 700; min-width: 18pt; }
.akrow { margin: 0 0 10pt 0; font-size: 10.5pt; }
.ans { font-weight: 700; }
.expl { font-size: 9.5pt; color: #555; margin: 2pt 0 0 18pt; }
/* KaTeX renders math at slightly oversized line-height; calm it down. */
.katex { font-size: 1.05em; }
"""

_DELIMITERS = (
    '[{"left":"$$","right":"$$","display":true},'
    '{"left":"$","right":"$","display":false}]'
)

# Browse for $...$ / $$...$$ after the page is parsed, then flag done so
# we don't capture an unrendered snapshot.
_RENDER_SCRIPT = f"""
document.addEventListener('DOMContentLoaded', () => {{
  if (typeof renderMathInElement === 'function') {{
    renderMathInElement(document.body, {{
      delimiters: {_DELIMITERS},
      throwOnError: false,
      errorColor: '#c00',
    }});
  }}
  window.__katexDone = true;
}});
"""


def _header_html(brand_name: str, test: Any, n_questions: int, subtitle: str) -> str:
    return (
        f'<h1 class="brand">{html.escape(brand_name)}</h1>'
        f'<p class="sub">{html.escape(test.name)} &middot; '
        f"{html.escape(test.paper_type)} &middot; {n_questions} questions "
        f"&middot; Max marks {test.total_marks:.0f} &middot; "
        f"{html.escape(subtitle)}</p>"
        '<hr class="divider">'
    )


_OPTION_ORDER = ["A", "B", "C", "D", "E", "F"]


def _options_html(options: dict | None) -> str:
    if not options:
        return ""
    keys = [k for k in _OPTION_ORDER if k in options] or list(options.keys())
    rows = []
    for k in keys:
        val = _ensure_math_wrap(str(options[k]))
        rows.append(
            f'<div class="opt"><span class="opt-key">{html.escape(str(k))}.</span>'
            f"<span>{html.escape(val)}</span></div>"
        )
    return f'<div class="opts">{"".join(rows)}</div>'


def _doc(body: str) -> str:
    return f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<link rel="stylesheet" href="{_KATEX_CSS}">
<script defer src="{_KATEX_JS}"></script>
<script defer src="{_AUTO_RENDER_JS}"></script>
<style>{_PAGE_CSS}</style>
<script>{_RENDER_SCRIPT}</script>
</head><body>
{body}
</body></html>
"""


def _build_question_paper_html(
    test: Any, questions: list[dict], brand_name: str
) -> str:
    parts = [_header_html(brand_name, test, len(questions), "Question paper")]
    for i, q in enumerate(questions, start=1):
        content = _ensure_math_wrap(q.get("content", ""))
        parts.append(
            f'<div class="q"><span class="q-num">{i}.</span>'
            f"{html.escape(content)}"
            f'{_options_html(q.get("options"))}</div>'
        )
    return _doc("".join(parts))


def _build_answer_key_html(
    test: Any, questions: list[dict], brand_name: str
) -> str:
    parts = [_header_html(brand_name, test, len(questions), "Answer key (internal)")]
    for i, q in enumerate(questions, start=1):
        ans = html.escape(str(q.get("correct_answer") or "—"))
        row = (
            f'<div class="akrow"><span class="q-num">{i}.</span> '
            f'<span class="ans">Answer: {ans}</span>'
        )
        expl = q.get("explanation")
        if expl:
            row += (
                f'<div class="expl">'
                f"{html.escape(_ensure_math_wrap(str(expl)))}</div>"
            )
        row += "</div>"
        parts.append(row)
    return _doc("".join(parts))


async def _render_pdf(doc_html: str) -> bytes:
    """Drive headless Chromium: set HTML, wait for KaTeX, emit PDF bytes."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox"])
        try:
            page = await browser.new_page()
            await page.set_content(doc_html, wait_until="networkidle")
            # KaTeX auto-render runs on DOMContentLoaded, but if assets
            # arrived late we still wait for the explicit flag before
            # snapshotting — otherwise the PDF can capture raw $...$.
            await page.wait_for_function(
                "window.__katexDone === true", timeout=15000
            )
            return await page.pdf(
                format="A4",
                margin={"top": "18mm", "right": "14mm",
                        "bottom": "18mm", "left": "14mm"},
                print_background=True,
            )
        finally:
            await browser.close()


async def build_question_paper_pdf(
    test: Any, questions: list[dict], brand_name: str
) -> bytes:
    return await _render_pdf(_build_question_paper_html(test, questions, brand_name))


async def build_answer_key_pdf(
    test: Any, questions: list[dict], brand_name: str
) -> bytes:
    return await _render_pdf(_build_answer_key_html(test, questions, brand_name))
