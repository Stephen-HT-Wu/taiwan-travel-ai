import math
from typing import Dict, List, Optional, Tuple, Union

import httpx

from routing import get_travel_route
from tdx import _localized_name, _tdx_get

EARTH_RADIUS_M = 6371000
BUS_STOP_PAGE_SIZE = 1000
BUS_STOP_MAX_PAGES = 15
STOP_OF_ROUTE_PAGE_SIZE = 500
STOP_OF_ROUTE_MAX_PAGES = 20

CITY_RAIL_SYSTEMS: Dict[str, List[str]] = {
    "Taipei": ["TRTC", "NTMC"],
    "NewTaipei": ["NTMC", "TRTC"],
    "Taoyuan": ["TYMC"],
    "Taichung": ["TMRT"],
    "Kaohsiung": ["KRTC"],
}

_bus_stops_cache: Dict[str, List[dict]] = {}
_stop_of_route_cache: Dict[str, List[dict]] = {}
_s2s_travel_time_cache: Dict[str, List[dict]] = {}
_metro_stations_cache: Dict[str, List[dict]] = {}
_metro_od_fare_cache: Dict[str, List[dict]] = {}
_bus_stops_error_cache: Dict[str, str] = {}


def _tdx_get_safe(path: str, params: Optional[dict] = None) -> Union[list, dict]:
    """Call TDX; return {"error": "..."} instead of raising on HTTP failures."""
    try:
        return _tdx_get(path, params)
    except httpx.HTTPStatusError as exc:
        detail = ""
        try:
            body = exc.response.json()
            detail = body.get("Message") or body.get("message") or str(body)
        except Exception:
            detail = exc.response.text[:200]
        return {"error": f"TDX 查詢失敗（{exc.response.status_code}）：{detail}"}
    except httpx.HTTPError as exc:
        return {"error": f"TDX 連線失敗：{exc}"}


def _unwrap_items(data) -> list:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("Items") or data.get("Stations") or []
    return []


def _parse_point(position: Optional[dict]) -> Tuple[Optional[float], Optional[float]]:
    if not position:
        return None, None
    lat = position.get("PositionLat")
    lng = position.get("PositionLon")
    if lat is None or lng is None:
        return None, None
    return float(lat), float(lng)


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return EARTH_RADIUS_M * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _nearest_points(
    points: List[dict],
    lat: float,
    lng: float,
    radius_m: float,
    limit: int,
) -> List[dict]:
    ranked = []
    for point in points:
        plat, plng = point.get("lat"), point.get("lng")
        if plat is None or plng is None:
            continue
        distance_m = haversine_m(lat, lng, plat, plng)
        if distance_m > radius_m:
            continue
        ranked.append({**point, "distance_m": round(distance_m)})
    ranked.sort(key=lambda item: item["distance_m"])
    return ranked[:limit]


def _parse_bus_stop(item: dict) -> Optional[dict]:
    lat, lng = _parse_point(item.get("StopPosition"))
    if lat is None:
        return None
    return {
        "type": "bus",
        "stop_uid": item.get("StopUID", ""),
        "stop_id": item.get("StopID", ""),
        "name": _localized_name(item.get("StopName")),
        "lat": lat,
        "lng": lng,
    }


def _fetch_paginated(path: str, page_size: int, max_pages: int) -> Union[list, dict]:
    items: List[dict] = []
    for page in range(max_pages):
        raw = _tdx_get_safe(
            path,
            {
                "$format": "JSON",
                "$top": page_size,
                "$skip": page * page_size,
            },
        )
        if isinstance(raw, dict) and raw.get("error"):
            return raw
        batch = _unwrap_items(raw)
        if not batch:
            break
        items.extend(batch)
        if len(batch) < page_size:
            break
    return items


def _load_bus_stops(city: str) -> Union[List[dict], dict]:
    if city in _bus_stops_error_cache:
        return {"error": _bus_stops_error_cache[city]}
    if city in _bus_stops_cache:
        return _bus_stops_cache[city]

    # TDX api/basic 的 v3 市區公車僅部分縣市（如 Tainan）；v2 支援 Taipei 等。
    raw_items = _fetch_paginated(
        f"/v2/Bus/Stop/City/{city}",
        BUS_STOP_PAGE_SIZE,
        BUS_STOP_MAX_PAGES,
    )
    if isinstance(raw_items, dict) and raw_items.get("error"):
        _bus_stops_error_cache[city] = raw_items["error"]
        return raw_items

    stops = []
    for item in raw_items:
        parsed = _parse_bus_stop(item)
        if parsed:
            stops.append(parsed)
    _bus_stops_cache[city] = stops
    return stops


