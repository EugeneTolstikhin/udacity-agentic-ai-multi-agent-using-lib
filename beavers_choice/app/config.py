from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import dotenv


@dataclass(frozen=True)
class AppConfig:
    """Runtime configuration for production adapters."""

    database_url: str = "sqlite:///beaver_choice.db"
    data_dir: Path = Path(".")
    results_path: Path = Path("test_results.csv")
    logfire_log_file: Path = Path("logfire.log")
    openai_api_key: str = ""
    openai_base_url: str = "https://openai.vocareum.com/v1"
    openai_model_name: str = "gpt-4o-mini"

    @classmethod
    def from_env(cls) -> "AppConfig":
        dotenv.load_dotenv()
        return cls(
            database_url=os.getenv("BEAVERS_CHOICE_DATABASE_URL", "sqlite:///beaver_choice.db"),
            data_dir=Path(os.getenv("BEAVERS_CHOICE_DATA_DIR", ".")),
            results_path=Path(os.getenv("BEAVERS_CHOICE_RESULTS_FILE", "test_results.csv")),
            logfire_log_file=Path(os.getenv("LOGFIRE_LOG_FILE", "logfire.log")),
            openai_api_key=os.getenv("UDACITY_OPENAI_API_KEY", ""),
            openai_base_url=os.getenv(
                "UDACITY_OPENAI_API_BASE_URL",
                "https://openai.vocareum.com/v1",
            ),
            openai_model_name=os.getenv("UDACITY_OPENAI_MODEL", "gpt-4o-mini"),
        )

    def require_openai_key(self) -> None:
        if not self.openai_api_key:
            raise RuntimeError(
                "UDACITY_OPENAI_API_KEY is required. Add it to .env before running the project."
            )

