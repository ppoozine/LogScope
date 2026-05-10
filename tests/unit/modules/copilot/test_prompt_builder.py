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
        from app.modules.copilot.schemas import AnalyzerPageContext
        defaults = {
            "page": "analyzer",
            "vrl": None,
            "vrl_engine": None,
            "logs": [],
            "parse_results": [],
            "match_top_candidate": None,
        }
        defaults.update(kwargs)
        return AnalyzerPageContext(**defaults)

    def test_minimal_context_only_facts(self):
        from app.modules.copilot.services.prompt_builder import _render_page_context_xml

        xml = _render_page_context_xml(
            self._ctx(),
            max_log_lines=20,
            max_vrl_chars=4000,
            max_library_products=20,
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
            max_library_products=20,
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
            max_library_products=20,
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
        xml = _render_page_context_xml(ctx, max_log_lines=20, max_vrl_chars=4000, max_library_products=20)

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
            max_library_products=20,
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
            max_library_products=20,
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
            max_library_products=20,
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
            max_library_products=20,
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
            max_library_products=20,
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
            max_library_products=20,
        )

        assert len(blocks) == 1
        assert blocks[0]["type"] == "text"
        assert blocks[0]["cache_control"] == {"type": "ephemeral"}
        assert "Skill: log_explain" in blocks[0]["text"]

    def test_with_page_context_returns_two_blocks(self):
        from app.modules.copilot.schemas import AnalyzerPageContext
        from app.modules.copilot.services.prompt_builder import build_system_blocks

        ctx = AnalyzerPageContext(page="analyzer", logs=["a"])
        blocks = build_system_blocks(
            skill="log_explain",
            page_context=ctx,
            max_log_lines=20,
            max_vrl_chars=4000,
            max_library_products=20,
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
            max_library_products=20,
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
            max_library_products=20,
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
            max_log_lines=10, max_vrl_chars=4000, max_library_products=20,
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
            max_log_lines=10, max_vrl_chars=4000, max_library_products=20,
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
            max_log_lines=10, max_vrl_chars=4000, max_library_products=20,
        )
        text = blocks[0]["text"]
        assert "Example A" in text
        assert "Example B" in text
        # Each example has its own ```vrl block
        assert text.count("```vrl") >= 2


class TestPageContextDispatch:
    def test_library_overview_routes_to_renderer(self):
        from app.modules.copilot.schemas import LibraryOverviewPageContext
        from app.modules.copilot.services.prompt_builder import _render_page_context_xml

        ctx = LibraryOverviewPageContext(
            page="library_overview",
            filters={},
            vendor_count=1,
            product_count=2,
            products_missing_parse_rule=[],
        )
        xml = _render_page_context_xml(
            ctx, max_log_lines=10, max_vrl_chars=4000, max_library_products=20,
        )
        assert '<page_context page="library_overview">' in xml

    def test_library_product_routes_to_renderer(self):
        from app.modules.copilot.schemas import LibraryProductPageContext
        from app.modules.copilot.services.prompt_builder import _render_page_context_xml

        ctx = LibraryProductPageContext(
            page="library_product",
            vendor_slug="v",
            product_slug="p",
            product_status="active",
        )
        xml = _render_page_context_xml(
            ctx, max_log_lines=10, max_vrl_chars=4000, max_library_products=20,
        )
        assert '<page_context page="library_product">' in xml

    def test_library_versions_routes_to_renderer(self):
        from app.modules.copilot.schemas import LibraryVersionsPageContext
        from app.modules.copilot.services.prompt_builder import _render_page_context_xml

        ctx = LibraryVersionsPageContext(
            page="library_versions",
            vendor_slug="v",
            product_slug="p",
            log_type_name="t",
        )
        xml = _render_page_context_xml(
            ctx, max_log_lines=10, max_vrl_chars=4000, max_library_products=20,
        )
        assert '<page_context page="library_versions">' in xml

    def test_analyzer_still_works_after_extraction(self):
        from app.modules.copilot.schemas import AnalyzerPageContext
        from app.modules.copilot.services.prompt_builder import _render_page_context_xml

        ctx = AnalyzerPageContext(page="analyzer", logs=["a", "b"])
        xml = _render_page_context_xml(
            ctx, max_log_lines=10, max_vrl_chars=4000, max_library_products=20,
        )
        assert '<page_context page="analyzer">' in xml
        assert '<log index="1">' in xml
        assert '<log index="2">' in xml


