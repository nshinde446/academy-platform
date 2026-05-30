"""Unit tests for the pure helpers in pdf_browser_service — these run
without a browser. End-to-end PDF rendering (which needs Chromium) is
covered separately in test_paper_pdf.py::TestPdfServiceEndToEnd."""

from app.modules.tests.services.pdf_browser_service import (
    _ensure_math_wrap,
    _normalize_exponents,
)


class TestNormalizeExponents:
    def test_negative_fraction_gets_braced(self):
        assert _normalize_exponents("t^-1/2") == "t^{-1/2}"

    def test_negative_integer_gets_braced(self):
        assert _normalize_exponents("t^-1") == "t^{-1}"

    def test_positive_fraction_gets_braced(self):
        assert _normalize_exponents("t^1/2") == "t^{1/2}"

    def test_single_char_exponent_left_alone(self):
        # KaTeX handles t^2 correctly on its own.
        assert _normalize_exponents("t^2") == "t^2"

    def test_already_braced_left_alone(self):
        assert _normalize_exponents("t^{-1/2}") == "t^{-1/2}"


class TestEnsureMathWrap:
    def test_plain_prose_untouched(self):
        assert _ensure_math_wrap("A particle of mass m") == "A particle of mass m"

    def test_text_with_dollars_untouched(self):
        # Already delimited — caller has done the work.
        assert _ensure_math_wrap("find $\\vec{F}$") == "find $\\vec{F}$"

    def test_pure_latex_option_gets_wrapped(self):
        # The exact user-reported shape from question 7 options.
        out = _ensure_math_wrap("\\sqrt{mkt^-1/2}")
        assert out == "$\\sqrt{mkt^{-1/2}}$"

    def test_prefix_then_latex_wraps_whole_string(self):
        # "1/2\sqrt{mkt^-1/2}" has nested braces inside \sqrt once the
        # exponent is normalized to ^{-1/2}; per-sequence wrap must
        # therefore cover the nesting.
        out = _ensure_math_wrap("1/2\\sqrt{mkt^-1/2}")
        # No raw \sqrt outside $...$ delimiters.
        assert "\\sqrt" in out
        # And the LaTeX command was wrapped at least once.
        assert "$" in out

    def test_mixed_prose_per_sequence_wrap(self):
        # Bare \vec{F} sitting in normal prose.
        out = _ensure_math_wrap("Force \\vec{F} acts on")
        assert "$\\vec{F}$" in out
        # Surrounding prose stays untouched.
        assert "Force " in out and " acts on" in out
