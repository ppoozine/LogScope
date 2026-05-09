"""Unit tests for Copilot prompt builder."""


class TestBuildBlock1:
    def test_includes_persona_and_output_rules(self):
        from app.modules.copilot.services.prompt_builder import _build_block1

        text = _build_block1(skill="log_explain")

        assert "LogScope Copilot" in text
        assert "繁體中文" in text
        assert "Cite data by tag" in text
        # the three confidence labels MUST appear verbatim
        assert "〔依據：明確〕" in text
        assert "〔依據：推測〕" in text
        assert "〔依據：未知〕" in text

    def test_includes_log_explain_skill_section(self):
        from app.modules.copilot.services.prompt_builder import _build_block1

        text = _build_block1(skill="log_explain")

        assert "# Skill: log_explain" in text
        assert "Process (follow in order)" in text
        assert "You must NOT" in text
        assert "Uncertainty rule" in text
        assert "GOOD OUTPUT" in text  # few-shot example

    def test_no_skill_omits_skill_section(self):
        from app.modules.copilot.services.prompt_builder import _build_block1

        text = _build_block1(skill=None)

        # Persona still there
        assert "LogScope Copilot" in text
        # Skill section gone
        assert "# Skill: log_explain" not in text
        assert "Process (follow in order)" not in text
        # Replaced by generic guidance
        assert "no active skill" in text.lower() or "active skill" in text.lower()