class TestLibraryOverviewXml:
    def _ctx(self, **kw):
        from app.modules.copilot.schemas import LibraryOverviewPageContext
        defaults = {
            "page": "library_overview",
            "filters": {"status": "published", "q": "palo"},
            "vendor_count": 12,
            "product_count": 34,
            "products_missing_parse_rule": [
                "paloalto/panorama",
                "cisco/ftd",
            ],
        }
        defaults.update(kw)
        return LibraryOverviewPageContext(**defaults)

    def test_basic_xml(self):
        from app.modules.copilot.services.prompt_builder import _render_library_overview_xml
        xml = _render_library_overview_xml(self._ctx(), max_products=20)
        assert '<page_context page="library_overview">' in xml
        assert "<vendor_count>12</vendor_count>" in xml
        assert "<product_count>34</product_count>" in xml
        assert "paloalto/panorama" in xml
        assert "cisco/ftd" in xml

    def test_truncates_to_max_products(self):
        from app.modules.copilot.services.prompt_builder import _render_library_overview_xml
        ctx = self._ctx(products_missing_parse_rule=[f"v/p{i}" for i in range(30)])
        xml = _render_library_overview_xml(ctx, max_products=5)
        # `showing` reflects how many entries are actually rendered, `count`
        # the original total
        assert 'showing="5"' in xml
        assert 'count="30"' in xml
        assert "v/p0" in xml
        assert "v/p4" in xml
        assert "v/p5" not in xml

    def test_empty_missing_list(self):
        from app.modules.copilot.services.prompt_builder import _render_library_overview_xml
        xml = _render_library_overview_xml(
            self._ctx(products_missing_parse_rule=[]),
            max_products=20,
        )
        assert 'count="0"' in xml
        assert 'showing="0"' in xml

    def test_filters_attribute_with_quote_characters(self):
        """quoteattr handles embedded quotes safely."""
        import xml.etree.ElementTree as ET
        from app.modules.copilot.services.prompt_builder import _render_library_overview_xml
        xml_str = _render_library_overview_xml(
            self._ctx(filters={"q": 'has "quote"', "status": None}),
            max_products=20,
        )
        # Result should be valid XML even with the embedded `"`
        root = ET.fromstring(xml_str)
        filters_el = root.find(".//filters")
        assert filters_el is not None
        # status=None is skipped, only q renders
        assert filters_el.get("q") == 'has "quote"'
        assert filters_el.get("status") is None

    def test_filters_omitted_when_none_or_empty(self):
        from app.modules.copilot.services.prompt_builder import _render_library_overview_xml
        xml = _render_library_overview_xml(
            self._ctx(filters={}),
            max_products=20,
        )
        # Empty filters renders an empty <filters/> element
        assert "<filters/>" in xml or "<filters />" in xml


