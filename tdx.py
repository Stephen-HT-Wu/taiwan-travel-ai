import httpx
from dotenv import load_dotenv
import os
from datetime import date
from typing import Optional, Union, List, Dict

load_dotenv()

TDX_AUTH_URL = "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token"
TDX_BASE_URL = "https://tdx.transportdata.tw/api/basic"

_token_cache: Optional[str] = None
_station_ids_cache: Optional[Dict[str, str]] = None


def get_tdx_token() -> str:
    global _token_cache
    if _token_cache:
        return _token_cache

    resp = httpx.post(TDX_AUTH_URL, data={
        "grant_type": "client_credentials",
        "client_id": os.getenv("TDX_CLIENT_ID"),
        "client_secret": os.getenv("TDX_CLIENT_SECRET"),
    })
    resp.raise_for_status()
    _token_cache = resp.json()["access_token"]
    return _token_cache


def _tdx_get(path: str, params: Optional[dict] = None) -> Union[list, dict]:
    token = get_tdx_token()
    headers = {"Authorization": f"Bearer {token}"}
    resp = httpx.get(f"{TDX_BASE_URL}{path}", headers=headers, params=params or {})
    resp.raise_for_status()
    return resp.json()


def _parse_position(position: Optional[dict]) -> dict:
    if not position:
        return {"lat": None, "lng": None}
    return {
        "lat": position.get("PositionLat"),
        "lng": position.get("PositionLon"),
    }


def _localized_name(value, lang: str = "Zh_tw", default: str = "") -> str:
    if isinstance(value, dict):
        return value.get(lang) or value.get("En") or default
    if isinstance(value, str):
        return value
    return default


def _unwrap_train_timetables(data) -> list:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("TrainTimetables") or data.get("TrainTimetable") or []
    return []


def _unwrap_tra_stations(data) -> list:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("Stations") or []
    return []


def _register_station_name(mapping: Dict[str, str], name: str, station_id: str) -> None:
    mapping[name] = station_id
    if "臺" in name:
        mapping[name.replace("臺", "台")] = station_id
    elif "台" in name:
        mapping[name.replace("台", "臺")] = station_id


def get_station_ids() -> Dict[str, str]:
    """Load all TRA station names → StationID from TDX (cached)."""
    global _station_ids_cache
    if _station_ids_cache is not None:
        return _station_ids_cache

    raw = _tdx_get("/v3/Rail/TRA/Station", {"$format": "JSON"})
    mapping: Dict[str, str] = {}
    for station in _unwrap_tra_stations(raw):
        station_id = station.get("StationID")
        name = _localized_name(station.get("StationName"))
        if station_id and name:
            _register_station_name(mapping, name, station_id)

    _station_ids_cache = mapping
    return mapping


def search_attractions(city: str, keyword: str = "", limit: int = 20) -> List[dict]:
    params = {
        "$top": limit,
        "$select": "ScenicSpotName,DescriptionDetail,Address,OpenTime,Picture,Class1,Position",
        "$format": "JSON",
    }
    if keyword:
        params["$filter"] = f"contains(ScenicSpotName,'{keyword}')"

    city_path = f"/{city}" if city else ""
    spots = _tdx_get(f"/v2/Tourism/ScenicSpot{city_path}", params)

    return [
        {
            "name": spot.get("ScenicSpotName", ""),
            "description": (spot.get("DescriptionDetail") or "")[:200],
            "address": spot.get("Address", ""),
            "open_time": spot.get("OpenTime", ""),
            "category": spot.get("Class1", ""),
            "image": spot.get("Picture", {}).get("PictureUrl1", ""),
            **_parse_position(spot.get("Position")),
        }
        for spot in spots
    ]


def search_restaurants(city: str, keyword: str = "", limit: int = 20) -> List[dict]:
    params = {
        "$top": limit,
        "$select": "RestaurantName,Description,Address,OpenTime,Phone,City,Position",
        "$format": "JSON",
    }
    if keyword:
        params["$filter"] = f"contains(RestaurantName,'{keyword}')"

    city_path = f"/{city}" if city else ""
    restaurants = _tdx_get(f"/v2/Tourism/Restaurant{city_path}", params)

    return [
        {
            "name": r.get("RestaurantName", ""),
            "description": (r.get("Description") or "")[:200],
            "address": r.get("Address", ""),
            "open_time": r.get("OpenTime", ""),
            "phone": r.get("Phone", ""),
            "city": r.get("City", ""),
            **_parse_position(r.get("Position")),
        }
        for r in restaurants
    ]


def search_bus_routes(city: str, keyword: str = "", limit: int = 5) -> List[dict]:
    params = {
        "$top": limit,
        "$select": "RouteUID,RouteName,SubRoutes,BusRouteType,DepartureStopNameZh,DestinationStopNameZh",
        "$format": "JSON",
    }
    if keyword:
        params["$filter"] = f"contains(RouteName/Zh_tw,'{keyword}')"

    routes = _tdx_get(f"/v2/Bus/Route/City/{city}", params)

    results = []
    for route in routes:
        route_name = route.get("RouteName") or {}
        sub_routes = route.get("SubRoutes") or []
        sub_route_names = []
        for sub in sub_routes[:3]:
            name = (sub.get("SubRouteName") or {}).get("Zh_tw")
            if name and name not in sub_route_names:
                sub_route_names.append(name)

        results.append({
            "route_name": route_name.get("Zh_tw") or route_name.get("En") or "",
            "sub_route": "、".join(sub_route_names),
            "route_type": route.get("BusRouteType", ""),
            "from": route.get("DepartureStopNameZh", ""),
            "to": route.get("DestinationStopNameZh", ""),
        })
    return results



def search_train_schedule(
    origin: str,
    destination: str,
    travel_date: str = "",
    limit: int = 5,
) -> List[dict]:
    station_ids = get_station_ids()
    origin_id = station_ids.get(origin)
    dest_id = station_ids.get(destination)
    if not origin_id or not dest_id:
        unknown = []
        if not origin_id:
            unknown.append(origin)
        if not dest_id:
            unknown.append(destination)
        examples = "、".join(["台北", "台中", "高雄", "花蓮", "宜蘭", "礁溪", "羅東"])
        return [{
            "error": (
                f"不支援的站名：{'、'.join(unknown)}。"
                f"請使用台鐵正式站名（共 {len(station_ids)} 個站名可查，例如：{examples}）"
            )
        }]

    query_date = travel_date or date.today().strftime("%Y-%m-%d")
    params = {"$top": limit, "$format": "JSON"}
    raw = _tdx_get(
        f"/v3/Rail/TRA/DailyTrainTimetable/OD/{origin_id}/to/{dest_id}/{query_date}",
        params,
    )
    trains = _unwrap_train_timetables(raw)
    if not trains:
        return [{"error": f"{query_date} {origin}→{destination} 查無班次，請換日期或路線再試"}]

    results = []
    for train in trains:
        if not isinstance(train, dict):
            continue

        train_info = train.get("TrainInfo") or train.get("DailyTrainInfo") or train
        stop_times = train.get("StopTimes") or train_info.get("StopTimes") or []

        departure = stop_times[0].get("DepartureTime", "") if stop_times else ""
        arrival = stop_times[-1].get("ArrivalTime", "") if stop_times else ""

        results.append({
            "train_no": train_info.get("TrainNo", ""),
            "train_type": _localized_name(train_info.get("TrainTypeName")),
            "departure_time": departure,
            "arrival_time": arrival,
            "duration_minutes": train_info.get("JourneyTime", ""),
            "origin": origin,
            "destination": destination,
            "date": query_date,
        })
    return results
