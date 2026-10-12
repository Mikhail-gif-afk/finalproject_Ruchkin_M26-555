"""Предметные сущности пользователя, кошелька и портфеля."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime
from numbers import Real
from typing import Any

from .exceptions import InsufficientFundsError, ValidationError
from .utils import normalize_currency_code, validate_positive_amount


class User:
    """Пользователь с солёным SHA-256 хешем вместо открытого пароля."""

    def __init__(
        self,
        user_id: int,
        username: str,
        hashed_password: str,
        salt: str,
        registration_date: datetime,
    ) -> None:
        self._user_id = int(user_id)
        self.username = username
        self._hashed_password = hashed_password
        self._salt = salt
        self._registration_date = registration_date

    @classmethod
    def create(cls, user_id: int, username: str, password: str) -> User:
        """Создаёт пользователя, генерируя соль и безопасный хеш пароля."""
        cls._validate_password(password)
        salt = secrets.token_hex(16)
        hashed_password = cls._hash_password(password, salt)
        return cls(user_id, username, hashed_password, salt, datetime.now().astimezone())

    @staticmethod
    def _hash_password(password: str, salt: str) -> str:
        return hashlib.sha256(f"{password}{salt}".encode()).hexdigest()

    @staticmethod
    def _validate_password(password: str) -> None:
        if not isinstance(password, str) or len(password) < 4:
            raise ValidationError("Пароль должен быть не короче 4 символов")

    @property
    def user_id(self) -> int:
        """Возвращает неизменяемый идентификатор пользователя."""
        return self._user_id

    @property
    def username(self) -> str:
        """Возвращает имя пользователя."""
        return self._username

    @username.setter
    def username(self, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValidationError("Имя пользователя не может быть пустым")
        self._username = value.strip()

    @property
    def registration_date(self) -> datetime:
        """Возвращает дату регистрации."""
        return self._registration_date

    def change_password(self, new_password: str) -> None:
        """Меняет пароль, сохраняя только новый солёный хеш."""
        self._validate_password(new_password)
        self._salt = secrets.token_hex(16)
        self._hashed_password = self._hash_password(new_password, self._salt)

    def verify_password(self, password: str) -> bool:
        """Сравнивает хеш введённого пароля с сохранённым хешем."""
        if not isinstance(password, str):
            return False
        return secrets.compare_digest(
            self._hashed_password, self._hash_password(password, self._salt)
        )

    def get_user_info(self) -> dict[str, Any]:
        """Сериализует публичную информацию без пароля и соли."""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "registration_date": self.registration_date.isoformat(),
        }

    def to_dict(self) -> dict[str, Any]:
        """Сериализует пользователя для внутреннего JSON-хранилища."""
        return {
            **self.get_user_info(),
            "hashed_password": self._hashed_password,
            "salt": self._salt,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> User:
        """Восстанавливает пользователя из JSON-представления."""
        return cls(
            user_id=data["user_id"],
            username=data["username"],
            hashed_password=data["hashed_password"],
            salt=data["salt"],
            registration_date=datetime.fromisoformat(data["registration_date"]),
        )


class Wallet:
    """Кошелёк одной валюты с инвариантом неотрицательного баланса."""

    def __init__(self, currency_code: str, balance: float = 0.0) -> None:
        self.currency_code = normalize_currency_code(currency_code)
        self.balance = balance

    @property
    def balance(self) -> float:
        """Возвращает текущий баланс кошелька."""
        return self._balance

    @balance.setter
    def balance(self, value: float) -> None:
        if isinstance(value, bool) or not isinstance(value, Real) or float(value) < 0:
            raise ValidationError("Баланс должен быть неотрицательным числом")
        self._balance = float(value)

    def deposit(self, amount: float) -> float:
        """Пополняет кошелёк и возвращает новый баланс."""
        self.balance += validate_positive_amount(amount)
        return self.balance

    def withdraw(self, amount: float) -> float:
        """Списывает сумму, не позволяя балансу стать отрицательным."""
        valid_amount = validate_positive_amount(amount)
        if valid_amount > self.balance:
            raise InsufficientFundsError(self.balance, valid_amount, self.currency_code)
        self.balance -= valid_amount
        return self.balance

    def get_balance_info(self) -> str:
        """Возвращает удобную для CLI строку с балансом."""
        return f"{self.currency_code}: {self.balance:.4f}"

    def to_dict(self) -> dict[str, float | str]:
        """Сериализует кошелёк для JSON-хранилища."""
        return {"currency_code": self.currency_code, "balance": self.balance}


class Portfolio:
    """Набор валютных кошельков одного пользователя."""

    def __init__(self, user: User, wallets: dict[str, Wallet] | None = None) -> None:
        self._user = user
        self._wallets = dict(wallets or {})

    @property
    def user(self) -> User:
        """Возвращает владельца портфеля без возможности переназначения."""
        return self._user

    @property
    def wallets(self) -> dict[str, Wallet]:
        """Возвращает копию словаря кошельков."""
        return dict(self._wallets)

    def add_currency(self, currency_code: str) -> Wallet:
        """Создаёт отсутствующий кошелёк или возвращает существующий."""
        code = normalize_currency_code(currency_code)
        if code not in self._wallets:
            self._wallets[code] = Wallet(code)
        return self._wallets[code]

    def get_wallet(self, currency_code: str) -> Wallet | None:
        """Возвращает кошелёк по коду или None, если его нет."""
        return self._wallets.get(normalize_currency_code(currency_code))

    def get_total_value(self, base_currency: str, rates: dict[str, float]) -> float:
        """Считает стоимость всех кошельков в базовой валюте."""
        base = normalize_currency_code(base_currency)
        total = 0.0
        for code, wallet in self._wallets.items():
            if code == base:
                total += wallet.balance
                continue
            direct_key = f"{code}_{base}"
            inverse_key = f"{base}_{code}"
            if direct_key in rates:
                total += wallet.balance * float(rates[direct_key])
            elif inverse_key in rates:
                total += wallet.balance / float(rates[inverse_key])
            else:
                raise ValidationError(f"Не удалось получить курс для {code}→{base}")
        return total

    def to_dict(self) -> dict[str, Any]:
        """Сериализует портфель для JSON-хранилища."""
        return {
            "user_id": self.user.user_id,
            "wallets": {code: wallet.to_dict() for code, wallet in self._wallets.items()},
        }
