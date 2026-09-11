import pytest

from src.integrations.gemini_client import LLMStageError, require_ok

# Prefix captured from a real Vertex 404 probe (2026-09-11, us-central1),
# in the exact "[Error: {e}]" shape GeminiClient.generate returns.
REAL_ERROR = (
    "[Error: 404 NOT_FOUND. {'error': {'code': 404, 'message': 'Publisher model "
    "`projects/ngresp-gemini-enterprise/locations/us-central1/publishers/google/"
    "models/gemini-3.8-flash` was not found'}}]"
)


def test_require_ok_raises_on_generate_error_string():
    with pytest.raises(LLMStageError, match="expert"):
        require_ok("expert", REAL_ERROR)


def test_require_ok_passes_normal_text_through():
    md = "## 💡 ประเด็นวันนี้\nลดค่าไฟ 20%"
    assert require_ok("translator", md) is md


def test_require_ok_ignores_error_word_mid_text():
    # Anchored on the prefix: an article that merely mentions "[Error"
    # must not abort the run.
    md = "## Log\nระบบแสดง [Error: timeout] เมื่อ PLC หลุด"
    assert require_ok("translator", md) is md


def test_require_ok_ignores_non_text():
    assert require_ok("industry", None) is None