class TestLibraryProductXml:
    def _ctx(self, active_log_type=None):
        from app.modules.copilot.schemas import LibraryProductPageContext
        return LibraryProductPageContext(
            page="library_product",
            vendor_slug="paloalto",
            product_slug="pan-os",
            product_status="active",
            active_log_type=active_log_type,
        )

    def test_no_active_log_type(self):
        from app.modules.copilot.services.prompt_builder import _render_library_product_xml
        xml = _render_library_product_xml(self._ctx(), max_vrl_chars=4000)
        assert "<vendor_slug>paloalto</vendor_slug>" in xml
        assert "<product_slug>pan-os</product_slug>" in xml
        assert "<product_status>active</product_status>" in xml
        # active_log_type element is omitted entirely when None
        assert "<active_log_type" not in xml

    def test_with_active_log_type(self):
        from app.modules.copilot.schemas import ActiveLogTypeContext, FieldSummary
        from app.modules.copilot.services.prompt_builder import _render_library_product_xml
        alt = ActiveLogTypeContext(
            name="traffic",
            fields=[
                FieldSummary(name="src_ip", type="string", required=True),
                FieldSummary(name="dst_port", type="integer", required=False),
            ],
            samples_count=23,
            parse_rule_head=". = parse_syslog!(.message)",
        )
        xml = _render_library_product_xml(self._ctx(active_log_type=alt), max_vrl_chars=4000)
        assert '<active_log_type name="traffic">' in xml
        assert '<fields count="2">' in xml
        assert '<field name="src_ip" type="string" required="true"/>' in xml
        assert '<field name="dst_port" type="integer" required="false"/>' in xml
        assert "<samples_count>23</samples_count>" in xml
        assert "parse_syslog" in xml

    def test_active_log_type_no_parse_rule_head(self):
        from app.modules.copilot.schemas import ActiveLogTypeContext
        from app.modules.copilot.services.prompt_builder import _render_library_product_xml
        alt = ActiveLogTypeContext(name="t", fields=[], samples_count=0, parse_rule_head=None)
        xml = _render_library_product_xml(self._ctx(active_log_type=alt), max_vrl_chars=4000)
        assert '<active_log_type name="t">' in xml
        # parse_rule_head element omitted when None
        assert "<parse_rule_head" not in xml

    def test_parse_rule_head_truncated(self):
        from app.modules.copilot.schemas import ActiveLogTypeContext
        from app.modules.copilot.services.prompt_builder import _render_library_product_xml
        long_rule = "x" * 10000
        alt = ActiveLogTypeContext(name="t", parse_rule_head=long_rule)
        xml = _render_library_product_xml(
            self._ctx(active_log_type=alt), max_vrl_chars=100,
        )
        # truncated_to attribute appears with the cap value
        assert 'truncated_to="100"' in xml
        # Truncated content present
        assert "x" * 100 in xml
        # Original full rule NOT in output
        assert "x" * 200 not in xml

    def test_parse_rule_head_with_cdata_terminator_escaped(self):
        """`]]>` inside parse_rule_head must be escaped via _safe_cdata."""
        from app.modules.copilot.schemas import ActiveLogTypeContext
        from app.modules.copilot.services.prompt_builder import _render_library_product_xml
        alt = ActiveLogTypeContext(
            name="t", parse_rule_head='. = parse_json(.) ?? "]]>"',
        )
        xml = _render_library_product_xml(self._ctx(active_log_type=alt), max_vrl_chars=4000)
        # _safe_cdata splits the CDATA boundary
        assert "]]]]><![CDATA[>" in xml
        # Balanced CDATA opens/closes
        assert xml.count("<![CDATA[") == xml.count("]]>")

    def test_field_attributes_use_quoteattr(self):
        """Field names with quotes shouldn't break XML."""
        import xml.etree.ElementTree as ET
        from app.modules.copilot.schemas import ActiveLogTypeContext, FieldSummary
        from app.modules.copilot.services.prompt_builder import _render_library_product_xml
        alt = ActiveLogTypeContext(
            name='log "type"',  # name with quotes
            fields=[FieldSummary(name='field "x"', type="string", required=True)],
        )
        xml_str = _render_library_product_xml(self._ctx(active_log_type=alt), max_vrl_chars=4000)
        # Resulting XML must be parsable
        root = ET.fromstring(xml_str)
        alt_el = root.find(".//active_log_type")
        assert alt_el is not None
        assert alt_el.get("name") == 'log "type"'
        field_el = root.find(".//field")
        assert field_el is not None
        assert field_el.get("name") == 'field "x"'


