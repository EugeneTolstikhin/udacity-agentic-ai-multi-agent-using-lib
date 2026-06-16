from __future__ import annotations

from contextlib import AbstractContextManager, nullcontext
from types import TracebackType
from typing import Any, Optional, Protocol, Type


class TelemetryPort(Protocol):
    """Trace/log workflow events without binding the app to a tracing framework."""

    def span(self, name: str, **attributes: Any) -> AbstractContextManager[Any]:
        """Open a tracing span."""

    def info(self, message: str, **attributes: Any) -> None:
        """Record an info event."""

    def exception(self, message: str, **attributes: Any) -> None:
        """Record an exception event."""

    def flush(self) -> None:
        """Flush buffered telemetry."""


class NoopTelemetry:
    """Telemetry adapter for tests and offline workflows."""

    def span(self, name: str, **attributes: Any) -> AbstractContextManager[Any]:
        return nullcontext()

    def info(self, message: str, **attributes: Any) -> None:
        return None

    def exception(self, message: str, **attributes: Any) -> None:
        return None

    def flush(self) -> None:
        return None


class NullSpan:
    """Concrete span helper when an explicit object is needed."""

    def __enter__(self) -> "NullSpan":
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> bool:
        return False