def _load_stop_of_route(city: str) -> Union[List[dict], dict]:
    if city in _stop_of_route_cache:
        return _stop_of_route_cache[city]

    raw_items = _fetch_paginated(
        f"/v2/Bus/StopOfRoute/City/{city}",
        STOP_OF_ROUTE_PAGE_SIZE,
        STOP_OF_ROUTE_MAX_PAGES,
    )
    if isinstance(raw_items, dict) and raw_items.get("error"):
        return raw_items

    _stop_of_route_cache[city] = raw_items
    return raw_items


def _load_s2s_travel_time(city: str) -> List[dict]:
    if city in _s2s_travel_time_cache:
        return _s2s_travel_time_cache[city]

    raw = _tdx_get_safe(
        f"/v3/Bus/S2STravelTime/City/{city}",
        {"$format": "JSON", "$top": 5000},
    )
    if isinstance(raw, dict) and raw.get("error"):
        _s2s_travel_time_cache[city] = []
        return []

    entries = _unwrap_items(raw)
    _s2s_travel_time_cache[city] = entries
    return entries


def _load_metro_stations(rail_system: str) -> List[dict]:
    if rail_system in _metro_stations_cache:
        return _metro_stations_cache[rail_system]

    raw = _tdx_get_safe(
        f"/v2/Rail/Metro/Station/{rail_system}",
        {"$format": "JSON"},
    )
    if isinstance(raw, dict) and raw.get("error"):
        return []

    stations = []
    for item in _unwrap_items(raw):
        lat, lng = _parse_point(item.get("StationPosition"))
        if lat is None:
            continue
        stations.append({
            "type": "metro",
            "rail_system": rail_system,
            "station_id": item.get("StationID", ""),
            "station_uid": item.get("StationUID", ""),
            "name": _localized_name(item.get("StationName")),
            "lat": lat,
            "lng": lng,
        })
    _metro_stations_cache[rail_system] = stations
    return stations


def _load_metro_od_fare(rail_system: str) -> List[dict]:
    if rail_system in _metro_od_fare_cache:
        return _metro_od_fare_cache[rail_system]

    raw = _tdx_get_safe(
        f"/v2/Rail/Metro/ODFare/{rail_system}",
        {"$format": "JSON", "$top": 10000},
    )
    if isinstance(raw, dict) and raw.get("error"):
        return []

    entries = _unwrap_items(raw)
    _metro_od_fare_cache[rail_system] = entries
    return entries


def _metro_stations_for_city(city: str) -> List[dict]:
    systems = CITY_RAIL_SYSTEMS.get(city, [])
    stations: List[dict] = []
    for system in systems:
        stations.extend(_load_metro_stations(system))
    return stations


def _walking_leg(
    origin_name: str,
    dest_name: str,
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
) -> dict:
    route = get_travel_route(
        origin_name,
        dest_name,
        mode="walking",
        origin_lat=origin_lat,
        origin_lng=origin_lng,
        destination_lat=dest_lat,
        destination_lng=dest_lng,
    )
    if route.get("error"):
        return {"type": "walk", "error": route["error"]}
    return {
        "type": "walk",
        "from": origin_name,
        "to": dest_name,
        "duration_minutes": route.get("duration_minutes"),
        "distance_km": route.get("distance_km"),
        "geocode_warnings": route.get("geocode_warnings") or [],
    }


def _find_direct_bus_routes(city: str, origin_stop: dict, dest_stop: dict) -> List[dict]:
    routes = _load_stop_of_route(city)
    if isinstance(routes, dict) and routes.get("error"):
        return []

    matches = []
    for route in routes:
        route_uid = route.get("RouteUID")
        route_name = _localized_name(route.get("RouteName"))
        stops_on_route = route.get("Stops") or []

        origin_seq = dest_seq = None
        origin_id = dest_id = None
        for stop in stops_on_route:
            if stop.get("StopUID") == origin_stop["stop_uid"]:
                origin_seq = stop.get("StopSequence")
                origin_id = stop.get("StopID")
            if stop.get("StopUID") == dest_stop["stop_uid"]:
                dest_seq = stop.get("StopSequence")
                dest_id = stop.get("StopID")

        if (
            origin_seq is not None
            and dest_seq is not None
            and origin_id
            and dest_id
            and origin_seq < dest_seq
        ):
            matches.append({
                "route_uid": route_uid,
                "route_name": route_name,
                "origin_stop_id": origin_id,
                "dest_stop_id": dest_id,
                "origin_seq": origin_seq,
                "dest_seq": dest_seq,
                "stops_on_route": stops_on_route,
            })
    return matches


