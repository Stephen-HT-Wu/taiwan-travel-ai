from tests.conftest import json_response, tdx_get_handler
from tests.test_routing_integration import osrm_handler
from transit import (
    estimate_transit_segment,
    haversine_m,
    search_nearby_transit_stops,
)


def test_haversine_m():
    distance = haversine_m(25.033, 121.565, 25.034, 121.566)

    assert 100 < distance < 200


def test_search_nearby_transit_stops_filters_by_distance(mock_httpx):
    mock_httpx["get_handlers"].append(
        tdx_get_handler(
            "/v3/Bus/Stop/City/Chiayi",
            {
                "Items": [
                    {
                        "StopUID": "CYB001",
                        "StopID": "001",
                        "StopName": {"Zh_tw": "近站"},
                        "StopPosition": {"PositionLat": 23.480, "PositionLon": 120.449},
                    },
                    {
                        "StopUID": "CYB002",
                        "StopID": "002",
                        "StopName": {"Zh_tw": "遠站"},
                        "StopPosition": {"PositionLat": 23.600, "PositionLon": 120.600},
                    },
                ]
            },
        )
    )

    results = search_nearby_transit_stops(
        23.4798,
        120.4493,
        "Chiayi",
        transit_type="bus",
        radius_m=800,
        limit=5,
    )

    assert len(results) == 1
    assert results[0]["name"] == "近站"
    assert results[0]["distance_m"] < 800


def test_estimate_transit_segment_bus_direct(mock_httpx):
    mock_httpx["get_handlers"].append(
        tdx_get_handler(
            "/v3/Bus/Stop/City/Tainan",
            {
                "Items": [
                    {
                        "StopUID": "TNA001",
                        "StopID": "A1",
                        "StopName": {"Zh_tw": "起站牌"},
                        "StopPosition": {"PositionLat": 23.000, "PositionLon": 120.200},
                    },
                    {
                        "StopUID": "TNA002",
                        "StopID": "B1",
                        "StopName": {"Zh_tw": "迄站牌"},
                        "StopPosition": {"PositionLat": 23.010, "PositionLon": 120.210},
                    },
                ]
            },
        )
    )
    mock_httpx["get_handlers"].append(
        tdx_get_handler(
            "/v3/Bus/StopOfRoute/City/Tainan",
            {
                "Items": [
                    {
                        "RouteUID": "TNN001",
                        "RouteName": {"Zh_tw": "1路"},
                        "Stops": [
                            {
                                "StopUID": "TNA001",
                                "StopID": "A1",
                                "StopSequence": 1,
                                "StopName": {"Zh_tw": "起站牌"},
                            },
                            {
                                "StopUID": "TNA002",
                                "StopID": "B1",
                                "StopSequence": 2,
                                "StopName": {"Zh_tw": "迄站牌"},
                            },
                        ],
                    }
                ]
            },
        )
    )
    mock_httpx["get_handlers"].append(
        tdx_get_handler(
            "/v3/Bus/S2STravelTime/City/Tainan",
            {
                "Items": [
                    {
                        "RouteUID": "TNN001",
                        "TravelTimes": [
                            {
                                "FromStopID": "A1",
                                "ToStopID": "B1",
                                "RunTime": 8,
                            }
                        ],
                    }
                ]
            },
        )
    )
    mock_httpx["get_handlers"].append(osrm_handler(300, 240))
    mock_httpx["get_handlers"].append(osrm_handler(300, 240))

    result = estimate_transit_segment(
        23.0001,
        120.2001,
        23.0099,
        120.2099,
        "Tainan",
        origin_name="景點A",
        destination_name="景點B",
        prefer="bus",
    )

    assert result["feasible"] is True
    assert result["mode"] == "bus_direct"
    assert result["bus_minutes"] == 8
    assert result["total_minutes"] >= 8


def test_estimate_transit_segment_metro(mock_httpx):
    mock_httpx["get_handlers"].append(
        tdx_get_handler(
            "/v2/Rail/Metro/Station/TRTC",
            {
                "Stations": [
                    {
                        "StationID": "R10",
                        "StationUID": "TRTC_R10",
                        "StationName": {"Zh_tw": "台北車站"},
                        "StationPosition": {"PositionLat": 25.047, "PositionLon": 121.517},
                    },
                    {
                        "StationID": "R11",
                        "StationUID": "TRTC_R11",
                        "StationName": {"Zh_tw": "台大醫院"},
                        "StationPosition": {"PositionLat": 25.041, "PositionLon": 121.516},
                    },
                ]
            },
        )
    )
    mock_httpx["get_handlers"].append(
        tdx_get_handler(
            "/v2/Rail/Metro/Station/NTMC",
            {"Stations": []},
        )
    )
    mock_httpx["get_handlers"].append(
        tdx_get_handler(
            "/v2/Rail/Metro/ODFare/TRTC",
            {
                "Stations": [
                    {
                        "OriginStationID": "R10",
                        "DestinationStationID": "R11",
                        "TravelTime": 3,
                        "OriginStationName": {"Zh_tw": "台北車站"},
                        "DestinationStationName": {"Zh_tw": "台大醫院"},
                    }
                ]
            },
        )
    )
    mock_httpx["get_handlers"].append(osrm_handler(200, 180))
    mock_httpx["get_handlers"].append(osrm_handler(200, 180))

    result = estimate_transit_segment(
        25.0471,
        121.5171,
        25.0409,
        121.5159,
        "Taipei",
        prefer="metro",
    )

    assert result["feasible"] is True
    assert result["mode"] == "metro"
    assert result["metro_minutes"] == 3


def test_estimate_transit_segment_no_direct_route(mock_httpx):
    mock_httpx["get_handlers"].append(
        tdx_get_handler(
            "/v3/Bus/Stop/City/Chiayi",
            {
                "Items": [
                    {
                        "StopUID": "CY1",
                        "StopID": "1",
                        "StopName": {"Zh_tw": "站A"},
                        "StopPosition": {"PositionLat": 23.48, "PositionLon": 120.44},
                    },
                    {
                        "StopUID": "CY2",
                        "StopID": "2",
                        "StopName": {"Zh_tw": "站B"},
                        "StopPosition": {"PositionLat": 23.49, "PositionLon": 120.45},
                    },
                ]
            },
        )
    )
    mock_httpx["get_handlers"].append(
        tdx_get_handler(
            "/v3/Bus/StopOfRoute/City/Chiayi",
            {"Items": []},
        )
    )
    mock_httpx["get_handlers"].append(
        tdx_get_handler(
            "/v3/Bus/S2STravelTime/City/Chiayi",
            {"Items": []},
        )
    )
    mock_httpx["get_handlers"].append(osrm_handler(1500, 1200))

    result = estimate_transit_segment(
        23.480,
        120.440,
        23.490,
        120.450,
        "Chiayi",
        prefer="bus",
    )

    assert result["feasible"] is False
    assert result["walking_alternative"] is not None
