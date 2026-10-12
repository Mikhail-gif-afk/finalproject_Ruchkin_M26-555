"""Настройка ротационного журнала доменных операций и Parser Service."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .infra.settings import SettingsLoader


def configure_logging() -> None:
    """Один раз настраивает INFO-логи в ``logs/actions.log`` и ``logs/parser.log``."""
    logs_dir = Path(SettingsLoader().get("logs_dir"))
    logs_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(SettingsLoader().get("log_format"))

    for logger_name, filename in (
        ("valutatrade.actions", "actions.log"),
        ("valutatrade.parser", "parser.log"),
    ):
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.INFO)
        logger.propagate = False
        if logger.handlers:
            continue
        handler = RotatingFileHandler(
            logs_dir / filename,
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
