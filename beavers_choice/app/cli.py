from __future__ import annotations

from beavers_choice.app.container import AppContainer


def main() -> None:
    container = AppContainer.production()
    container.evaluation.run()

