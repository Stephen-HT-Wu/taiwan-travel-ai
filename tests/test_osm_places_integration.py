from osm_places import _is_area_keyword, _resolve_search_area, search_places
from tests.conftest import json_response


def nominatim_bbox_handler(city_name="臺南市"):
    def handler(url, kwargs):
        if "nominatim.openstreetmap.org" in url:
            return json_response([{
                "display_name": city_name,
                "boundingbox": ["22.8", "23.3", "120.0", "120.5"],
            }])
        return None

    return handler


def overpass_handler(elements):
    def handler(url, kwargs):
        if "overpass" in url:
            response = json_response({"elements": elements})
            response.text = ""
            return response
        return None

    return handler


def test_is_area_keyword():
    assert _is_area_keyword("花蓮市") is True
    assert _is_area_keyword("赤崁樓") is False


def test_resolve_search_area_prefers_subregion_for_area_keyword(mock_httpx):
    def nominatim_handler(url, kwargs):
        if "nominatim.openstreetmap.org" not in url:
            return None
        query = kwargs.get("params", {}).get("q", "")
        if "花蓮市" in query:
            return json_response([{
                "display_name": "花蓮市, 花蓮縣, 臺灣",
                "boundingbox": ["23.95", "24.01", "121.58", "121.67"],
            }])
        if query == "花蓮縣":
            return json_response([{
                "display_name": "花蓮縣, 臺灣",
                "boundingbox": ["23.0", "24.3", "121.0", "121.8"],
            }])
        return json_response([])

    mock_httpx["get_handlers"].append(nominatim_handler)

    area = _resolve_search_area("花蓮縣", "花蓮市")

    assert area is not None
    assert area["name_filter"] == ""
    assert area["north"] - area["south"] < 0.1


def test_search_places_area_keyword_skips_name_filter_in_overpass(mock_httpx):
    captured = {}

    def nominatim_handler(url, kwargs):
        if "nominatim.openstreetmap.org" not in url:
            return None
        query = kwargs.get("params", {}).get("q", "")
        if "花蓮市" in query:
            return json_response([{
                "display_name": "花蓮市, 花蓮縣, 臺灣",
                "boundingbox": ["23.95", "24.01", "121.58", "121.67"],
            }])
        if query == "花蓮縣":
            return json_response([{
                "display_name": "花蓮縣, 臺灣",
                "boundingbox": ["23.0", "24.3", "121.0", "121.8"],
            }])
        return json_response([])

    def overpass_capture_handler(url, kwargs):
        if "overpass" in url:
            captured["query"] = kwargs.get("data", {}).get("data", "")
            return json_response({
                "elements": [{
                    "type": "node",
                    "lat": 23.99,
                    "lon": 121.60,
                    "tags": {"name": "測試餐廳", "amenity": "restaurant"},
                }]
            })
        return None

    mock_httpx["get_handlers"].append(nominatim_handler)
    mock_httpx["post_handlers"].append(overpass_capture_handler)

    results = search_places("HualienCounty", keyword="花蓮市", place_type="restaurant", limit=5)

    assert len(results) == 1
    assert '["name"~"花蓮市"' not in captured.get("query", "")
    assert "23.95" in captured.get("query", "")


def test_search_places_parses_overpass_response(mock_httpx):
    mock_httpx["get_handlers"].append(nominatim_bbox_handler())
    mock_httpx["post_handlers"].append(
        overpass_handler([
            {
                "type": "node",
                "lat": 22.997,
                "lon": 120.202,
                "tags": {"name": "赤崁樓", "tourism": "attraction"},
            }
        ])
    )

    results = search_places("Tainan", keyword="赤崁", place_type="attraction", limit=5)

    assert len(results) == 1
    assert results[0]["name"] == "赤崁樓"
    assert results[0]["source"] == "OpenStreetMap"
    assert results[0]["type"] == "attraction"


def test_search_places_invalid_place_type():
    results = search_places("Tainan", place_type="invalid")

    assert results[0]["error"]
