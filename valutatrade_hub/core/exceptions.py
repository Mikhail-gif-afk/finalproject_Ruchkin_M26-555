"""Доменные исключения с понятными сообщениями для CLI."""


class ValutaTradeError(Exception):
    """Базовое исключение предметной области."""


class ValidationError(ValutaTradeError):
    """Входные данные не удовлетворяют правилам предметной области."""


class AuthenticationError(ValutaTradeError):
    """Ошибка аутентификации пользователя."""


class NotLoggedInError(ValutaTradeError):
    """Операция требует активной пользовательской сессии."""


class CurrencyNotFoundError(ValutaTradeError):
    """Запрошенный код валюты не зарегистрирован в приложении."""

    def __init__(self, code: str) -> None:
        super().__init__(f"Неизвестная валюта '{code}'")


class InsufficientFundsError(ValutaTradeError):
    """На кошельке недостаточно средств для списания."""

    def __init__(self, available: float, required: float, code: str) -> None:
        super().__init__(
            "Недостаточно средств: "
            f"доступно {available:.4f} {code}, требуется {required:.4f} {code}"
        )


class ApiRequestError(ValutaTradeError):
    """Внешний источник курсов недоступен или вернул некорректные данные."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"Ошибка при обращении к внешнему API: {reason}")


class RateNotFoundError(ValutaTradeError):
    """Курс валютной пары отсутствует в кэше и не может быть получен."""

    def __init__(self, from_code: str, to_code: str) -> None:
        super().__init__(f"Курс {from_code}→{to_code} недоступен. Повторите попытку позже.")


class StaleRateError(ValutaTradeError):
    """Кэш курсов устарел и требует обновления."""

    def __init__(self) -> None:
        super().__init__("Кэш курсов устарел. Выполните 'update-rates' и повторите попытку.")
