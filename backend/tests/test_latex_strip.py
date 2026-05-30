"""latex_strip.latex_to_plain — turn ingested LaTeX-style markup into the
same readable text the Question Bank preview pane shows (KaTeX-rendered).
"""

from app.modules.tests.services.latex_strip import latex_to_plain


class TestDelimiters:
    def test_strips_inline_dollar_pairs(self):
        assert latex_to_plain("$1.6\\text{m}$") == "1.6m"

    def test_strips_block_dollar_pairs(self):
        assert latex_to_plain("foo $$x+1$$ bar") == "foo x+1 bar"

    def test_leaves_text_without_delimiters_alone(self):
        s = "Plain question about Newton's laws."
        assert latex_to_plain(s) == s


class TestWrappers:
    def test_text_wrapper_keeps_inner(self):
        assert latex_to_plain("$5\\text{kg}$") == "5kg"

    def test_vec_and_hat_drop_to_argument(self):
        assert latex_to_plain("$\\vec{F}$") == "F"
        assert latex_to_plain("$\\hat{i}$") == "i"

    def test_mathrm_keeps_inner(self):
        assert latex_to_plain("$5\\mathrm{m/s}$") == "5m/s"

    def test_nested_vec_hat(self):
        # \vec{\hat{i}} → i after two passes
        assert latex_to_plain("$\\vec{\\hat{i}}$") == "i"


class TestSpecialChars:
    def test_escaped_percent(self):
        assert latex_to_plain("$100\\%$") == "100%"

    def test_escaped_amp_hash(self):
        assert latex_to_plain("\\& \\#") == "& #"


class TestFracAndSqrt:
    def test_frac_becomes_slash(self):
        assert latex_to_plain("$\\frac{1}{2}$") == "1/2"

    def test_sqrt_uses_radical(self):
        assert latex_to_plain("$\\sqrt{3}$") == "√3"


class TestSymbols:
    def test_pi_renders_unicode(self):
        assert latex_to_plain("$250\\pi^2$") == "250π²"

    def test_times_and_cdot(self):
        # Spaces inside $...$ become NBSP so the formula stays together.
        assert latex_to_plain("$a \\times b$") == "a\xa0×\xa0b"

    def test_inequalities(self):
        assert latex_to_plain("$x \\leq 5$") == "x\xa0≤\xa05"
        assert latex_to_plain("$x \\geq 5$") == "x\xa0≥\xa05"

    def test_arrow(self):
        assert latex_to_plain("$x \\rightarrow 0$") == "x\xa0→\xa00"


class TestSubSuper:
    def test_numeric_subscript(self):
        assert latex_to_plain("$m_1 = m_2$") == "m₁\xa0=\xa0m₂"

    def test_numeric_superscript(self):
        assert latex_to_plain("$x^2 + y^2$") == "x²\xa0+\xa0y²"

    def test_brace_subscript_with_digits(self):
        assert latex_to_plain("$P_{0}$") == "P₀"

    def test_non_convertible_subscript_kept_literal(self):
        # 'b' has no Unicode subscript — keep underscore notation.
        assert latex_to_plain("$m_b$") == "m_b"


class TestDegreeIdiom:
    def test_caret_circ_becomes_degree(self):
        # The user-reported case from question 7.
        assert latex_to_plain("$45^\\circ$") == "45°"

    def test_caret_braced_circ_becomes_degree(self):
        assert latex_to_plain("$45^{\\circ}$") == "45°"

    def test_bare_circ_still_works(self):
        # Standalone \circ (not preceded by ^) still maps to °.
        assert latex_to_plain("$\\circ$") == "°"


class TestNbspInMath:
    def test_spaces_inside_inline_math_become_nbsp(self):
        # Spaces inside $...$ get replaced with NBSP (U+00A0) so a short
        # formula doesn't word-wrap mid-expression in the PDF. Whole
        # text outside math is left alone.
        out = latex_to_plain("a $b c d$ e")
        assert "b\xa0c\xa0d" in out
        # Outside-math spaces stay ASCII.
        assert "a " in out and " e" in out

    def test_math_keeps_together_in_force_expression(self):
        # Real example: F = (4 + t \hat{i} + 6\hat{j})N
        out = latex_to_plain("$F = (4 + t \\hat{i} + 6\\hat{j})N$")
        assert "\xa0" in out  # at least one NBSP present
        assert "F" in out and "N" in out


class TestRealWorld:
    def test_full_bucket_question(self):
        # Exactly the case from the user-reported screenshot.
        src = (
            "A bucket tied at the end of a $1.6\\text{m}$ long string is "
            "whirled in a vertical circle with constant speed."
        )
        assert "1.6m" in latex_to_plain(src)
        assert "$" not in latex_to_plain(src)
        assert "\\text" not in latex_to_plain(src)

    def test_empty_string(self):
        assert latex_to_plain("") == ""

    def test_none_safe(self):
        # The pdf_service passes whatever Question.content gave; empty is
        # always possible.
        assert latex_to_plain("") == ""
