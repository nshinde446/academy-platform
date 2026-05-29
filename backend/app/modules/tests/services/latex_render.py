"""Render LaTeX math in question text to PNG images for the paper PDFs.

Uses matplotlib's built-in *mathtext* engine — no system TeX install
required, so it works identically on the Windows dev box and the Linux
prod image. We deliberately use the object-oriented ``Figure`` API
(not ``pyplot``) so rendering is thread-safe under ``asyncio.to_thread``
with concurrent requests.

A malformed expression (common in AI-extracted text) raises here; callers
get ``None`` and fall back to showing the raw ``$...$`` source rather than
failing the whole paper.
"""

import io

import matplotlib

matplotlib.use("Agg")
from matplotlib.figure import Figure

# (expr, fontsize) -> PNG bytes. Math repeats across a paper's questions;
# rendering each figure costs tens of ms, so a tiny process cache helps.
_CACHE: dict[tuple[str, int], bytes] = {}
_FAILED: set[tuple[str, int]] = set()


def render_math_png(expr: str, *, fontsize: int = 16, dpi: int = 200) -> bytes | None:
    """LaTeX expr (no surrounding $) -> tightly-cropped transparent PNG.

    Returns None if mathtext can't parse it (caller shows raw source)."""
    key = (expr, fontsize)
    if key in _CACHE:
        return _CACHE[key]
    if key in _FAILED:
        return None
    try:
        fig = Figure(figsize=(0.01, 0.01))
        fig.text(0, 0, f"${expr}$", fontsize=fontsize)
        buf = io.BytesIO()
        fig.savefig(
            buf, format="png", dpi=dpi,
            bbox_inches="tight", pad_inches=0.02, transparent=True,
        )
        data = buf.getvalue()
    except Exception:
        # mathtext ParseSyntaxException (or anything else) — never let a
        # single bad expression take down the paper.
        _FAILED.add(key)
        return None
    _CACHE[key] = data
    return data
