"""Проверки ключевых доменных инвариантов проекта."""

from datetime import UTC, datetime

import pytest
from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import (
    CurrencyNotFoundError,
    InsufficientFundsError,
    ValidationError,
)
from valutatrade_hub.core.models import User, Wallet


def test_user_hashes_password_and_hides_secret() -> None:
    user = User.create(1, "Тест", "1234")
    assert user.verify_password("1234")
    assert not user.verify_password("wrong")
    assert "hashed_password" not in user.get_user_info()
    assert user.to_dict()["hashed_password"] != "1234"


def test_wallet_rejects_negative_balance_and_insufficient_withdrawal() -> None:
    wallet = Wallet("USD", 10)
    wallet.deposit(5)
    assert wallet.balance == 15
    with pytest.raises(InsufficientFundsError, match="Недостаточно средств"):
        wallet.withdraw(16)
    with pytest.raises(ValidationError):
        wallet.deposit(0)


def test_currency_factory_and_validation() -> None:
    assert get_currency("btc").get_display_info().startswith("[CRYPTO] BTC")
    with pytest.raises(CurrencyNotFoundError, match="Неизвестная валюта"):
        get_currency("ABC")


def test_registration_date_is_timezone_aware() -> None:
    user = User.create(1, "alice", "1234")
    assert user.registration_date.tzinfo is not None
    assert datetime.now(UTC) >= user.registration_date.astimezone(UTC)
