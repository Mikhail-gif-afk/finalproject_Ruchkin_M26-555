"""Единый Singleton для конфигурации, читаемой из pyproject.toml."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any


class SettingsLoader:
    """Кэширует настройки приложения в одном экземпляре.

    Реализация через ``__new__`` выбрана за простоту и читаемость: каждый импорт
    получает один объект и не читает конфигурационный файл повторно.
    """

    _instance: SettingsLoader | None = None

    def __new__(cls) -> SettingsLoader:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance

    @staticmethod
    def project_root() -> Path:
        """Возвращает абсолютный путь к корню пакета."""
        return Path(__file__).resolve().parents[2]

    def _load(self) -> None:
        pyproject_path = self.project_root() / "pyproject.toml"
        with pyproject_path.open("rb") as file:
            document = tomllib.load(file)
        self._settings: dict[str, Any] = document.get("tool", {}).get("valutatrade", {})
        self._settings["data_dir"] = str(self.project_root() / "data")
        self._settings["logs_dir"] = str(self.project_root() / "logs")

    def get(self, key: str, default: Any = None) -> Any:
        """Возвращает значение настройки или переданный default."""
        return self._settings.get(key, default)

    def reload(self) -> None:
        """Перечитывает pyproject.toml для применения изменённых настроек."""
        self._load()
