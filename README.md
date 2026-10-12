# ValutaTrade Hub

Консольная платформа для регистрации пользователей, виртуальных валютных кошельков, торговли и просмотра курсов `finalproject_Ручкин_М26-555`.

Автор проекта: Ручкин, группа М26-555. GitHub: [Mikhail-gif-afk](https://github.com/Mikhail-gif-afk).

## Возможности

- регистрация и вход без хранения открытых паролей: соль и SHA-256;
- кошельки USD, EUR, GBP, RUB, BTC, ETH и SOL;
- команды `buy`, `sell`, `show-portfolio` и `get-rate`;
- TTL-проверка локального кэша курсов;
- Parser Service с клиентами CoinGecko и ExchangeRate-API;
- атомарная запись `rates.json` и история измерений в `exchange_rates.json`;
- Singleton-настройки и JSON DatabaseManager;
- ротационные UTF-8 журналы действий и обновлений;
- Ruff, типизированные модели и тесты.

## Установка

Требуется Python 3.12+ и uv.

```powershell
uv sync
uv run ruff check .
uv run pytest
```

## Запуск

```powershell
uv run python main.py
```

Пример полного цикла:

```text
register --username alice --password 1234
login --username alice --password 1234
buy --currency USD --amount 1000
buy --currency BTC --amount 0.01
show-portfolio
sell --currency BTC --amount 0.001
get-rate --from BTC --to USD
```

Для `buy` целевой валюты сначала пополните USD-кошелёк. Покупка USD используется как учебное внесение стартового виртуального капитала.

## Parser Service

Обновление вручную:

```text
update-rates
update-rates --source coingecko
show-rates
show-rates --currency BTC
show-rates --top 2
```

Ключ ExchangeRate-API не хранится в исходном коде. Перед запросом задайте его в окружении:

```powershell
$env:EXCHANGERATE_API_KEY = "[REDACTED_SECRET]"
```

CoinGecko можно использовать без ключа. Если внешний источник недоступен, Parser Service сохраняет данные от доступного источника и записывает ошибку в `logs/parser.log`.

## Структура

```text
data/
  users.json portfolios.json rates.json exchange_rates.json
valutatrade_hub/
  core/       модели, валюты, исключения и usecases
  infra/      Singleton-настройки и JSON DatabaseManager
  parser_service/  API-клиенты, storage, updater и scheduler
  cli/        интерфейс команд
main.py       точка запуска
tests/        функциональные и unit-тесты
```

Все JSON-файлы записываются в UTF-8 с `ensure_ascii=False`, поэтому русские имена и сообщения не искажаются.