class TestLibraryVersionsXml:
    def _ctx(self, diff=None):
        from app.modules.copilot.schemas import LibraryVersionsPageContext
        return LibraryVersionsPageContext(
            page="library_versions",
            vendor_slug="paloalto",
            product_slug="pan-os",
            log_type_name="traffic",
            diff=diff,
        )

    def test_no_diff(self):
        from app.modules.copilot.services.prompt_builder import _render_library_versions_xml
        xml = _render_library_versions_xml(self._ctx(), max_vrl_chars=4000)
        assert '<page_context page="library_versions">' in xml
        assert "<vendor_slug>paloalto</vendor_slug>" in xml
        assert "<product_slug>pan-os</product_slug>" in xml
        assert "<log_type_name>traffic</log_type_name>" in xml
        # diff element entirely omitted when None
        assert "<diff" not in xml

    def test_with_diff(self):
        from app.modules.copilot.schemas import VersionDiffContext
        from app.modules.copilot.services.prompt_builder import _render_library_versions_xml
        diff = VersionDiffContext(
            base_version="v3", head_version="v4",
            base_vrl="old vrl content",
            head_vrl="new vrl content",
        )
        xml = _render_library_versions_xml(self._ctx(diff=diff), max_vrl_chars=4000)
        assert 'base_version="v3"' in xml
        assert 'head_version="v4"' in xml
        assert "<base_vrl>" in xml
        assert "<head_vrl>" in xml
        assert "old vrl content" in xml
        assert "new vrl content" in xml

    def test_diff_with_only_head_vrl(self):
        """base_vrl=None should omit only the base_vrl element, head_vrl still rendered."""
        from app.modules.copilot.schemas import VersionDiffContext
        from app.modules.copilot.services.prompt_builder import _render_library_versions_xml
        diff = VersionDiffContext(
            base_version="v3", head_version="v4",
            base_vrl=None,
            head_vrl="new only",
        )
        xml = _render_library_versions_xml(self._ctx(diff=diff), max_vrl_chars=4000)
        assert "<base_vrl" not in xml
        assert "<head_vrl>" in xml
        assert "new only" in xml

    def test_vrl_truncated(self):
        from app.modules.copilot.schemas import VersionDiffContext
        from app.modules.copilot.services.prompt_builder import _render_library_versions_xml
        long = "y" * 8000
        diff = VersionDiffContext(
            base_version="v1", head_version="v2",
            base_vrl=long, head_vrl="short",
        )
        xml = _render_library_versions_xml(self._ctx(diff=diff), max_vrl_chars=200)
        # base_vrl truncated; head_vrl not
        assert '<base_vrl truncated_to="200">' in xml
        assert "y" * 200 in xml
        assert "y" * 400 not in xml
        # head_vrl renders without truncated_to attribute
        assert "<head_vrl>" in xml

    def test_vrl_with_cdata_terminator_escaped(self):
        from app.modules.copilot.schemas import VersionDiffContext
        from app.modules.copilot.services.prompt_builder import _render_library_versions_xml
        diff = VersionDiffContext(
            base_version="v1", head_version="v2",
            base_vrl='. = parse_json(.) ?? "]]>"',
            head_vrl=None,
        )
        xml = _render_library_versions_xml(self._ctx(diff=diff), max_vrl_chars=4000)
        assert "]]]]><![CDATA[>" in xml
        assert xml.count("<![CDATA[") == xml.count("]]>")

    def test_diff_attributes_use_quoteattr(self):
        """Version strings with quotes shouldn't break XML."""
        import xml.etree.ElementTree as ET
        from app.modules.copilot.schemas import VersionDiffContext
        from app.modules.copilot.services.prompt_builder import _render_library_versions_xml
        diff = VersionDiffContext(
            base_version='v"1', head_version='v"2',
            base_vrl=None, head_vrl=None,
        )
        xml_str = _render_library_versions_xml(self._ctx(diff=diff), max_vrl_chars=4000)
        root = ET.fromstring(xml_str)
        diff_el = root.find(".//diff")
        assert diff_el is not None
        assert diff_el.get("base_version") == 'v"1'
        assert diff_el.get("head_version") == 'v"2'


class TestVrlOptimizeBlock:
    def test_vrl_optimize_skill_uses_dedicated_block(self):
        from app.modules.copilot.services.prompt_builder import build_system_blocks

        text = build_system_blocks(
            skill="vrl_optimize",
            page_context=None,
            max_log_lines=10,
            max_vrl_chars=4000,
            max_library_products=20,
        )[0]["text"]

        assert "LogScope Copilot" in text
        assert "vrl_optimize" in text
        # Refactor-oriented language
        assert "```vrl" in text
        assert "parse_results" in text
        assert "You must NOT" in text
        # Distinct from log_explain
        assert "Skill: log_explain" not in text


class TestAnomalyBlock:
    def test_anomaly_skill_uses_dedicated_block(self):
        from app.modules.copilot.services.prompt_builder import build_system_blocks

        text = build_system_blocks(
            skill="anomaly",
            page_context=None,
            max_log_lines=10,
            max_vrl_chars=4000,
            max_library_products=20,
        )[0]["text"]

        assert "LogScope Copilot" in text
        assert "anomaly" in text
        # Anomaly-specific phrasing
        assert "異常" in text or "anomal" in text.lower()
        # Confidence labels (mandatory; consistent with log_explain)
        assert "〔依據：" in text
        assert "Skill: log_explain" not in text


