"""Валидации и арифметика валютных курсов."""

from __future__ import annotations

from numbers import Real

from .exceptions import ValidationError


def normalize_currency_code(code: str) -> str:
    """Возвращает корректный валютный код в верхнем регистре."""
    if not isinstance(code, str):
        raise ValidationError("Код валюты должен быть строкой")
    normalized = code.strip().upper()
    if not 2 <= len(normalized) <= 5 or not normalized.isalpha():
        raise ValidationError("Код валюты должен содержать 2-5 букв верхнего регистра")
    return normalized


def validate_positive_amount(amount: float) -> float:
    """Проверяет, что сумма является положительным конечным числом."""
    if isinstance(amount, bool) or not isinstance(amount, Real):
        raise ValidationError("'amount' должен быть положительным числом")
    result = float(amount)
    if result <= 0:
        raise ValidationError("'amount' должен быть положительным числом")
    return result


def pair_key(from_code: str, to_code: str) -> str:
    """Формирует ключ пары из двух валидированных валютных кодов."""
    return f"{normalize_currency_code(from_code)}_{normalize_currency_code(to_code)}"


def convert_amount(amount: float, rate: float) -> float:
    """Конвертирует сумму по прямому курсу, валидируя оба операнда."""
    valid_amount = validate_positive_amount(amount)
    if isinstance(rate, bool) or not isinstance(rate, Real) or float(rate) <= 0:
        raise ValidationError("Курс должен быть положительным числом")
    return valid_amount * float(rate)
