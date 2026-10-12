"""Сценарии Core Service; здесь концентрируется бизнес-логика, а не CLI."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ..decorators import log_action
from ..infra.database import DatabaseManager
from ..infra.settings import SettingsLoader
from .currencies import get_currency
from .exceptions import (
    AuthenticationError,
    CurrencyNotFoundError,
    NotLoggedInError,
    RateNotFoundError,
    StaleRateError,
    ValidationError,
)
from .models import Portfolio, User, Wallet
from .utils import normalize_currency_code, validate_positive_amount


class TradingService:
    """Управляет регистрацией, сессией, портфелями и торговыми операциями."""

    def __init__(
        self,
        database: DatabaseManager | None = None,
        settings: SettingsLoader | None = None,
    ) -> None:
        self._database = database or DatabaseManager()
        self._settings = settings or SettingsLoader()
        self._current_user_id: int | None = None

    def register(self, username: str, password: str) -> User:
        """Регистрирует уникального пользователя и создаёт пустой портфель."""
        users = self._load_users()
        if any(item["username"].casefold() == username.strip().casefold() for item in users):
            raise ValidationError(f"Имя пользователя '{username}' уже занято")
        next_user_id = max((int(item["user_id"]) for item in users), default=0) + 1
        user = User.create(next_user_id, username, password)
        users.append(user.to_dict())
        portfolios = self._database.read("portfolios.json", [])
        portfolios.append({"user_id": user.user_id, "wallets": {}})
        self._database.write("users.json", users)
        self._database.write("portfolios.json", portfolios)
        return user

    def login(self, username: str, password: str) -> User:
        """Проверяет учётные данные и фиксирует пользователя текущей сессии."""
        user = self._find_user_by_username(username)
        if user is None:
            raise AuthenticationError(f"Пользователь '{username}' не найден")
        if not user.verify_password(password):
            raise AuthenticationError("Неверный пароль")
        self._current_user_id = user.user_id
        return user

    def logout(self) -> None:
        """Завершает текущую CLI-сессию."""
        self._current_user_id = None

    @property
    def current_user(self) -> User:
        """Возвращает активного пользователя или сообщает о необходимости входа."""
        if self._current_user_id is None:
            raise NotLoggedInError("Сначала выполните login")
        user = self._find_user_by_id(self._current_user_id)
        if user is None:
            self._current_user_id = None
            raise NotLoggedInError("Сначала выполните login")
        return user

    def show_portfolio(self, base_currency: str = "USD") -> tuple[Portfolio, float]:
        """Возвращает портфель пользователя и его общую стоимость в базе."""
        portfolio = self._load_portfolio(self.current_user)
        base = normalize_currency_code(base_currency)
        get_currency(base)
        rates = self._rate_values()
        return portfolio, portfolio.get_total_value(base, rates) if portfolio.wallets else 0.0

    @log_action("BUY", verbose=True)
    def buy(self, currency_code: str, amount: float) -> dict[str, float | str]:
        """Покупает валюту: списывает USD и пополняет целевой кошелёк."""
        user = self.current_user
        code = normalize_currency_code(currency_code)
        get_currency(code)
        amount_value = validate_positive_amount(amount)
        portfolio = self._load_portfolio(user)
        rate, _ = self.get_rate(code, "USD", require_fresh=False)
        cost = amount_value * rate
        usd_wallet = portfolio.add_currency("USD")
        if code != "USD":
            usd_wallet.withdraw(cost)
            target_wallet = portfolio.add_currency(code)
            before = target_wallet.balance
            target_wallet.deposit(amount_value)
            after = target_wallet.balance
        else:
            before = usd_wallet.balance
            usd_wallet.deposit(amount_value)
            after = usd_wallet.balance
        self._save_portfolio(portfolio)
        return {
            "currency": code,
            "amount": amount_value,
            "rate": rate,
            "cost": cost,
            "before": before,
            "after": after,
        }

    @log_action("SELL", verbose=True)
    def sell(self, currency_code: str, amount: float) -> dict[str, float | str]:
        """Продаёт валюту: списывает её и начисляет USD по текущему курсу."""
        user = self.current_user
        code = normalize_currency_code(currency_code)
        get_currency(code)
        amount_value = validate_positive_amount(amount)
        portfolio = self._load_portfolio(user)
        wallet = portfolio.get_wallet(code)
        if wallet is None:
            raise ValidationError(
                f"У вас нет кошелька '{code}'. "
                "Добавьте валюту: она создаётся автоматически при первой покупке."
            )
        rate, _ = self.get_rate(code, "USD", require_fresh=False)
        before = wallet.balance
        wallet.withdraw(amount_value)
        after = wallet.balance
        proceeds = amount_value * rate
        if code != "USD":
            portfolio.add_currency("USD").deposit(proceeds)
        self._save_portfolio(portfolio)
        return {
            "currency": code,
            "amount": amount_value,
            "rate": rate,
            "proceeds": proceeds,
            "before": before,
            "after": after,
        }

    def get_rate(
        self,
        from_code: str,
        to_code: str,
        *,
        require_fresh: bool = True,
    ) -> tuple[float, str]:
        """Получает прямой или обратный курс из кэша, контролируя TTL."""
        source = normalize_currency_code(from_code)
        target = normalize_currency_code(to_code)
        get_currency(source)
        get_currency(target)
        if source == target:
            return 1.0, datetime.now(UTC).isoformat()
        snapshot = self._database.read("rates.json", {"pairs": {}, "last_refresh": None})
        pairs = snapshot.get("pairs", {})
        direct_key = f"{source}_{target}"
        inverse_key = f"{target}_{source}"
        if direct_key in pairs:
            item = pairs[direct_key]
            rate = float(item["rate"])
        elif inverse_key in pairs:
            item = pairs[inverse_key]
            rate = 1 / float(item["rate"])
        else:
            raise RateNotFoundError(source, target)
        updated_at = str(item["updated_at"])
        if require_fresh and not self._is_fresh(updated_at):
            raise StaleRateError()
        return rate, updated_at

    def list_rates(
        self,
        currency: str | None = None,
        top: int | None = None,
        base: str | None = None,
    ) -> tuple[list[tuple[str, float, str]], str | None]:
        """Возвращает отфильтрованный и отсортированный список локальных курсов."""
        snapshot = self._database.read("rates.json", {"pairs": {}, "last_refresh": None})
        pairs = snapshot.get("pairs", {})
        if not pairs:
            raise RateNotFoundError("локальный кеш", "пуст")
        normalized_currency = normalize_currency_code(currency) if currency else None
        normalized_base = normalize_currency_code(base) if base else None
        entries: list[tuple[str, float, str]] = []
        for pair, item in pairs.items():
            from_code, to_code = pair.split("_", maxsplit=1)
            if normalized_currency and normalized_currency not in (from_code, to_code):
                continue
            if normalized_base and normalized_base != to_code:
                try:
                    value, updated = self.get_rate(from_code, normalized_base, require_fresh=False)
                    entries.append((f"{from_code}_{normalized_base}", value, updated))
                except (CurrencyNotFoundError, RateNotFoundError):
                    continue
            else:
                entries.append((pair, float(item["rate"]), str(item["updated_at"])))
        if not entries:
            code = normalized_currency or normalized_base or "запрошенной"
            raise RateNotFoundError(code, "USD")
        entries.sort(key=(lambda item: item[1]), reverse=top is not None)
        if top is not None:
            if top <= 0:
                raise ValidationError("'top' должен быть положительным числом")
            entries = entries[:top]
        return entries, snapshot.get("last_refresh")

    def _load_users(self) -> list[dict[str, Any]]:
        return self._database.read("users.json", [])

    def _find_user_by_username(self, username: str) -> User | None:
        for item in self._load_users():
            if item["username"].casefold() == username.strip().casefold():
                return User.from_dict(item)
        return None

    def _find_user_by_id(self, user_id: int) -> User | None:
        for item in self._load_users():
            if int(item["user_id"]) == user_id:
                return User.from_dict(item)
        return None

    def _load_portfolio(self, user: User) -> Portfolio:
        portfolios = self._database.read("portfolios.json", [])
        for item in portfolios:
            if int(item["user_id"]) == user.user_id:
                wallets = {
                    code: Wallet(payload.get("currency_code", code), payload["balance"])
                    for code, payload in item.get("wallets", {}).items()
                }
                return Portfolio(user, wallets)
        return Portfolio(user)

    def _save_portfolio(self, portfolio: Portfolio) -> None:
        portfolios = self._database.read("portfolios.json", [])
        serialized = portfolio.to_dict()
        for index, item in enumerate(portfolios):
            if int(item["user_id"]) == portfolio.user.user_id:
                portfolios[index] = serialized
                break
        else:
            portfolios.append(serialized)
        self._database.write("portfolios.json", portfolios)

    def _rate_values(self) -> dict[str, float]:
        snapshot = self._database.read("rates.json", {"pairs": {}})
        return {pair: float(item["rate"]) for pair, item in snapshot.get("pairs", {}).items()}

    def _is_fresh(self, updated_at: str) -> bool:
        try:
            timestamp = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        except ValueError:
            return False
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        return (datetime.now(UTC) - timestamp).total_seconds() <= int(
            self._settings.get("rates_ttl_seconds", 300)
        )
