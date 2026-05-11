from app.modules.llm_pipeline.services.prompt_builder import DRAFT_TOOL_SCHEMA


class TestDraftToolSchema:
    def test_top_level(self):
        assert DRAFT_TOOL_SCHEMA["name"] == "submit_draft"
        assert "input_schema" in DRAFT_TOOL_SCHEMA

    def test_required_top_level_keys(self):
        req = set(DRAFT_TOOL_SCHEMA["input_schema"]["required"])
        assert req == {"log_type", "fields", "vrl_code", "engine_version", "notes"}

    def test_log_type_subschema(self):
        lt = DRAFT_TOOL_SCHEMA["input_schema"]["properties"]["log_type"]
        assert "name" in lt["properties"]
        assert "format" in lt["properties"]
        assert "json" in lt["properties"]["format"]["enum"]

    def test_field_type_enum(self):
        fields = DRAFT_TOOL_SCHEMA["input_schema"]["properties"]["fields"]
        item = fields["items"]
        assert "ip" in item["properties"]["field_type"]["enum"]
        assert fields["minItems"] == 1
        assert fields["maxItems"] == 50

    def test_engine_version_enum(self):
        ev = DRAFT_TOOL_SCHEMA["input_schema"]["properties"]["engine_version"]
        assert ev["enum"] == ["0.25", "0.32"]


class TestBlock1:
    def test_block1_imports_cheatsheet(self):
        from app.modules.llm_pipeline.services.prompt_builder import BLOCK1_TEXT
        assert "VRL function cheatsheet" in BLOCK1_TEXT

    def test_block1_persona(self):
        from app.modules.llm_pipeline.services.prompt_builder import BLOCK1_TEXT
        assert "library builder" in BLOCK1_TEXT.lower()

    def test_block1_warns_against_invented_fields(self):
        from app.modules.llm_pipeline.services.prompt_builder import BLOCK1_TEXT
        # may say "do not invent" or "don't invent" depending on prose
        text = BLOCK1_TEXT.lower()
        assert "do not invent" in text or "don't invent" in text

    def test_block1_includes_example(self):
        from app.modules.llm_pipeline.services.prompt_builder import BLOCK1_TEXT
        assert "PAN-OS" in BLOCK1_TEXT

    def test_block1_example_uses_real_braces(self):
        from app.modules.llm_pipeline.services.prompt_builder import BLOCK1_TEXT
        # verify f-string {{ }} escapes produced literal braces
        assert '"log_type":' in BLOCK1_TEXT
        assert "{{" not in BLOCK1_TEXT  # would mean escaping leaked through


class TestRenderBlock2:
    def _ctx(self, **overrides):
        from app.modules.llm_pipeline.services.prompt_builder import (
            DraftPromptContext,
            ExistingLogTypeView,
            FieldView,
        )
        defaults = {
            "vendor_name": "Acme",
            "vendor_slug": "acme",
            "product_name": "FW",
            "product_slug": "fw",
            "product_version": None,
            "product_deploy_type": "cloud",
            "existing_log_types": [
                ExistingLogTypeView(
                    name="PAN-OS TRAFFIC", format="syslog", transport="syslog_udp",
                    fields=[FieldView(name="src_ip", type="ip", required=True)],
                ),
            ],
            "doc_title": "A",
            "doc_url": "https://x",
            "doc_content": "# hi",
            "hint": None,
        }
        defaults.update(overrides)
        return DraftPromptContext(**defaults)

    def test_renders_vendor_product(self):
        from app.modules.llm_pipeline.services.prompt_builder import render_block2_xml
        x = render_block2_xml(self._ctx())
        assert '<vendor name="Acme" slug="acme" />' in x
        assert '<product name="FW" slug="fw"' in x

    def test_renders_existing_log_types(self):
        from app.modules.llm_pipeline.services.prompt_builder import render_block2_xml
        x = render_block2_xml(self._ctx())
        assert '<existing_log_types count="1">' in x
        assert 'PAN-OS TRAFFIC' in x
        assert 'src_ip' in x

    def test_existing_log_types_count_zero(self):
        from app.modules.llm_pipeline.services.prompt_builder import render_block2_xml
        x = render_block2_xml(self._ctx(existing_log_types=[]))
        assert '<existing_log_types count="0">' in x

    def test_doc_truncation(self):
        from app.modules.llm_pipeline.services.prompt_builder import render_block2_xml
        long = "A" * 30000
        x = render_block2_xml(self._ctx(doc_content=long))
        assert 'truncated_to="20000"' in x
        assert "A" * 20000 in x
        assert "A" * 20001 not in x

    def test_hint_omitted_when_none(self):
        from app.modules.llm_pipeline.services.prompt_builder import render_block2_xml
        x = render_block2_xml(self._ctx(hint=None))
        assert "<hint>" not in x

    def test_hint_rendered_when_present(self):
        from app.modules.llm_pipeline.services.prompt_builder import render_block2_xml
        x = render_block2_xml(self._ctx(hint="focus on subtype X"))
        assert "<hint>" in x
        assert "focus on subtype X" in x


class TestBuildSystemBlocks:
    def test_two_blocks_block1_cached(self):
        from app.modules.llm_pipeline.services.prompt_builder import (
            DraftPromptContext,
            build_system_blocks,
        )
        ctx = DraftPromptContext(
            vendor_name="x", vendor_slug="x",
            product_name="p", product_slug="p",
            product_version=None, product_deploy_type=None,
            existing_log_types=[], doc_title=None, doc_url=None,
            doc_content="x", hint=None,
        )
        blocks = build_system_blocks(ctx)
        assert len(blocks) == 2
        assert blocks[0]["type"] == "text"
        assert blocks[0]["cache_control"] == {"type": "ephemeral"}
        assert blocks[1]["type"] == "text"
        assert "cache_control" not in blocks[1]
        assert "library builder" in blocks[0]["text"].lower()
        assert "<vendor" in blocks[1]["text"]
