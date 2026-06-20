"""HTTP GET with browser UA, tenacity retry/backoff, and circuit breaker."""
from __future__ import annotations

import time
import random
from dataclasses import dataclass, field

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_fixed,
    RetryCallState,
)

from ingest.errors import (
    TransientError,
    NotFoundError,
    ForbiddenError,
    IngestError,
    CircuitBreakerOpen,
)

_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_DEFAULT_HEADERS = {
    "User-Agent": _BROWSER_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}
_REQUEST_TIMEOUT = 30  # seconds


@dataclass
class CircuitBreaker:
    threshold: int = 10
    _consecutive: int = field(default=0, init=False, repr=False)

    def record_success(self) -> None:
        self._consecutive = 0

    def record_failure(self) -> None:
        self._consecutive += 1
        if self._consecutive >= self.threshold:
            raise CircuitBreakerOpen(
                f"Circuit breaker open: {self._consecutive} consecutive "
                "transient failures — possible block or outage. Aborting run."
            )

    def reset(self) -> None:
        self._consecutive = 0


def _raise_for_status(response: requests.Response, url: str) -> None:
    code = response.status_code
    if code == 404:
        raise NotFoundError(f"HTTP 404: {url}")
    if code == 403:
        raise ForbiddenError(f"HTTP 403: {url}")
    if code == 429:
        raise TransientError(f"HTTP 429 rate-limited: {url}")
    if code >= 500:
        raise TransientError(f"HTTP {code} server error: {url}")
    if code >= 400:
        raise IngestError(category="unknown", message=f"HTTP {code}: {url}")
    response.raise_for_status()


def _make_get(url: str) -> requests.Response:
    """Single GET attempt; raises typed IngestError on failure."""
    try:
        response = requests.get(url, headers=_DEFAULT_HEADERS, timeout=_REQUEST_TIMEOUT)
    except requests.exceptions.ConnectionError as exc:
        raise TransientError(f"Connection error: {exc}") from exc
    except requests.exceptions.Timeout as exc:
        raise TransientError(f"Timeout: {exc}") from exc
    except requests.exceptions.RequestException as exc:
        raise TransientError(f"Request failed: {exc}") from exc
    _raise_for_status(response, url)
    return response


def get(url: str, circuit_breaker: CircuitBreaker | None = None) -> requests.Response:
    """
    GET *url* with retry on transient errors.

    Retry schedule (tenacity):
    - 429 → fixed 5s / 15s / 45s waits (3 attempts total)
    - 5xx / network → fixed 2s / 8s / 32s waits (3 attempts total)

    Non-transient errors (404, 403, parse) propagate immediately.
    On final transient failure, records to circuit_breaker if provided.
    """

    def _before_retry_429(state: RetryCallState) -> None:
        waits = [5, 15, 45]
        n = state.attempt_number - 1
        time.sleep(waits[min(n, len(waits) - 1)])

    def _before_retry_5xx(state: RetryCallState) -> None:
        waits = [2, 8, 32]
        n = state.attempt_number - 1
        time.sleep(waits[min(n, len(waits) - 1)])

    # We implement retry manually (two separate policies) rather than stacking
    # tenacity decorators, to keep wait schedules independent.
    last_exc: TransientError | None = None
    for attempt in range(3):
        try:
            resp = _make_get(url)
            if circuit_breaker:
                circuit_breaker.record_success()
            return resp
        except TransientError as exc:
            last_exc = exc
            if "429" in str(exc):
                waits = [0, 5, 15]
                time.sleep(waits[attempt])
            else:
                waits = [0, 2, 8]
                time.sleep(waits[attempt])

    if circuit_breaker:
        circuit_breaker.record_failure()
    raise last_exc  # type: ignore[misc]


def polite_delay(base: float = 1.5, jitter: float = 0.5) -> None:
    """Sleep for base ± jitter seconds between requests."""
    time.sleep(base + random.uniform(-jitter, jitter))
