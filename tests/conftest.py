import json
from unittest.mock import MagicMock

import pytest

import tdx


@pytest.fixture(autouse=True)
def reset_tdx_token_cache():
    tdx._token_cache = None
    tdx._station_ids_cache = None
    yield
    tdx._token_cache = None
    tdx._station_ids_cache = None


@pytest.fixture
def mock_httpx(monkeypatch):
    """Mock httpx for tdx.py and cwa.py. Configure get_handlers before calling code under test."""
    state = {"get_handlers": [], "post_handlers": []}

    def mock_post(url, **kwargs):
        for handler in state["post_handlers"]:
            result = handler(url, kwargs)
            if result is not None:
                return result
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json.return_value = {"access_token": "test-token"}
        return response

    def mock_get(url, **kwargs):
        for handler in state["get_handlers"]:
            result = handler(url, kwargs)
            if result is not None:
                return result
        raise AssertionError(f"Unexpected GET {url} params={kwargs.get('params')}")

    monkeypatch.setattr("tdx.httpx.post", mock_post)
    monkeypatch.setattr("tdx.httpx.get", mock_get)
    monkeypatch.setattr("cwa.httpx.get", mock_get)
    monkeypatch.setattr("routing.httpx.get", mock_get)
    return state


def json_response(payload, status_code=200):
    response = MagicMock()
    response.raise_for_status = MagicMock()
    if status_code >= 400:
        response.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    response.json.return_value = payload
    return response


class FakeAnthropicStream:
    def __init__(self, events, final_message):
        self._events = events
        self._final_message = final_message

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def __iter__(self):
        return iter(self._events)

    def get_final_message(self):
        return self._final_message


def tdx_get_handler(path_fragment, payload):
    def handler(url, kwargs):
        if path_fragment in url:
            return json_response(payload)
        return None

    return handler


def mock_tra_stations(mock_httpx, stations=None):
    if stations is None:
        stations = [
            {"StationID": "1000", "StationName": {"Zh_tw": "臺北"}},
            {"StationID": "4220", "StationName": {"Zh_tw": "臺南"}},
        ]
    mock_httpx["get_handlers"].append(
        tdx_get_handler("/v3/Rail/TRA/Station", {"Stations": stations})
    )
