"""Convert LaTeX-style markup in question text to plain readable text.

This is NOT a real LaTeX renderer — it's a small set of substitutions
that handle the patterns Gemini-ingested questions most often emit
(``$...$`` delimiters, ``\\text{}`` wrappers, common Greek letters and
operators) so that PDFs read like the rendered KaTeX output the admin
sees in the Question Bank preview pane.

Anything unhandled survives as-is, which is acceptable — the admin can
clean it up in Question Bank Edit if it matters.
"""

import re

# Non-breaking space — used inside math expressions so that a short
# formula like "F = (4 + t i + 6j)N" doesn't word-wrap mid-expression
# when PyMuPDF Story lays the PDF out.
NBSP = "\xa0"

# \cmd -> unicode glyph. Word-boundary matched at use so \\alpha doesn't
# eat \\alphax.
_SYMBOL_MAP: dict[str, str] = {
    # Greek lowercase
    r"\alpha": "α", r"\beta": "β", r"\gamma": "γ", r"\delta": "δ",
    r"\epsilon": "ε", r"\varepsilon": "ε", r"\zeta": "ζ", r"\eta": "η",
    r"\theta": "θ", r"\vartheta": "θ", r"\iota": "ι", r"\kappa": "κ",
    r"\lambda": "λ", r"\mu": "μ", r"\nu": "ν", r"\xi": "ξ",
    r"\pi": "π", r"\varpi": "π", r"\rho": "ρ", r"\sigma": "σ",
    r"\tau": "τ", r"\upsilon": "υ", r"\phi": "φ", r"\varphi": "φ",
    r"\chi": "χ", r"\psi": "ψ", r"\omega": "ω",
    # Greek uppercase
    r"\Gamma": "Γ", r"\Delta": "Δ", r"\Theta": "Θ", r"\Lambda": "Λ",
    r"\Xi": "Ξ", r"\Pi": "Π", r"\Sigma": "Σ", r"\Phi": "Φ",
    r"\Psi": "Ψ", r"\Omega": "Ω",
    # Operators / relations
    r"\infty": "∞", r"\pm": "±", r"\mp": "∓",
    r"\times": "×", r"\cdot": "·", r"\div": "÷",
    r"\leq": "≤", r"\le": "≤", r"\geq": "≥", r"\ge": "≥",
    r"\neq": "≠", r"\ne": "≠", r"\approx": "≈", r"\equiv": "≡",
    r"\sim": "∼", r"\propto": "∝",
    # Arrows
    r"\rightarrow": "→", r"\to": "→", r"\leftarrow": "←", r"\gets": "←",
    r"\Rightarrow": "⇒", r"\Leftarrow": "⇐",
    r"\leftrightarrow": "↔",
    # Misc
    r"\degree": "°", r"\circ": "°", r"\prime": "′",
    r"\ldots": "…", r"\dots": "…", r"\cdots": "…",
    r"\sum": "∑", r"\int": "∫", r"\partial": "∂",
    r"\nabla": "∇",
}

# Wrapper commands whose only effect (for plain-text purposes) is the
# inner argument — \vec{F} -> F, \text{m} -> m, etc.
_WRAPPER_CMDS = (
    "text", "mathrm", "mathbf", "mathit", "mathsf", "mathtt",
    "textbf", "textit", "textrm", "texttt", "boldsymbol",
    "vec", "hat", "bar", "tilde", "dot", "ddot",
    "overline", "underline",
)
_WRAPPER_RE = re.compile(r"\\(?:" + "|".join(_WRAPPER_CMDS) + r")\{([^{}]*)\}")

_FRAC_RE = re.compile(r"\\frac\{([^{}]*)\}\{([^{}]*)\}")
_SQRT_RE = re.compile(r"\\sqrt\{([^{}]*)\}")
_BLOCK_DELIM_RE = re.compile(r"\$\$(.+?)\$\$", re.DOTALL)
_INLINE_DELIM_RE = re.compile(r"\$([^$]+)\$", re.DOTALL)

