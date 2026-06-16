from __future__ import annotations

import atexit
from pathlib import Path
from typing import Any

import logfire


class LogfireTelemetryAdapter:
    """Local Logfire tracing adapter."""

    def __init__(
        self,
        log_path: str | Path = "logfire.log",
        service_name: str = "beavers-choice-multi-agent",
        sqlalchemy_engine=None,
    ) -> None:
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.log_path.open("a", encoding="utf-8", buffering=1)
        logfire.configure(
            service_name=service_name,
            send_to_logfire=False,
            console=logfire.ConsoleOptions(
                output=self.stream,
                span_style="show-parents",
                include_timestamps=True,
                include_tags=True,
                verbose=True,
                show_project_link=False,
            ),
        )
        logfire.instrument_pydantic_ai()
        if sqlalchemy_engine is not None:
            logfire.instrument_sqlalchemy(engine=sqlalchemy_engine)
        atexit.register(self.close)

    def span(self, name: str, **attributes: Any):
        return logfire.span(name, **attributes)

    def info(self, message: str, **attributes: Any) -> None:
        logfire.info(message, **attributes)

    def exception(self, message: str, **attributes: Any) -> None:
        logfire.exception(message, **attributes)

    def flush(self) -> None:
        logfire.force_flush()
        self.stream.flush()

    def close(self) -> None:
        try:
            self.flush()
        finally:
            if not self.stream.closed:
                self.stream.close()

