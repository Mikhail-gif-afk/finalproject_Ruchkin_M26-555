"""Адаптер сохранения актуального кэша и журнала измерений курсов."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ..infra.database import DatabaseManager


class RatesStorage:
    """Сохраняет снимок ``rates.json`` и дедуплицированную историю измерений."""

    def __init__(self, database: DatabaseManager | None = None) -> None:
        self._database = database or DatabaseManager()

    def read_snapshot(self) -> dict[str, Any]:
        """Возвращает снимок текущих курсов."""
        return self._database.read("rates.json", {"pairs": {}, "last_refresh": None})

    def write_snapshot(self, pairs: dict[str, dict[str, Any]]) -> str:
        """Сохраняет последние курсы, не заменяя запись более старым значением."""
        snapshot = self.read_snapshot()
        current_pairs = snapshot.get("pairs", {})
        for key, value in pairs.items():
            previous = current_pairs.get(key)
            if previous is None or value["updated_at"] >= previous.get("updated_at", ""):
                current_pairs[key] = value
        refreshed_at = datetime.now(UTC).isoformat()
        self._database.write("rates.json", {"pairs": current_pairs, "last_refresh": refreshed_at})
        return refreshed_at

    def append_history(self, pairs: dict[str, dict[str, Any]]) -> None:
        """Добавляет в журнал только уникальные пару и момент измерения."""
        history = self._database.read("exchange_rates.json", [])
        known_ids = {entry["id"] for entry in history}
        for pair, value in pairs.items():
            from_code, to_code = pair.split("_", maxsplit=1)
            timestamp = value["updated_at"]
            record_id = f"{from_code}_{to_code}_{timestamp}"
            if record_id not in known_ids:
                history.append(
                    {
                        "id": record_id,
                        "from_currency": from_code,
                        "to_currency": to_code,
                        "rate": value["rate"],
                        "timestamp": timestamp,
                        "source": value["source"],
                    }
                )
                known_ids.add(record_id)
        self._database.write("exchange_rates.json", history)
