"""Потокобезопасное JSON-хранилище с атомарной записью."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from .settings import SettingsLoader


class DatabaseManager:
    """Singleton-адаптер над JSON-файлами данных приложения."""

    _instance: DatabaseManager | None = None

    def __new__(cls) -> DatabaseManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._lock = threading.RLock()
            cls._instance._data_dir = Path(SettingsLoader().get("data_dir"))
            cls._instance._data_dir.mkdir(parents=True, exist_ok=True)
        return cls._instance

    def _path(self, name: str) -> Path:
        path = (self._data_dir / name).resolve()
        if path.parent != self._data_dir.resolve() or path.suffix != ".json":
            raise ValueError("Допускаются только JSON-файлы из каталога data")
        return path

    def read(self, name: str, default: Any) -> Any:
        """Читает JSON или возвращает default для отсутствующего/пустого файла."""
        path = self._path(name)
        with self._lock:
            if not path.exists() or not path.read_text(encoding="utf-8").strip():
                return default
            with path.open("r", encoding="utf-8") as file:
                return json.load(file)

    def write(self, name: str, data: Any) -> None:
        """Атомарно записывает JSON как UTF-8 без потери кириллицы."""
        path = self._path(name)
        temporary_path = path.with_suffix(".tmp")
        with self._lock:
            with temporary_path.open("w", encoding="utf-8", newline="\n") as file:
                json.dump(data, file, ensure_ascii=False, indent=2)
                file.write("\n")
            temporary_path.replace(path)