# ---------------------------------------------------------------------------
# Inline VRL tests (Task 3)
# ---------------------------------------------------------------------------

from app.modules.copilot.schemas import InlineVrlRequest  # noqa: E402
from app.modules.copilot.services.prompt_builder import (  # noqa: E402
    _inject_marker,
    _sanitize_markers,
    build_inline_system_blocks,
)


class TestSanitizeMarkers:
    def test_replaces_pipe_markers_with_underscore(self):
        v = "let x = '<|cursor|>'"
        out = _sanitize_markers(v)
        assert "<|cursor|>" not in out
        assert "<_cursor_>" in out

    def test_preserves_offset_length(self):
        # Marker length must be preserved so caller offsets stay valid.
        for marker, sanitized in [
            ("<|cursor|>", "<_cursor_>"),
            ("<|sel_start|>", "<_sel_start_>"),
            ("<|sel_end|>", "<_sel_end_>"),
        ]:
            assert len(marker) == len(sanitized)
        v = "abc<|cursor|>def"
        assert len(_sanitize_markers(v)) == len(v)

    def test_no_marker_unchanged(self):
        v = ". = parse_syslog!(.message)"
        assert _sanitize_markers(v) == v


class TestInjectMarker:
    def test_insert_at_offset(self):
        req = InlineVrlRequest(
            instruction="x", mode="insert",
            current_vrl="abcdef", cursor_offset=3,
        )
        assert _inject_marker("abcdef", req) == "abc<|cursor|>def"

    def test_replace_wraps_selection(self):
        req = InlineVrlRequest(
            instruction="x", mode="replace",
            current_vrl="abcdefghij",
            selection_start=2, selection_end=5,
        )
        assert _inject_marker("abcdefghij", req) == "ab<|sel_start|>cde<|sel_end|>fghij"

    def test_insert_at_zero(self):
        req = InlineVrlRequest(
            instruction="x", mode="insert",
            current_vrl="", cursor_offset=0,
        )
        assert _inject_marker("", req) == "<|cursor|>"


