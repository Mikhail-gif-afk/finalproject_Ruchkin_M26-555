"""Единый интерфейс и реализации клиентов публичных API курсов."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

import requests

from ..core.exceptions import ApiRequestError
from .config import ParserConfig


class BaseApiClient(ABC):
    """Контракт любого внешнего поставщика курсов."""

    @abstractmethod
    def fetch_rates(self) -> dict[str, float]:
        """Получает пары в виде ``{'BTC_USD': 59337.21}``."""


class CoinGeckoClient(BaseApiClient):
    """Получает котировки криптовалют к USD из публичного CoinGecko API."""

    source_name = "CoinGecko"

    def __init__(self, config: ParserConfig | None = None) -> None:
        self._config = config or ParserConfig()

    def fetch_rates(self) -> dict[str, float]:
        """Запрашивает сразу все криптовалюты и нормализует ответ."""
        params = {
            "ids": ",".join(self._config.crypto_id_map.values()),
            "vs_currencies": self._config.base_currency.lower(),
        }
        try:
            response = requests.get(
                self._config.coingecko_url,
                params=params,
                timeout=self._config.request_timeout,
            )
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
        except (requests.RequestException, ValueError) as error:
            raise ApiRequestError(f"CoinGecko: {error}") from error
        base = self._config.base_currency.upper()
        result: dict[str, float] = {}
        for code, coin_id in self._config.crypto_id_map.items():
            try:
                result[f"{code}_{base}"] = float(payload[coin_id][base.lower()])
            except (KeyError, TypeError, ValueError) as error:
                raise ApiRequestError(f"CoinGecko: некорректный ответ для {code}") from error
        return result


class ExchangeRateApiClient(BaseApiClient):
    """Получает котировки фиатных валют из ExchangeRate-API."""

    source_name = "ExchangeRate-API"

    def __init__(self, config: ParserConfig | None = None) -> None:
        self._config = config or ParserConfig()

    def fetch_rates(self) -> dict[str, float]:
        """Возвращает прямые курсы ``валюта_USD`` из ответа API."""
        if not self._config.exchangerate_api_key:
            raise ApiRequestError("не задана переменная окружения EXCHANGERATE_API_KEY")
        url = (
            f"{self._config.exchangerate_api_url}/{self._config.exchangerate_api_key}/latest/"
            f"{self._config.base_currency}"
        )
        try:
            response = requests.get(url, timeout=self._config.request_timeout)
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
            if payload.get("result") != "success":
                raise ValueError(payload.get("error-type", "неуспешный ответ"))
            rates = (
                payload["conversion_rates"] if "conversion_rates" in payload else payload["rates"]
            )
        except (requests.RequestException, KeyError, TypeError, ValueError) as error:
            raise ApiRequestError(f"ExchangeRate-API: {error}") from error
        result: dict[str, float] = {}
        for code in self._config.fiat_currencies:
            try:
                # API сообщает USD -> currency; Core хранит currency -> USD.
                result[f"{code}_{self._config.base_currency}"] = 1 / float(rates[code])
            except (KeyError, ValueError, ZeroDivisionError) as error:
                raise ApiRequestError(f"ExchangeRate-API: некорректный курс {code}") from error
        return result


def utc_now() -> str:
    """Даёт ISO-время в UTC для записей Parser Service."""
    return datetime.now(UTC).isoformat()
