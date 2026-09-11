"""
Verify the with_retries decorator retries on transient errors and not on
non-transient ones.
"""
from unittest.mock import Mock

import pytest
from googleapiclient.errors import HttpError

from src.utils.retry import _is_transient, with_retries


def _fake_http_error(status: int) -> HttpError:
    resp = Mock()
    resp.status = status
    resp.reason = "x"
    return HttpError(resp=resp, content=b"")


def test_is_transient_for_retryable_http():
    assert _is_transient(_fake_http_error(429))
    assert _is_transient(_fake_http_error(500))
    assert _is_transient(_fake_http_error(503))


def test_is_not_transient_for_4xx():
    assert not _is_transient(_fake_http_error(400))
    assert not _is_transient(_fake_http_error(403))
    assert not _is_transient(_fake_http_error(404))


def test_is_transient_for_connection_errors():
    assert _is_transient(ConnectionError("boom"))
    assert _is_transient(TimeoutError("slow"))


def test_retries_on_transient_then_succeeds():
    calls = {"n": 0}

    @with_retries
    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("transient")
        return "ok"

    assert flaky() == "ok"
    assert calls["n"] == 3


def test_does_not_retry_on_non_transient():
    calls = {"n": 0}

    @with_retries
    def busted():
        calls["n"] += 1
        raise ValueError("permanent")

    with pytest.raises(ValueError):
        busted()
    assert calls["n"] == 1


# --- google-genai errors (Gemini via Vertex) -------------------------------
from google.genai import errors as genai_errors  # noqa: E402

# Payload captured from the 2026-09-11 production run (editor stage,
# gemini-3.8-flash @ global). google-genai raises 429 as ClientError, which
# the class-name check missed, so it was never retried.
REAL_GENAI_429 = {
    "error": {
        "code": 429,
        "message": "Resource exhausted. Please try again later. Please refer to "
                   "https://cloud.google.com/vertex-ai/generative-ai/docs/error-code-429 "
                   "for more details.",
        "status": "RESOURCE_EXHAUSTED",
    }
}


def test_genai_429_is_transient():
    assert _is_transient(genai_errors.ClientError(429, REAL_GENAI_429))


def test_genai_503_is_transient():
    body = {"error": {"code": 503, "message": "overloaded", "status": "UNAVAILABLE"}}
    assert _is_transient(genai_errors.ServerError(503, body))


def test_genai_404_is_not_transient():
    # A missing/retired model is permanent — retrying only delays the failure.
    body = {"error": {"code": 404, "message": "Publisher model not found",
                      "status": "NOT_FOUND"}}
    assert not _is_transient(genai_errors.ClientError(404, body))
