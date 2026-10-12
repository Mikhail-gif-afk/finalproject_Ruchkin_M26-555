"""Настройки Parser Service без хранения секретов в исходном коде."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ParserConfig:
    """Контракт источников, валют и сетевых параметров Parser Service."""

    exchangerate_api_key: str | None = field(
        default_factory=lambda: os.getenv("EXCHANGERATE_API_KEY")
    )
    coingecko_url: str = "https://api.coingecko.com/api/v3/simple/price"
    exchangerate_api_url: str = "https://v6.exchangerate-api.com/v6"
    base_currency: str = "USD"
    fiat_currencies: tuple[str, ...] = ("EUR", "GBP", "RUB")
    crypto_currencies: tuple[str, ...] = ("BTC", "ETH", "SOL")
    crypto_id_map: dict[str, str] = field(
        default_factory=lambda: {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana"}
    )
    request_timeout: int = 10