def _sum_bus_ride_minutes(city: str, match: dict) -> Optional[int]:
    route_entry = next(
        (item for item in _load_s2s_travel_time(city) if item.get("RouteUID") == match["route_uid"]),
        None,
    )
    if not route_entry:
        return None

    segment_map: Dict[Tuple[str, str], int] = {}
    for segment in route_entry.get("TravelTimes") or []:
        runtime = segment.get("RunTime")
        if runtime is None or runtime < 0:
            continue
        segment_map[(segment.get("FromStopID"), segment.get("ToStopID"))] = int(runtime)

    ordered_ids = [
        stop.get("StopID")
        for stop in match["stops_on_route"]
        if match["origin_seq"] <= stop.get("StopSequence", 0) <= match["dest_seq"]
    ]
    if len(ordered_ids) < 2:
        return None

    total = 0
    for index in range(len(ordered_ids) - 1):
        runtime = segment_map.get((ordered_ids[index], ordered_ids[index + 1]))
        if runtime is None:
            return None
        total += runtime
    return total


def _estimate_bus_direct(
    city: str,
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    origin_name: str,
    dest_name: str,
    stop_radius_m: int = 800,
) -> Union[dict, None]:
    bus_stops = _load_bus_stops(city)
    if isinstance(bus_stops, dict) and bus_stops.get("error"):
        return bus_stops
    if not bus_stops:
        return None

    origin_candidates = _nearest_points(bus_stops, origin_lat, origin_lng, stop_radius_m, 3)
    dest_candidates = _nearest_points(bus_stops, dest_lat, dest_lng, stop_radius_m, 3)
    if not origin_candidates or not dest_candidates:
        return None

    best: Optional[dict] = None
    for origin_stop in origin_candidates:
        for dest_stop in dest_candidates:
            if origin_stop["stop_uid"] == dest_stop["stop_uid"]:
                continue
            for match in _find_direct_bus_routes(city, origin_stop, dest_stop):
                ride_minutes = _sum_bus_ride_minutes(city, match)
                walk_to = _walking_leg(
                    origin_name,
                    origin_stop["name"],
                    origin_lat,
                    origin_lng,
                    origin_stop["lat"],
                    origin_stop["lng"],
                )
                walk_from = _walking_leg(
                    dest_stop["name"],
                    dest_name,
                    dest_stop["lat"],
                    dest_stop["lng"],
                    dest_lat,
                    dest_lng,
                )
                if walk_to.get("error") or walk_from.get("error"):
                    continue

                walk_total = (walk_to.get("duration_minutes") or 0) + (
                    walk_from.get("duration_minutes") or 0
                )
                if ride_minutes is None:
                    candidate = {
                        "mode": "bus_direct",
                        "route_name": match["route_name"],
                        "origin_bus_stop": origin_stop["name"],
                        "destination_bus_stop": dest_stop["name"],
                        "bus_minutes": None,
                        "segments": [walk_to, {
                            "type": "bus",
                            "route_name": match["route_name"],
                            "from": origin_stop["name"],
                            "to": dest_stop["name"],
                            "duration_minutes": None,
                            "note": "找到同路線直達，但此縣市無 TDX 站間時間資料",
                        }, walk_from],
                        "total_minutes": walk_total,
                        "time_note": "僅含步行接驳；公車段時間未提供",
                    }
                else:
                    candidate = {
                        "mode": "bus_direct",
                        "route_name": match["route_name"],
                        "origin_bus_stop": origin_stop["name"],
                        "destination_bus_stop": dest_stop["name"],
                        "bus_minutes": ride_minutes,
                        "segments": [walk_to, {
                            "type": "bus",
                            "route_name": match["route_name"],
                            "from": origin_stop["name"],
                            "to": dest_stop["name"],
                            "duration_minutes": ride_minutes,
                        }, walk_from],
                        "total_minutes": walk_total + ride_minutes,
                    }
                if best is None or candidate["total_minutes"] < best["total_minutes"]:
                    best = candidate
    return best


