import pytest

from app.modules.llm_pipeline.exceptions import VrlCompileError
from app.modules.llm_pipeline.services.vrl_validator import validate_vrl


class TestValidateVrl:
    def test_valid_vrl_032_returns_none(self):
        # parse_json! + assignment is a minimal compilable program
        result = validate_vrl(". = parse_json!(.message)", engine_version="0.32")
        assert result is None

    def test_valid_vrl_025(self):
        result = validate_vrl(". = parse_json!(.message)", engine_version="0.25")
        assert result is None

    def test_invalid_vrl_raises_vrl_compile_error(self):
        with pytest.raises(VrlCompileError) as excinfo:
            validate_vrl("???not vrl???", engine_version="0.32")
        assert len(str(excinfo.value)) > 0
