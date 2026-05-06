"""
Verify the with_retries decorator retries on transient errors and not on
non-transient ones.
"""
from unittest.mock import Mock

import pytest
from googleapiclient.errors import HttpError

from src.utils.retry import with_retries, _is_transient


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
