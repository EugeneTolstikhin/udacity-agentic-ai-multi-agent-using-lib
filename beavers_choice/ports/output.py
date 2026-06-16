from __future__ import annotations

from typing import Iterable, Protocol

from beavers_choice.domain.models import EvaluationRow


class EvaluationOutputPort(Protocol):
    """Write and summarize evaluation output."""

    def write_results(self, rows: Iterable[EvaluationRow]) -> None:
        """Persist evaluation rows and print the validation summary."""

