"""Иерархия фиатных и криптовалют, используемая всеми слоями сервиса."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from .exceptions import CurrencyNotFoundError, ValidationError
from .utils import normalize_currency_code


@dataclass(frozen=True, slots=True)
class Currency(ABC):
    """Базовый тип валюты с единым отображением в интерфейсе."""

    name: str
    code: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValidationError("Название валюты не может быть пустым")
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "code", normalize_currency_code(self.code))

    @abstractmethod
    def get_display_info(self) -> str:
        """Возвращает представление валюты для UI и журналов."""


@dataclass(frozen=True, slots=True)
class FiatCurrency(Currency):
    """Фиатная валюта с зоной эмиссии."""

    issuing_country: str

    def get_display_info(self) -> str:
        """Возвращает информацию о фиатной валюте."""
        return f"[FIAT] {self.code} — {self.name} (Issuing: {self.issuing_country})"


@dataclass(frozen=True, slots=True)
class CryptoCurrency(Currency):
    """Криптовалюта с алгоритмом и справочной капитализацией."""

    algorithm: str
    market_cap: float

    def get_display_info(self) -> str:
        """Возвращает информацию о криптовалюте."""
        return (
            f"[CRYPTO] {self.code} — {self.name} "
            f"(Algo: {self.algorithm}, MCAP: {self.market_cap:.2e})"
        )


CURRENCY_REGISTRY: dict[str, Currency] = {
    "USD": FiatCurrency("US Dollar", "USD", "United States"),
    "EUR": FiatCurrency("Euro", "EUR", "Eurozone"),
    "GBP": FiatCurrency("Pound Sterling", "GBP", "United Kingdom"),
    "RUB": FiatCurrency("Russian Ruble", "RUB", "Russia"),
    "BTC": CryptoCurrency("Bitcoin", "BTC", "SHA-256", 1.12e12),
    "ETH": CryptoCurrency("Ethereum", "ETH", "Ethash", 4.2e11),
    "SOL": CryptoCurrency("Solana", "SOL", "Proof of History", 7.0e10),
}


def get_currency(code: str) -> Currency:
    """Получает валюту по коду или сообщает об отсутствии поддержки."""
    normalized = normalize_currency_code(code)
    try:
        return CURRENCY_REGISTRY[normalized]
    except KeyError as error:
        raise CurrencyNotFoundError(normalized) from error
