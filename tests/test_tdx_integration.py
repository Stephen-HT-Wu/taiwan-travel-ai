from tests.conftest import tdx_get_handler

from tdx import search_attractions, search_bus_routes, search_restaurants, search_train_schedule


def test_search_attractions_parses_tdx_response(mock_httpx):
    mock_httpx["get_handlers"].append(
        tdx_get_handler(
            "/v2/Tourism/ScenicSpot/Tainan",
            [
                {
                    "ScenicSpotName": "赤崁樓",
                    "DescriptionDetail": "台南古蹟",
                    "Address": "臺南市中西區",
                    "OpenTime": "08:00-21:30",
                    "Class1": "古蹟",
                    "Picture": {"PictureUrl1": "https://example.com/photo.jpg"},
                }
            ],
        )
    )

    results = search_attractions("Tainan", limit=1)

    assert len(results) == 1
    assert results[0]["name"] == "赤崁樓"
    assert results[0]["category"] == "古蹟"
    assert results[0]["image"] == "https://example.com/photo.jpg"


def test_search_restaurants_parses_tdx_response(mock_httpx):
    mock_httpx["get_handlers"].append(
        tdx_get_handler(
            "/v2/Tourism/Restaurant/Tainan",
            [
                {
                    "RestaurantName": "度小月",
                    "Description": "擔仔麵",
                    "Address": "臺南市",
                    "OpenTime": "11:00-21:00",
                    "Phone": "886-6-123456",
                    "City": "臺南市",
                }
            ],
        )
    )

    results = search_restaurants("Tainan", limit=1)

    assert results[0]["name"] == "度小月"
    assert results[0]["phone"] == "886-6-123456"


def test_search_bus_routes_parses_subroutes(mock_httpx):
    mock_httpx["get_handlers"].append(
        tdx_get_handler(
            "/v2/Bus/Route/City/Taipei",
            [
                {
                    "RouteUID": "TPE10132",
                    "RouteName": {"Zh_tw": "234", "En": "234"},
                    "SubRoutes": [
                        {"SubRouteName": {"Zh_tw": "234", "En": "234"}},
                    ],
                    "BusRouteType": 11,
                    "DepartureStopNameZh": "板橋",
                    "DestinationStopNameZh": "西門",
                }
            ],
        )
    )

    results = search_bus_routes("Taipei", limit=1)

    assert results[0]["route_name"] == "234"
    assert results[0]["sub_route"] == "234"
    assert results[0]["from"] == "板橋"
    assert results[0]["to"] == "西門"


def test_search_train_schedule_unknown_station_returns_error():
    results = search_train_schedule("不存在", "台南")

    assert results[0]["error"]
    assert "支援的站名" in results[0]["error"]


def test_search_train_schedule_parses_tdx_response(mock_httpx):
    mock_httpx["get_handlers"].append(
        tdx_get_handler(
            "/v3/Rail/TRA/DailyTrainTimetable/OD/1000/to/4220/",
            [
                {
                    "DailyTrainInfo": {
                        "TrainNo": "133",
                        "TrainTypeName": {"Zh_tw": "自強"},
                        "JourneyTime": 240,
                        "StopTimes": [
                            {"DepartureTime": "08:00"},
                            {"ArrivalTime": "12:00"},
                        ],
                    }
                }
            ],
        )
    )

    results = search_train_schedule("台北", "台南", travel_date="2026-06-01", limit=1)

    assert results[0]["train_no"] == "133"
    assert results[0]["departure_time"] == "08:00"
    assert results[0]["arrival_time"] == "12:00"
