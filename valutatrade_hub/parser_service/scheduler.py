"""Простой планировщик ручного периодического обновления курсов."""

from __future__ import annotations

import time

from .updater import RatesUpdater


def run_periodically(interval_seconds: int, updater: RatesUpdater | None = None) -> None:
    """Запускает обновление через заданные интервалы до прерывания пользователем."""
    service = updater or RatesUpdater()
    while True:
        service.run_update()
        time.sleep(interval_seconds)
