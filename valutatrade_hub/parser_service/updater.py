"""Координация отказоустойчивого обновления курсов из нескольких источников."""

from __future__ import annotations

import logging
from typing import Any

from ..core.exceptions import ApiRequestError
from .api_clients import BaseApiClient, CoinGeckoClient, ExchangeRateApiClient, utc_now
from .storage import RatesStorage


class RatesUpdater:
    """Опрашивает источники и сохраняет объединённый валидный результат."""

    def __init__(
        self,
        clients: list[BaseApiClient] | None = None,
        storage: RatesStorage | None = None,
    ) -> None:
        self._clients = clients or [CoinGeckoClient(), ExchangeRateApiClient()]
        self._storage = storage or RatesStorage()
        self._logger = logging.getLogger("valutatrade.parser")

    def run_update(self, source: str | None = None) -> dict[str, Any]:
        """Обновляет все доступные источники, продолжая работу при частичных ошибках."""
        selected_clients = self._select_clients(source)
        pairs: dict[str, dict[str, Any]] = {}
        errors: list[str] = []
        self._logger.info("Starting rates update")
        for client in selected_clients:
            source_name = getattr(client, "source_name", client.__class__.__name__)
            try:
                fetched = client.fetch_rates()
                timestamp = utc_now()
                pairs.update(
                    {
                        pair: {"rate": rate, "updated_at": timestamp, "source": source_name}
                        for pair, rate in fetched.items()
                    }
                )
                self._logger.info("Fetched %s rates from %s", len(fetched), source_name)
            except ApiRequestError as error:
                errors.append(str(error))
                self._logger.error("Failed to fetch from %s: %s", source_name, error)
        if not pairs:
            raise ApiRequestError("ни один источник курсов не вернул данных")
        last_refresh = self._storage.write_snapshot(pairs)
        self._storage.append_history(pairs)
        self._logger.info("Rates update completed: %s pairs", len(pairs))
        return {"pairs": len(pairs), "errors": errors, "last_refresh": last_refresh}

    def _select_clients(self, source: str | None) -> list[BaseApiClient]:
        if source is None:
            return self._clients
        normalized = source.strip().lower()
        selected = [
            client
            for client in self._clients
            if normalized in getattr(client, "source_name", "").lower().replace("-", "")
        ]
        if not selected:
            raise ApiRequestError("источник должен быть coingecko или exchangerate")
        return selected
