"""
Retry decorator for transient errors (HTTP 429/5xx, network blips).
Built on tenacity. Safe to apply to idempotent ops (reads + writes guarded
by skip_if_exists / get_or_create).
"""
import logging

from googleapiclient.errors import HttpError
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

RETRYABLE_HTTP = {429, 500, 502, 503, 504}


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, HttpError):
        return exc.resp.status in RETRYABLE_HTTP
    if isinstance(exc, (ConnectionError, TimeoutError)):
        return True
    # google-genai surfaces server errors with these names; match by class name
    # to avoid a hard import dependency on internal SDK paths.
    name = type(exc).__name__
    return name in {"ServerError", "ServiceUnavailable", "DeadlineExceeded",
                    "ResourceExhausted", "APIError"}


with_retries = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=10),
    retry=retry_if_exception(_is_transient),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
