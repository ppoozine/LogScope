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


class TestRenderPageContextXml:
    def _ctx(self, **kwargs):
        from app.modules.copilot.schemas import PageContext
        defaults = {
            "page": "analyzer",
            "vrl": None,
            "vrl_engine": None,
            "logs": [],
            "parse_results": [],
            "match_top_candidate": None,
        }
        defaults.update(kwargs)
        return PageContext(**defaults)

    def test_minimal_context_only_facts(self):
        from app.modules.copilot.services.prompt_builder import _render_page_context_xml

        xml = _render_page_context_xml(
            self._ctx(),
            max_log_lines=20,
            max_vrl_chars=4000,
        )

        assert '<page_context page="analyzer">' in xml
        assert "<facts>" in xml
        assert "<log_count>0</log_count>" in xml
        assert "<hypotheses>" in xml
        assert "<match_candidate" not in xml  # no candidate, not rendered
        assert "<current_vrl" not in xml      # no vrl, not rendered

    def test_logs_use_cdata_wrap(self):
        from app.modules.copilot.services.prompt_builder import _render_page_context_xml

        xml = _render_page_context_xml(
            self._ctx(logs=["raw <log> with & ents"]),
            max_log_lines=20,
            max_vrl_chars=4000,
        )

        assert "<![CDATA[raw <log> with & ents]]>" in xml
        assert '<logs count="1" showing="1">' in xml

    def test_logs_truncated_to_max(self):
        from app.modules.copilot.services.prompt_builder import _render_page_context_xml

        logs = [f"line {i}" for i in range(30)]
        xml = _render_page_context_xml(
            self._ctx(logs=logs),
            max_log_lines=20,
            max_vrl_chars=4000,
        )

        assert '<logs count="30" showing="20">' in xml
        assert "line 0" in xml
        assert "line 19" in xml
        assert "line 20" not in xml

    def test_match_candidate_renders_to_hypotheses(self):
        from app.modules.copilot.services.prompt_builder import _render_page_context_xml

        ctx = self._ctx(
            match_top_candidate={
                "vendor_slug": "paloalto",
                "product_slug": "pan-os",
                "log_type_name": "Traffic",
                "confidence": 0.94,
            }
        )
        xml = _render_page_context_xml(ctx, max_log_lines=20, max_vrl_chars=4000)

        assert 'source="MatchBar"' in xml
        assert 'vendor="paloalto"' in xml
        assert 'product="pan-os"' in xml
        assert 'log_type="Traffic"' in xml
        assert 'confidence="0.94"' in xml

    def test_vrl_truncated_with_attribute(self):
        from app.modules.copilot.services.prompt_builder import _render_page_context_xml

        long_vrl = "x" * 5000
        xml = _render_page_context_xml(
            self._ctx(vrl=long_vrl, vrl_engine="v0.32"),
            max_log_lines=20,
            max_vrl_chars=4000,
        )

        assert '<current_vrl truncated_to="4000">' in xml
        assert "x" * 4000 in xml
        # full vrl NOT in output
        assert "x" * 5000 not in xml
        assert "<vrl_engine>v0.32</vrl_engine>" in xml

    def test_short_vrl_no_truncate_attribute(self):
        from app.modules.copilot.services.prompt_builder import _render_page_context_xml

        xml = _render_page_context_xml(
            self._ctx(vrl=". = .message"),
            max_log_lines=20,
            max_vrl_chars=4000,
        )

        assert "<current_vrl>" in xml          # no truncated_to attribute
        assert ". = .message" in xml

    def test_parse_results_attribute_escape(self):
        import xml.etree.ElementTree as ET

        from app.modules.copilot.services.prompt_builder import _render_page_context_xml

        xml_str = _render_page_context_xml(
            self._ctx(
                parse_results=[
                    {"index": 0, "status": "ok"},
                    {"index": 1, "status": "error", "message": 'field "x" missing'},
                ]
            ),
            max_log_lines=20,
            max_vrl_chars=4000,
        )

        # Backend ParseResultItem.index is 0-based; renderer adds +1 so the
        # number lines up with <log index="N"> rendering above.
        assert '<result index="1" status="ok"/>' in xml_str
        # Naive interpolation would break the XML. We assert by *parsing* the
        # rendered output: a valid XML parse proves the `"` was correctly
        # escaped (either via &quot; or by quoteattr switching to single-quote
        # delimiters; both are valid XML).
        root = ET.fromstring(xml_str)
        results = root.findall(".//result")
        assert len(results) == 2
        ok_one = results[0]
        err = results[1]
        assert ok_one.get("index") == "1"
        assert err.get("index") == "2"
        assert err.get("status") == "error"
        assert err.get("message") == 'field "x" missing'

    def test_log_with_cdata_terminator_is_escaped(self):
        from app.modules.copilot.services.prompt_builder import _render_page_context_xml

        xml = _render_page_context_xml(
            self._ctx(logs=["payload before ]]> after"]),
            max_log_lines=20,
            max_vrl_chars=4000,
        )

        # The escape splits CDATA at the boundary so the LLM sees the literal `]]>` byte
        # sequence without prematurely closing CDATA.
        assert "]]]]><![CDATA[>" in xml
        # CDATA opens and closes must remain balanced.
        assert xml.count("<![CDATA[") == xml.count("]]>")

    def test_vrl_with_cdata_terminator_is_escaped(self):
        from app.modules.copilot.services.prompt_builder import _render_page_context_xml

        xml = _render_page_context_xml(
            self._ctx(vrl=".x = parse(.) ?? \"]]>\""),
            max_log_lines=20,
            max_vrl_chars=4000,
        )

        assert "]]]]><![CDATA[>" in xml
        assert xml.count("<![CDATA[") == xml.count("]]>")