class TestBuildInlineSystemBlocks:
    def _req_insert(self, **kw):
        defaults = dict(
            instruction="加 dst_ip",
            mode="insert",
            current_vrl=". = parse_syslog!(.message)",
            cursor_offset=27,
            vrl_engine="0.32",
            logs=["log a", "log b"],
        )
        defaults.update(kw)
        return InlineVrlRequest(**defaults)

    def _req_replace(self, **kw):
        defaults = dict(
            instruction="改寫",
            mode="replace",
            current_vrl="abcdefghij",
            selection_start=2,
            selection_end=5,
        )
        defaults.update(kw)
        return InlineVrlRequest(**defaults)

    def test_returns_two_blocks(self):
        blocks = build_inline_system_blocks(
            self._req_insert(), max_log_lines=20, max_vrl_chars=4000,
        )
        assert len(blocks) == 2
        assert blocks[0]["type"] == "text"
        assert blocks[0].get("cache_control") == {"type": "ephemeral"}
        assert blocks[1]["type"] == "text"
        assert "cache_control" not in blocks[1]

    def test_block1_contains_skill_rules(self):
        blocks = build_inline_system_blocks(
            self._req_insert(), max_log_lines=20, max_vrl_chars=4000,
        )
        b1 = blocks[0]["text"]
        assert "Mode A" in b1
        assert "Mode B" in b1
        assert "ONLY raw VRL" in b1
        assert "<|cursor|>" in b1
        assert "<|sel_start|>" in b1

    def test_block2_insert_has_cursor_marker(self):
        blocks = build_inline_system_blocks(
            self._req_insert(), max_log_lines=20, max_vrl_chars=4000,
        )
        b2 = blocks[1]["text"]
        assert "<vrl_engine>0.32</vrl_engine>" in b2
        assert "<|cursor|>" in b2
        assert "<|sel_start|>" not in b2

    def test_block2_replace_has_selection_markers(self):
        blocks = build_inline_system_blocks(
            self._req_replace(), max_log_lines=20, max_vrl_chars=4000,
        )
        b2 = blocks[1]["text"]
        assert "<|sel_start|>" in b2
        assert "<|sel_end|>" in b2
        assert "<|cursor|>" not in b2

    def test_block2_logs_capped(self):
        req = self._req_insert(logs=[f"l{i}" for i in range(30)])
        blocks = build_inline_system_blocks(req, max_log_lines=5, max_vrl_chars=4000)
        b2 = blocks[1]["text"]
        assert 'count="30" showing="5"' in b2
        assert '<log index="5"' in b2
        assert '<log index="6"' not in b2

    def test_block2_vrl_truncated_when_marker_in_kept_window(self):
        # cursor at offset 5 → marker is in first portion → truncate keeps it
        req = self._req_insert(current_vrl="abcde" + "x" * 200, cursor_offset=5)
        blocks = build_inline_system_blocks(req, max_log_lines=20, max_vrl_chars=50)
        b2 = blocks[1]["text"]
        assert "<|cursor|>" in b2
        assert 'truncated_to="50"' in b2

    def test_block2_vrl_omitted_when_marker_lost_to_truncation(self):
        # cursor at offset 200 → marker lies past the truncated window
        req = self._req_insert(current_vrl="x" * 500, cursor_offset=200)
        blocks = build_inline_system_blocks(req, max_log_lines=20, max_vrl_chars=50)
        b2 = blocks[1]["text"]
        assert "<current_vrl" not in b2

    def test_block2_no_logs(self):
        req = self._req_insert(logs=[])
        blocks = build_inline_system_blocks(req, max_log_lines=20, max_vrl_chars=4000)
        b2 = blocks[1]["text"]
        assert "<logs" not in b2

    def test_user_vrl_with_literal_marker_sanitized(self):
        # User's VRL accidentally contains <|cursor|> string
        req = self._req_insert(
            current_vrl='. = "<|cursor|> note"', cursor_offset=21,
        )
        blocks = build_inline_system_blocks(req, max_log_lines=20, max_vrl_chars=4000)
        b2 = blocks[1]["text"]
        # Original literal must have been sanitized so only one marker remains
        assert b2.count("<|cursor|>") == 1
        assert "<_cursor_>" in b2

    def _req_fix(self, **kw):
        defaults = dict(
            instruction="Fix this",
            skill="vrl_fix",
            mode="replace",
            current_vrl="abcdefghij",
            selection_start=2,
            selection_end=5,
            compile_error="error[E110]: function `split` expected `string`, got `bytes`",
            vrl_engine="0.32",
        )
        defaults.update(kw)
        return InlineVrlRequest(**defaults)

    def test_vrl_fix_uses_dedicated_block1(self):
        blocks = build_inline_system_blocks(
            self._req_fix(), max_log_lines=20, max_vrl_chars=4000,
        )
        b1 = blocks[0]["text"]
        assert "VRL compile-error fixer" in b1
        assert "<|sel_start|>" in b1
        assert "Output ONLY raw VRL" in b1
        assert "無法修復" in b1

    def test_vrl_fix_block2_includes_compile_error(self):
        blocks = build_inline_system_blocks(
            self._req_fix(compile_error="error[E110]: WIRE_THIS_THROUGH"),
            max_log_lines=20, max_vrl_chars=4000,
        )
        b2 = blocks[1]["text"]
        assert "<compile_error>" in b2
        assert "WIRE_THIS_THROUGH" in b2
        assert "<|sel_start|>" in b2
        assert "<|sel_end|>" in b2

    def test_vrl_inline_block2_excludes_compile_error(self):
        # default skill=vrl_inline (existing behavior) must NOT include compile_error block
        blocks = build_inline_system_blocks(
            self._req_insert(),  # existing helper (skill defaults to vrl_inline)
            max_log_lines=20, max_vrl_chars=4000,
        )
        b2 = blocks[1]["text"]
        assert "<compile_error>" not in b2

    def test_vrl_fix_block1_differs_from_vrl_inline(self):
        b1_fix = build_inline_system_blocks(
            self._req_fix(), max_log_lines=20, max_vrl_chars=4000,
        )[0]["text"]
        b1_inline = build_inline_system_blocks(
            self._req_insert(), max_log_lines=20, max_vrl_chars=4000,
        )[0]["text"]
        assert b1_fix != b1_inline
