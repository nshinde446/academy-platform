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
        assert latex_to_plain("$a \\times b$") == "a × b"

    def test_inequalities(self):
        assert latex_to_plain("$x \\leq 5$") == "x ≤ 5"
        assert latex_to_plain("$x \\geq 5$") == "x ≥ 5"

    def test_arrow(self):
        assert latex_to_plain("$x \\rightarrow 0$") == "x → 0"


class TestSubSuper:
    def test_numeric_subscript(self):
        assert latex_to_plain("$m_1 = m_2$") == "m₁ = m₂"

    def test_numeric_superscript(self):
        assert latex_to_plain("$x^2 + y^2$") == "x² + y²"

    def test_brace_subscript_with_digits(self):
        assert latex_to_plain("$P_{0}$") == "P₀"

    def test_non_convertible_subscript_kept_literal(self):
        # 'b' has no Unicode subscript — keep underscore notation.
        assert latex_to_plain("$m_b$") == "m_b"


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