class TestBuildSystemBlocks:
    def test_no_page_context_returns_one_block(self):
        from app.modules.copilot.services.prompt_builder import build_system_blocks

        blocks = build_system_blocks(
            skill="log_explain",
            page_context=None,
            max_log_lines=20,
            max_vrl_chars=4000,
        )

        assert len(blocks) == 1
        assert blocks[0]["type"] == "text"
        assert blocks[0]["cache_control"] == {"type": "ephemeral"}
        assert "Skill: log_explain" in blocks[0]["text"]

    def test_with_page_context_returns_two_blocks(self):
        from app.modules.copilot.schemas import PageContext
        from app.modules.copilot.services.prompt_builder import build_system_blocks

        ctx = PageContext(page="analyzer", logs=["a"])
        blocks = build_system_blocks(
            skill="log_explain",
            page_context=ctx,
            max_log_lines=20,
            max_vrl_chars=4000,
        )

        assert len(blocks) == 2
        # block 1 cached
        assert blocks[0]["cache_control"] == {"type": "ephemeral"}
        # block 2 NOT cached
        assert "cache_control" not in blocks[1]
        assert "<page_context" in blocks[1]["text"]

    def test_no_skill_no_context(self):
        from app.modules.copilot.services.prompt_builder import build_system_blocks

        blocks = build_system_blocks(
            skill=None,
            page_context=None,
            max_log_lines=20,
            max_vrl_chars=4000,
        )

        assert len(blocks) == 1
        assert "Skill: log_explain" not in blocks[0]["text"]


class TestVrlGenerateBlock:
    def test_vrl_generate_skill_uses_dedicated_block(self):
        from app.modules.copilot.services.prompt_builder import build_system_blocks

        blocks = build_system_blocks(
            skill="vrl_generate",
            page_context=None,
            max_log_lines=10,
            max_vrl_chars=4000,
        )
        text = blocks[0]["text"]
        # 含 persona 段
        assert "LogScope Copilot" in text
        # 含 vrl_generate skill 段
        assert "vrl_generate" in text
        # 含關鍵指令
        assert "```vrl" in text
        assert "hard-code" in text.lower() or "hardcode" in text.lower()
        assert "You must NOT" in text

    def test_vrl_generate_does_not_include_log_explain_section(self):
        from app.modules.copilot.services.prompt_builder import build_system_blocks
        blocks = build_system_blocks(
            skill="vrl_generate", page_context=None,
            max_log_lines=10, max_vrl_chars=4000,
        )
        text = blocks[0]["text"]
        assert "Skill: log_explain" not in text

    def test_vrl_generate_includes_function_cheatsheet(self):
        """Cheatsheet exists so the LLM doesn't have to remember function
        names; the absence of these names was a top cause of compile errors
        in early production samples."""
        from app.modules.copilot.services.prompt_builder import build_system_blocks
        blocks = build_system_blocks(
            skill="vrl_generate", page_context=None,
            max_log_lines=10, max_vrl_chars=4000,
        )
        text = blocks[0]["text"]
        # Core parse functions
        assert "parse_syslog" in text
        assert "parse_json" in text
        assert "parse_regex" in text
        # Suffix semantics — most common compile-error source
        assert "??" in text
        # Engine version contrast
        assert "0.32" in text
        assert "0.25" in text

    def test_vrl_generate_has_two_examples(self):
        """JSON example was added because syslog-only example overfit the
        LLM toward syslog-style output even for JSON inputs."""
        from app.modules.copilot.services.prompt_builder import build_system_blocks
        blocks = build_system_blocks(
            skill="vrl_generate", page_context=None,
            max_log_lines=10, max_vrl_chars=4000,
        )
        text = blocks[0]["text"]
        assert "Example A" in text
        assert "Example B" in text
        # Each example has its own ```vrl block
        assert text.count("```vrl") >= 2
