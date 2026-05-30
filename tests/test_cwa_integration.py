from tests.conftest import json_response, tdx_get_handler

from cwa import get_weather_forecast


def test_get_weather_forecast_without_api_key(monkeypatch):
    monkeypatch.delenv("CWA_API_KEY", raising=False)

    result = get_weather_forecast(city="Taipei")

    assert result["error"]
    assert "CWA_API_KEY" in result["error"]


def test_get_weather_forecast_parses_cwa_response(mock_httpx, monkeypatch):
    monkeypatch.setenv("CWA_API_KEY", "test-cwa-key")
    mock_httpx["get_handlers"].append(
        tdx_get_handler(
            "opendata.cwa.gov.tw",
            {
                "records": {
                    "location": [
                        {
                            "locationName": "臺北市",
                            "weatherElement": [
                                {
                                    "elementName": "Wx",
                                    "time": [
                                        {
                                            "startTime": "2026-06-01T06:00:00+08:00",
                                            "endTime": "2026-06-01T12:00:00+08:00",
                                            "parameter": {"parameterName": "晴"},
                                        }
                                    ],
                                },
                                {
                                    "elementName": "PoP",
                                    "time": [{"parameter": {"parameterName": "10"}}],
                                },
                                {
                                    "elementName": "MinT",
                                    "time": [{"parameter": {"parameterName": "25"}}],
                                },
                                {
                                    "elementName": "MaxT",
                                    "time": [{"parameter": {"parameterName": "32"}}],
                                },
                            ],
                        }
                    ]
                }
            },
        )
    )

    result = get_weather_forecast(city="Taipei")

    assert result["location"] == "臺北市"
    assert len(result["forecast"]) == 1
    assert result["forecast"][0]["weather"] == "晴"
    assert result["forecast"][0]["max_temp"] == "32"


def test_get_weather_forecast_passes_authorization(mock_httpx, monkeypatch):
    monkeypatch.setenv("CWA_API_KEY", "test-cwa-key")
    captured = {}

    def handler(url, kwargs):
        if "opendata.cwa.gov.tw" in url:
            captured["params"] = kwargs.get("params")
            return json_response({"records": {"location": []}})
        return None

    mock_httpx["get_handlers"].append(handler)

    get_weather_forecast(city="Taipei")

    assert captured["params"]["Authorization"] == "test-cwa-key"
    assert captured["params"]["locationName"] == "臺北市"
