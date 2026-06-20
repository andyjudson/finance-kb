"""Error categories and result types for the ingestion pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ErrorCategory = Literal["transient", "not_found", "forbidden", "parse", "unknown"]


@dataclass
class IngestError(Exception):
    category: ErrorCategory
    message: str

    def __str__(self) -> str:
        return f"[{self.category}] {self.message}"


class TransientError(IngestError):
    def __init__(self, message: str) -> None:
        super().__init__(category="transient", message=message)


class NotFoundError(IngestError):
    def __init__(self, message: str) -> None:
        super().__init__(category="not_found", message=message)


class ForbiddenError(IngestError):
    def __init__(self, message: str) -> None:
        super().__init__(category="forbidden", message=message)


class ParseError(IngestError):
    def __init__(self, message: str) -> None:
        super().__init__(category="parse", message=message)


class CircuitBreakerOpen(Exception):
    """Raised when too many consecutive transient failures occur."""
