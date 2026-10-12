"""Интерактивный CLI: парсит команды и делегирует работу Core/Parser Service."""

from __future__ import annotations

import argparse
import shlex
from collections.abc import Callable

from prettytable import PrettyTable

from ..core.exceptions import RateNotFoundError, ValutaTradeError
from ..core.usecases import TradingService
from ..logging_config import configure_logging
from ..parser_service.updater import RatesUpdater


class CommandInterface:
    """Единственная точка входа пользовательских команд ValutaTrade Hub."""

    PROMPT = "valutatrade> "

    def __init__(
        self,
        service: TradingService | None = None,
        updater: RatesUpdater | None = None,
        output: Callable[[str], None] = print,
    ) -> None:
        configure_logging()
        self._service = service or TradingService()
        self._updater = updater
        self._output = output

    def execute(self, line: str) -> bool:
        """Выполняет одну строку; возвращает False только для команды выхода."""
        try:
            tokens = shlex.split(line, posix=False)
        except ValueError as error:
            self._output(f"Ошибка разбора команды: {error}")
            return True
        if not tokens:
            return True
        command, arguments = tokens[0].lower(), tokens[1:]
        if command in {"exit", "quit"}:
            self._output("До свидания!")
            return False
        if command == "help":
            self._print_help()
            return True
        handlers: dict[str, Callable[[list[str]], None]] = {
            "register": self._register,
            "login": self._login,
            "logout": self._logout,
            "show-portfolio": self._show_portfolio,
            "buy": self._buy,
            "sell": self._sell,
            "get-rate": self._get_rate,
            "update-rates": self._update_rates,
            "show-rates": self._show_rates,
        }
        handler = handlers.get(command)
        if handler is None:
            self._output(f"Неизвестная команда '{command}'. Введите help.")
            return True
        try:
            handler(arguments)
        except (ValutaTradeError, ValueError) as error:
            self._output(str(error))
        except SystemExit:
            self._output("Некорректные аргументы. Введите help для справки.")
        return True

    def _register(self, arguments: list[str]) -> None:
        parser = self._parser("register")
        parser.add_argument("--username", required=True)
        parser.add_argument("--password", required=True)
        args = parser.parse_args(arguments)
        user = self._service.register(args.username, args.password)
        self._output(f"Пользователь '{user.username}' зарегистрирован (id={user.user_id}).")
        self._output(f"Войдите: login --username {user.username} --password ****")

    def _login(self, arguments: list[str]) -> None:
        parser = self._parser("login")
        parser.add_argument("--username", required=True)
        parser.add_argument("--password", required=True)
        args = parser.parse_args(arguments)
        user = self._service.login(args.username, args.password)
        self._output(f"Вы вошли как '{user.username}'")

    def _logout(self, arguments: list[str]) -> None:
        self._no_arguments(arguments)
        self._service.logout()
        self._output("Сессия завершена")

    def _show_portfolio(self, arguments: list[str]) -> None:
        parser = self._parser("show-portfolio")
        parser.add_argument("--base", default="USD")
        args = parser.parse_args(arguments)
        portfolio, total = self._service.show_portfolio(args.base)
        wallets = portfolio.wallets
        if not wallets:
            self._output(f"Портфель пользователя '{portfolio.user.username}' пока пуст.")
            return
        table = PrettyTable(["Валюта", "Баланс", f"Стоимость, {args.base.upper()}"])
        table.align = "r"
        table.align["Валюта"] = "l"
        rates = self._service._rate_values()
        for code, wallet in sorted(wallets.items()):
            value = (
                wallet.balance
                if code == args.base.upper()
                else portfolio.get_total_value(
                    args.base.upper(),
                    {f"{code}_{args.base.upper()}": rates.get(f"{code}_{args.base.upper()}", 1)},
                )
                if len(wallets) == 1
                else self._wallet_value(code, wallet.balance, args.base.upper(), rates)
            )
            table.add_row([code, f"{wallet.balance:.4f}", f"{value:,.2f}"])
        self._output(
            f"Портфель пользователя '{portfolio.user.username}' (база: {args.base.upper()}):"
        )
        self._output(str(table))
        self._output(f"ИТОГО: {total:,.2f} {args.base.upper()}")

    @staticmethod
    def _wallet_value(code: str, balance: float, base: str, rates: dict[str, float]) -> float:
        if code == base:
            return balance
        direct = rates.get(f"{code}_{base}")
        inverse = rates.get(f"{base}_{code}")
        if direct:
            return balance * direct
        if inverse:
            return balance / inverse
        return 0.0

    def _buy(self, arguments: list[str]) -> None:
        parser = self._parser("buy")
        parser.add_argument("--currency", required=True)
        parser.add_argument("--amount", required=True, type=float)
        args = parser.parse_args(arguments)
        result = self._service.buy(args.currency, args.amount)
        self._output(
            f"Покупка выполнена: {result['amount']:.4f} {result['currency']} "
            f"по курсу {result['rate']:.4f} USD/{result['currency']}"
        )
        self._output(
            f"Изменения в портфеле: было {result['before']:.4f} → стало {result['after']:.4f}"
        )
        self._output(f"Оценочная стоимость покупки: {result['cost']:,.2f} USD")

    def _sell(self, arguments: list[str]) -> None:
        parser = self._parser("sell")
        parser.add_argument("--currency", required=True)
        parser.add_argument("--amount", required=True, type=float)
        args = parser.parse_args(arguments)
        result = self._service.sell(args.currency, args.amount)
        self._output(
            f"Продажа выполнена: {result['amount']:.4f} {result['currency']} "
            f"по курсу {result['rate']:.4f} USD/{result['currency']}"
        )
        self._output(
            f"Изменения в портфеле: было {result['before']:.4f} → стало {result['after']:.4f}"
        )
        self._output(f"Оценочная выручка: {result['proceeds']:,.2f} USD")

    def _get_rate(self, arguments: list[str]) -> None:
        parser = self._parser("get-rate")
        parser.add_argument("--from", dest="from_code", required=True)
        parser.add_argument("--to", dest="to_code", required=True)
        args = parser.parse_args(arguments)
        rate, updated_at = self._service.get_rate(args.from_code, args.to_code)
        self._output(
            f"Курс {args.from_code.upper()}→{args.to_code.upper()}: "
            f"{rate:.8f} (обновлено: {updated_at})"
        )

    def _update_rates(self, arguments: list[str]) -> None:
        parser = self._parser("update-rates")
        parser.add_argument("--source", choices=("coingecko", "exchangerate"))
        args = parser.parse_args(arguments)
        updater = self._updater or RatesUpdater()
        result = updater.run_update(args.source)
        if result["errors"]:
            self._output("Обновление завершено с ошибками:")
            for error in result["errors"]:
                self._output(f"- {error}")
        self._output(
            f"Обновление завершено. Получено курсов: {result['pairs']}. "
            f"Последнее обновление: {result['last_refresh']}"
        )

    def _show_rates(self, arguments: list[str]) -> None:
        parser = self._parser("show-rates")
        parser.add_argument("--currency")
        parser.add_argument("--top", type=int)
        parser.add_argument("--base")
        args = parser.parse_args(arguments)
        try:
            entries, refreshed_at = self._service.list_rates(args.currency, args.top, args.base)
        except RateNotFoundError as error:
            if str(error).startswith("Курс локальный кеш→пуст"):
                self._output(
                    "Локальный кеш курсов пуст. Выполните 'update-rates', чтобы загрузить данные."
                )
                return
            raise
        table = PrettyTable(["Пара", "Курс", "Обновлено"])
        table.align = "l"
        for pair, rate, updated_at in entries:
            table.add_row([pair, f"{rate:.8f}", updated_at])
        self._output(f"Курсы из кеша (обновлено: {refreshed_at}):")
        self._output(str(table))

    def _print_help(self) -> None:
        self._output(
            "Команды:\n"
            "  register --username <имя> --password <пароль>\n"
            "  login --username <имя> --password <пароль>\n"
            "  logout\n"
            "  show-portfolio [--base USD]\n"
            "  buy --currency BTC --amount 0.05\n"
            "  sell --currency BTC --amount 0.01\n"
            "  get-rate --from BTC --to USD\n"
            "  update-rates [--source coingecko|exchangerate]\n"
            "  show-rates [--currency BTC] [--top 2] [--base EUR]\n"
            "  help | exit"
        )

    @staticmethod
    def _parser(command: str) -> argparse.ArgumentParser:
        return argparse.ArgumentParser(prog=command, add_help=False)

    @staticmethod
    def _no_arguments(arguments: list[str]) -> None:
        if arguments:
            raise ValueError("Эта команда не принимает аргументы")


def main() -> None:
    """Запускает интерактивный цикл командной строки."""
    interface = CommandInterface()
    print("ValutaTrade Hub. Введите help для списка команд.")
    while True:
        try:
            line = input(CommandInterface.PROMPT)
        except (EOFError, KeyboardInterrupt):
            print("\nДо свидания!")
            return
        if not interface.execute(line):
            return
