from routing import geocode_place, get_travel_route


def nominatim_handler(query_fragment, lat, lng, display_name):
    def handler(url, kwargs):
        if "nominatim.openstreetmap.org" not in url:
            return None
        q = (kwargs.get("params") or {}).get("q", "")
        if query_fragment not in q:
            return None
        from tests.conftest import json_response

        return json_response([{
            "lat": str(lat),
            "lon": str(lng),
            "display_name": display_name,
        }])

    return handler


def osrm_handler(distance_m, duration_s):
    def handler(url, kwargs):
        if "router.project-osrm.org" not in url:
            return None
        from tests.conftest import json_response

        return json_response({
            "code": "Ok",
            "routes": [{"distance": distance_m, "duration": duration_s}],
        })

    return handler


def test_geocode_place_not_found(mock_httpx):
    def handler(url, kwargs):
        if "nominatim.openstreetmap.org" in url:
            from tests.conftest import json_response
            return json_response([])
        return None

    mock_httpx["get_handlers"].append(handler)

    result = geocode_place("不存在的地方")

    assert result["error"]
    assert "找不到地點" in result["error"]


def test_get_travel_route_returns_duration_and_distance(mock_httpx):
    mock_httpx["get_handlers"].append(
        nominatim_handler("中山", 25.0527, 121.5200, "捷運中山站, 台北市")
    )
    mock_httpx["get_handlers"].append(
        nominatim_handler("雙城街", 25.0642, 121.5240, "雙城街, 台北市")
    )
    mock_httpx["get_handlers"].append(osrm_handler(2100, 1500))

    result = get_travel_route(
        "捷運中山站",
        "雙城街觀光夜市",
        mode="walking",
        near="台北市",
    )

    assert result["mode"] == "walking"
    assert result["mode_label"] == "步行"
    assert result["duration_minutes"] == 28
    assert result["distance_km"] == 2.1
    assert result["origin"]["lat"] == 25.0527


def test_get_travel_route_uses_coordinates_when_provided(mock_httpx):
    mock_httpx["get_handlers"].append(osrm_handler(800, 600))

    result = get_travel_route(
        "A",
        "B",
        mode="walking",
        origin_lat=25.05,
        origin_lng=121.52,
        destination_lat=25.06,
        destination_lng=121.53,
    )

    assert result["duration_minutes"] == 11
    assert result["distance_meters"] == 800


def test_get_travel_route_invalid_mode(mock_httpx):
    result = get_travel_route("A", "B", mode="subway")

    assert result["error"]
    assert "不支援的交通方式" in result["error"]
