"""Декораторы для аудита доменных операций."""

from __future__ import annotations

import logging
from collections.abc import Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")


def log_action(action: str, *, verbose: bool = False) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Логирует успех и ошибку действия, не перехватывая исключения."""

    def decorator(function: Callable[P, T]) -> Callable[P, T]:
        @wraps(function)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            logger = logging.getLogger("valutatrade.actions")
            fields: dict[str, Any] = {"action": action, **kwargs}
            if verbose:
                fields["args_count"] = len(args)
            try:
                result = function(*args, **kwargs)
            except Exception as error:
                logger.info(
                    "%s result=ERROR error_type=%s error_message=%s",
                    fields,
                    type(error).__name__,
                    error,
                )
                raise
            logger.info("%s result=OK", fields)
            return result

        return wrapper

    return decorator