_SUB_MAP = {
    "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄",
    "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉",
    "+": "₊", "-": "₋", "=": "₌", "(": "₍", ")": "₎",
    "a": "ₐ", "e": "ₑ", "o": "ₒ", "x": "ₓ", "h": "ₕ",
    "k": "ₖ", "l": "ₗ", "m": "ₘ", "n": "ₙ", "p": "ₚ",
    "s": "ₛ", "t": "ₜ",
}
_SUP_MAP = {
    "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
    "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹",
    "+": "⁺", "-": "⁻", "=": "⁼", "(": "⁽", ")": "⁾",
    "n": "ⁿ", "i": "ⁱ",
}


def _convert_run(run: str, table: dict[str, str]) -> str | None:
    """Translate the whole string char-by-char. Returns None if any char
    can't be translated — caller falls back to keeping the markup."""
    out: list[str] = []
    for c in run:
        sub = table.get(c)
        if sub is None:
            return None
        out.append(sub)
    return "".join(out)


def latex_to_plain(text: str) -> str:
    """Strip LaTeX markup to readable plain text (Unicode where useful).

    Order matters: idioms first (^\\circ), then delimiters, then
    multi-argument commands (\\frac, \\sqrt), wrappers, symbols, and
    finally sub/superscripts."""
    if not text:
        return text
    s = text

    # 0. Idioms that consume the caret along with their argument — handle
    #    before the generic symbol/superscript passes leave a stray "^".
    s = re.sub(r"\^\{?\\circ\}?", "°", s)
    s = re.sub(r"\^\{?\\prime\}?", "′", s)

    # 1. Strip $$...$$ and $...$ math delimiters. Replace ASCII spaces
    #    inside math with NBSP so short formulas don't word-wrap.
    def _keep_math_together(m: re.Match) -> str:
        return m.group(1).replace(" ", NBSP)

    s = _BLOCK_DELIM_RE.sub(_keep_math_together, s)
    s = _INLINE_DELIM_RE.sub(_keep_math_together, s)

    # 2. \frac{a}{b} -> a/b, \sqrt{x} -> √x — before generic wrappers
    #    eat the brace groups.
    s = _FRAC_RE.sub(lambda m: f"{m.group(1)}/{m.group(2)}", s)
    s = _SQRT_RE.sub(lambda m: f"√{m.group(1)}", s)

    # 3. Wrapper commands — applied twice for one level of nesting
    #    (e.g. \vec{\hat{i}}).
    s = _WRAPPER_RE.sub(lambda m: m.group(1), s)
    s = _WRAPPER_RE.sub(lambda m: m.group(1), s)

    # 4. \left and \right wrappers around delimiters — drop them. Negative
    #    lookahead so \rightarrow isn't decapitated into "arrow".
    s = re.sub(r"\\left(?![a-zA-Z])", "", s)
    s = re.sub(r"\\right(?![a-zA-Z])", "", s)

    # 5. Spacing commands -> spaces (NBSP since they originated in math).
    s = re.sub(r"\\[,;:!]", NBSP, s)
    s = re.sub(r"\\(?:quad|qquad)\b", NBSP * 2, s)

    # 6. Greek letters / operators / arrows / misc symbols.
    for cmd, sym in _SYMBOL_MAP.items():
        s = re.sub(re.escape(cmd) + r"(?![a-zA-Z])", sym, s)

    # 7. Subscripts and superscripts (Unicode where possible).
    def _sub_brace(m):
        out = _convert_run(m.group(1), _SUB_MAP)
        return out if out is not None else f"_{m.group(1)}"

    def _sub_short(m):
        out = _convert_run(m.group(1), _SUB_MAP)
        return out if out is not None else m.group(0)

    def _sup_brace(m):
        out = _convert_run(m.group(1), _SUP_MAP)
        return out if out is not None else f"^{m.group(1)}"

    def _sup_short(m):
        out = _convert_run(m.group(1), _SUP_MAP)
        return out if out is not None else m.group(0)

    s = re.sub(r"_\{([^{}]*)\}", _sub_brace, s)
    s = re.sub(r"_([a-zA-Z0-9])", _sub_short, s)
    s = re.sub(r"\^\{([^{}]*)\}", _sup_brace, s)
    s = re.sub(r"\^([a-zA-Z0-9])", _sup_short, s)

    # 8. Escaped punctuation — last so earlier passes don't consume them.
    s = s.replace(r"\%", "%").replace(r"\&", "&")
    s = s.replace(r"\#", "#").replace(r"\$", "$").replace(r"\_", "_")

    return s
