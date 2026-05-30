import httpx
from dotenv import load_dotenv
import os
from datetime import date, datetime, timedelta
from typing import Optional, Union, List, Dict, Tuple

load_dotenv()

TDX_AUTH_URL = "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token"
TDX_BASE_URL = "https://tdx.transportdata.tw/api/basic"

_token_cache: Optional[str] = None
_station_ids_cache: Optional[Dict[str, str]] = None
_hsr_station_ids_cache: Optional[Dict[str, str]] = None

HSR_STATION_ALIASES = {
    "高雄": "左營",
    "高鐵高雄": "左營",
    "高鐵左營": "左營",
}


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



def _normalize_travel_date(
    travel_date: str,
    max_days: int = 60,
) -> Tuple[str, Optional[str]]:
    today = date.today()
    if not travel_date or not str(travel_date).strip():
        return today.strftime("%Y-%m-%d"), None

    raw = str(travel_date).strip()
    try:
        parsed = datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        corrected = today.strftime("%Y-%m-%d")
        return corrected, f"日期格式無效「{raw}」，已改用今天 {corrected}"

    if parsed < today:
        corrected = today.strftime("%Y-%m-%d")
        return corrected, f"日期 {raw} 已過期，已改用今天 {corrected}"

    max_date = today + timedelta(days=max_days)
    if parsed > max_date:
        corrected = today.strftime("%Y-%m-%d")
        return corrected, f"日期 {raw} 超出可查範圍（{max_days} 天內），已改用今天 {corrected}"

    return parsed.strftime("%Y-%m-%d"), None


def _unwrap_hsr_stations(data) -> list:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("Stations") or []
    return []


def _unwrap_hsr_timetables(data) -> list:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("DailyTimetables") or data.get("DailyTimetable") or []
    return []


def _resolve_hsr_station_name(name: str) -> str:
    trimmed = (name or "").strip()
    return HSR_STATION_ALIASES.get(trimmed, trimmed)


def get_hsr_station_ids() -> Dict[str, str]:
    """Load THSR station names → StationID from TDX (cached)."""
    global _hsr_station_ids_cache
    if _hsr_station_ids_cache is not None:
        return _hsr_station_ids_cache

    raw = _tdx_get("/v2/Rail/THSR/Station", {"$format": "JSON"})
    mapping: Dict[str, str] = {}
    for station in _unwrap_hsr_stations(raw):
        station_id = station.get("StationID")
        name = _localized_name(station.get("StationName"))
        if station_id and name:
            _register_station_name(mapping, name, station_id)

    for alias, official in HSR_STATION_ALIASES.items():
        station_id = mapping.get(official)
        if station_id:
            _register_station_name(mapping, alias, station_id)

    _hsr_station_ids_cache = mapping
    return mapping


def _parse_hsr_train_row(
    train: dict,
    origin: str,
    destination: str,
    query_date: str,
) -> Optional[dict]:
    if not isinstance(train, dict):
        return None

    train_info = train.get("DailyTrainInfo") or train
    origin_stop = train.get("OriginStopTime") or {}
    dest_stop = train.get("DestinationStopTime") or {}
    stop_times = train.get("StopTimes") or train_info.get("StopTimes") or []

    if origin_stop or dest_stop:
        departure = origin_stop.get("DepartureTime") or origin_stop.get("ArrivalTime", "")
        arrival = dest_stop.get("ArrivalTime") or dest_stop.get("DepartureTime", "")
    elif stop_times:
        departure = stop_times[0].get("DepartureTime", "") if stop_times else ""
        arrival = stop_times[-1].get("ArrivalTime") or stop_times[-1].get("DepartureTime", "")
    else:
        return None

    duration_minutes = ""
    if departure and arrival:
        try:
            dep = datetime.strptime(departure, "%H:%M")
            arr = datetime.strptime(arrival, "%H:%M")
            if arr < dep:
                arr += timedelta(days=1)
            duration_minutes = int((arr - dep).total_seconds() // 60)
        except ValueError:
            duration_minutes = ""

    return {
        "train_no": train_info.get("TrainNo", ""),
        "train_type": "高鐵",
        "departure_time": departure,
        "arrival_time": arrival,
        "duration_minutes": duration_minutes,
        "origin": origin,
        "destination": destination,
        "date": query_date,
    }


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

    query_date, date_note = _normalize_travel_date(travel_date)
    params = {"$top": limit, "$format": "JSON"}
    try:
        raw = _tdx_get(
            f"/v3/Rail/TRA/DailyTrainTimetable/OD/{origin_id}/to/{dest_id}/{query_date}",
            params,
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 400:
            return [{
                "error": (
                    f"台鐵時刻查詢失敗（日期 {query_date} 可能無時刻表）。"
                    f"請改用今天或未來日期再試"
                )
            }]
        raise

    trains = _unwrap_train_timetables(raw)
    if not trains:
        return [{"error": f"{query_date} {origin}→{destination} 查無班次，請換日期或路線再試"}]

    results = []
    if date_note:
        results.append({"note": date_note})

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


def search_hsr_schedule(
    origin: str,
    destination: str,
    travel_date: str = "",
    limit: int = 5,
) -> List[dict]:
    station_ids = get_hsr_station_ids()
    origin_name = _resolve_hsr_station_name(origin)
    destination_name = _resolve_hsr_station_name(destination)
    origin_id = station_ids.get(origin_name)
    dest_id = station_ids.get(destination_name)
    if not origin_id or not dest_id:
        unknown = []
        if not origin_id:
            unknown.append(origin)
        if not dest_id:
            unknown.append(destination)
        examples = "、".join(["台北", "台中", "左營", "嘉義", "台南", "桃園"])
        return [{
            "error": (
                f"不支援的高鐵站名：{'、'.join(unknown)}。"
                f"請使用高鐵正式站名（共 {len(station_ids)} 站，例如：{examples}；"
                f"高雄請用左營）"
            )
        }]

    query_date, date_note = _normalize_travel_date(travel_date, max_days=45)
    params = {"$top": limit, "$format": "JSON"}
    try:
        raw = _tdx_get(
            f"/v2/Rail/THSR/DailyTimetable/OD/{origin_id}/to/{dest_id}/{query_date}",
            params,
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 400:
            return [{
                "error": (
                    f"高鐵時刻查詢失敗（日期 {query_date} 可能無時刻表）。"
                    f"請改用今天或未來 45 天內的日期再試"
                )
            }]
        raise

    trains = _unwrap_hsr_timetables(raw)
    if not trains:
        return [{
            "error": (
                f"{query_date} {origin_name}→{destination_name} 查無高鐵班次，"
                f"請換日期或路線再試"
            )
        }]

    results = []
    if date_note:
        results.append({"note": date_note})

    for train in trains[:limit]:
        row = _parse_hsr_train_row(train, origin_name, destination_name, query_date)
        if row:
            results.append(row)

    if not any(isinstance(item, dict) and item.get("train_no") for item in results):
        return [{
            "error": (
                f"{query_date} {origin_name}→{destination_name} 查無高鐵班次，"
                f"請換日期或路線再試"
            )
        }]

    return results
