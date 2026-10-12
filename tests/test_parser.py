"""Проверки отказоустойчивости Parser Service на контролируемых клиентах."""

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.api_clients import BaseApiClient
from valutatrade_hub.parser_service.storage import RatesStorage
from valutatrade_hub.parser_service.updater import RatesUpdater


class GoodClient(BaseApiClient):
    source_name = "Fixture"

    def fetch_rates(self) -> dict[str, float]:
        return {"BTC_USD": 60000.0}


class BadClient(BaseApiClient):
    source_name = "Broken"

    def fetch_rates(self) -> dict[str, float]:
        raise ApiRequestError("fixture failure")


class MemoryStorage(RatesStorage):
    def __init__(self) -> None:
        self.snapshot: dict = {"pairs": {}, "last_refresh": None}
        self.history: list = []

    def write_snapshot(self, pairs: dict) -> str:
        self.snapshot["pairs"].update(pairs)
        self.snapshot["last_refresh"] = "2026-10-11T00:00:00+00:00"
        return self.snapshot["last_refresh"]

    def append_history(self, pairs: dict) -> None:
        self.history.extend(pairs)


def test_updater_keeps_good_source_when_one_fails() -> None:
    storage = MemoryStorage()
    result = RatesUpdater([BadClient(), GoodClient()], storage).run_update()
    assert result["pairs"] == 1
    assert len(result["errors"]) == 1
    assert storage.snapshot["pairs"]["BTC_USD"]["rate"] == 60000.0