def _estimate_metro(
    city: str,
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    origin_name: str,
    dest_name: str,
    stop_radius_m: int = 1200,
) -> Optional[dict]:
    metro_stations = _metro_stations_for_city(city)
    if not metro_stations:
        return None

    origin_candidates = _nearest_points(metro_stations, origin_lat, origin_lng, stop_radius_m, 2)
    dest_candidates = _nearest_points(metro_stations, dest_lat, dest_lng, stop_radius_m, 2)
    if not origin_candidates or not dest_candidates:
        return None

    best: Optional[dict] = None
    for origin_station in origin_candidates:
        for dest_station in dest_candidates:
            if origin_station["station_id"] == dest_station["station_id"]:
                continue
            rail_system = origin_station["rail_system"]
            if dest_station["rail_system"] != rail_system:
                continue

            od_entry = next(
                (
                    item for item in _load_metro_od_fare(rail_system)
                    if item.get("OriginStationID") == origin_station["station_id"]
                    and item.get("DestinationStationID") == dest_station["station_id"]
                ),
                None,
            )
            if not od_entry:
                continue

            ride_minutes = od_entry.get("TravelTime")
            if ride_minutes is None or ride_minutes < 0:
                continue

            walk_to = _walking_leg(
                origin_name,
                origin_station["name"],
                origin_lat,
                origin_lng,
                origin_station["lat"],
                origin_station["lng"],
            )
            walk_from = _walking_leg(
                dest_station["name"],
                dest_name,
                dest_station["lat"],
                dest_station["lng"],
                dest_lat,
                dest_lng,
            )
            if walk_to.get("error") or walk_from.get("error"):
                continue

            total = (
                (walk_to.get("duration_minutes") or 0)
                + int(ride_minutes)
                + (walk_from.get("duration_minutes") or 0)
            )
            candidate = {
                "mode": "metro",
                "rail_system": rail_system,
                "origin_station": origin_station["name"],
                "destination_station": dest_station["name"],
                "metro_minutes": int(ride_minutes),
                "segments": [walk_to, {
                    "type": "metro",
                    "from": origin_station["name"],
                    "to": dest_station["name"],
                    "duration_minutes": int(ride_minutes),
                }, walk_from],
                "total_minutes": total,
            }
            if best is None or candidate["total_minutes"] < best["total_minutes"]:
                best = candidate
    return best


def search_nearby_transit_stops(
    lat: float,
    lng: float,
    city: str,
    transit_type: str = "all",
    radius_m: int = 800,
    limit: int = 5,
) -> List[dict]:
    results: List[dict] = []
    transit_type = (transit_type or "all").lower()

    if transit_type in {"all", "bus"}:
        bus_stops = _load_bus_stops(city)
        if isinstance(bus_stops, dict) and bus_stops.get("error"):
            return [bus_stops]
        for stop in _nearest_points(bus_stops, lat, lng, radius_m, limit):
            results.append({
                "type": "bus",
                "name": stop["name"],
                "stop_uid": stop["stop_uid"],
                "lat": stop["lat"],
                "lng": stop["lng"],
                "distance_m": stop["distance_m"],
            })

    if transit_type in {"all", "metro"}:
        for stop in _nearest_points(_metro_stations_for_city(city), lat, lng, radius_m, limit):
            results.append({
                "type": "metro",
                "name": stop["name"],
                "station_id": stop["station_id"],
                "rail_system": stop["rail_system"],
                "lat": stop["lat"],
                "lng": stop["lng"],
                "distance_m": stop["distance_m"],
            })

    results.sort(key=lambda item: item["distance_m"])
    return results[:limit]


def estimate_transit_segment(
    origin_lat: float,
    origin_lng: float,
    destination_lat: float,
    destination_lng: float,
    city: str,
    origin_name: str = "起點",
    destination_name: str = "終點",
    prefer: str = "auto",
) -> dict:
    prefer = (prefer or "auto").lower()
    limitations = [
        "TDX 歷史站間/OD 資料估算",
        "不含等車、轉乘與即時誤點",
        "僅支援同路線公車直達或同系統捷運，不支援複雜轉乘",
    ]

    walking = get_travel_route(
        origin_name,
        destination_name,
        mode="walking",
        origin_lat=origin_lat,
        origin_lng=origin_lng,
        destination_lat=destination_lat,
        destination_lng=destination_lng,
    )

    candidates: List[dict] = []
    if prefer in {"auto", "bus"}:
        bus = _estimate_bus_direct(
            city,
            origin_lat,
            origin_lng,
            destination_lat,
            destination_lng,
            origin_name,
            destination_name,
        )
        if isinstance(bus, dict) and bus.get("error"):
            return bus
        if bus:
            data_source = "TDX 公車路線 + OSRM 步行"
            if bus.get("bus_minutes") is not None:
                data_source = "TDX 公車站間旅行時間 + OSRM 步行"
            candidates.append({
                **bus,
                "feasible": True,
                "data_source": data_source,
                "limitations": limitations,
            })

    if prefer in {"auto", "metro"}:
        metro = _estimate_metro(
            city,
            origin_lat,
            origin_lng,
            destination_lat,
            destination_lng,
            origin_name,
            destination_name,
        )
        if metro:
            candidates.append({
                **metro,
                "feasible": True,
                "data_source": "TDX 捷運 OD 票價/旅行時間 + OSRM 步行",
                "limitations": limitations,
            })

    if candidates:
        best = min(candidates, key=lambda item: item["total_minutes"])
        return best

    walking_minutes = walking.get("duration_minutes") if not walking.get("error") else None
    return {
        "feasible": False,
        "reason": "查無同路線公車直達或捷運 OD 資料（可能需轉乘）",
        "data_source": "TDX + OSRM",
        "limitations": limitations,
        "walking_alternative": walking if not walking.get("error") else None,
        "walking_minutes": walking_minutes,
    }
