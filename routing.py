import httpx
from typing import Optional

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OSRM_URL = "https://router.project-osrm.org/route/v1"
USER_AGENT = "taiwan-travel-ai/0.1 (travel assistant demo)"

OSRM_PROFILES = {
    "walking": "walking",
    "walk": "walking",
    "foot": "walking",
    "driving": "driving",
    "car": "driving",
    "cycling": "cycling",
    "bike": "cycling",
    "bicycle": "cycling",
}


def _resolve_profile(mode: str) -> str:
    profile = OSRM_PROFILES.get((mode or "walking").lower())
    if not profile:
        supported = "、".join(sorted(set(OSRM_PROFILES.keys())))
        raise ValueError(f"不支援的交通方式「{mode}」，請使用：{supported}")
    return profile


def geocode_place(place: str, near: str = "") -> dict:
    """Resolve a place name to coordinates via OpenStreetMap Nominatim."""
    query = place.strip()
    if near:
        query = f"{place}, {near}"
    if "台" not in query and "臺" not in query:
        query = f"{query}, 台灣"

    params = {
        "q": query,
        "format": "json",
        "limit": 1,
        "countrycodes": "tw",
    }
    if near and ("台北" in near or "臺北" in near):
        params["viewbox"] = "121.45,25.00,121.65,25.20"
        params["bounded"] = "0"

    resp = httpx.get(
        NOMINATIM_URL,
        params=params,
        headers={"User-Agent": USER_AGENT},
        timeout=15.0,
    )
    resp.raise_for_status()
    results = resp.json()
    if not results:
        return {"error": f"找不到地點：{place}"}

    hit = results[0]
    return {
        "name": hit.get("display_name", place),
        "lat": float(hit["lat"]),
        "lng": float(hit["lon"]),
    }


def _resolve_point(
    place: str,
    lat: Optional[float],
    lng: Optional[float],
    near: str = "",
) -> dict:
    if lat is not None and lng is not None:
        return {"name": place or f"{lat},{lng}", "lat": lat, "lng": lng}
    if not place:
        return {"error": "請提供地點名稱或經緯度"}
    result = geocode_place(place, near=near)
    if result.get("error"):
        return result
    if place and place not in result["name"]:
        result["query"] = place
    return result


def _geocode_warnings(label: str, point: dict) -> list:
    query = point.get("query")
    name = point.get("name", "")
    if not query or query in name:
        return []
    return [
        f"{label}「{query}」已對應至：{name}（{point['lat']}, {point['lng']}）"
    ]


def get_travel_route(
    origin: str,
    destination: str,
    mode: str = "walking",
    origin_lat: Optional[float] = None,
    origin_lng: Optional[float] = None,
    destination_lat: Optional[float] = None,
    destination_lng: Optional[float] = None,
    near: str = "台北市",
) -> dict:
    """
    Estimate travel time and distance between two places using OSRM (OpenStreetMap routing).
    Geocodes place names via Nominatim when coordinates are not provided.
    """
    try:
        profile = _resolve_profile(mode)
    except ValueError as e:
        return {"error": str(e)}

    origin_point = _resolve_point(origin, origin_lat, origin_lng, near=near)
    if origin_point.get("error"):
        return origin_point

    dest_point = _resolve_point(destination, destination_lat, destination_lng, near=near)
    if dest_point.get("error"):
        return dest_point

    coords = (
        f"{origin_point['lng']},{origin_point['lat']};"
        f"{dest_point['lng']},{dest_point['lat']}"
    )
    resp = httpx.get(
        f"{OSRM_URL}/{profile}/{coords}",
        params={"overview": "false"},
        headers={"User-Agent": USER_AGENT},
        timeout=15.0,
    )
    resp.raise_for_status()
    data = resp.json()

    if data.get("code") != "Ok" or not data.get("routes"):
        return {"error": f"無法規劃路線（{data.get('code', '未知錯誤')}）"}

    route = data["routes"][0]
    distance_m = route.get("distance", 0)
    duration_s = route.get("duration", 0)

    if profile == "walking":
        # OSRM 步行秒數常偏快；改用市區步行約 4.5 km/h（75 公尺/分）
        duration_min = max(1, round(distance_m / 75))
        duration_s = duration_min * 60
    else:
        duration_min = max(1, round(duration_s / 60))

    mode_labels = {
        "walking": "步行",
        "driving": "開車",
        "cycling": "騎車",
    }

    geocode_warnings = (
        _geocode_warnings("起點", origin_point)
        + _geocode_warnings("終點", dest_point)
    )

    return {
        "origin": origin_point,
        "destination": dest_point,
        "mode": profile,
        "mode_label": mode_labels.get(profile, profile),
        "distance_meters": round(distance_m),
        "distance_km": round(distance_m / 1000, 1),
        "duration_seconds": round(duration_s),
        "duration_minutes": duration_min,
        "geocode_warnings": geocode_warnings,
        "note": "步行時間依距離以約 4.5 km/h 估算；開車/騎車為 OSRM 路線時間，不含等車或轉乘",
    }


ITINERARY_LEGS_NOTE = (
    "移動時間不含景點停留、不含等車或轉乘；高鐵/台鐵跨城段請另引用時刻表工具。"
)


def get_itinerary_legs(
    stops: list,
    mode: str = "walking",
    near: str = "",
) -> dict:
    """
    Compute travel time between consecutive stops in visit order.
    Each stop: {name, lat?, lng?}. Reuses get_travel_route per leg.
    """
    if not isinstance(stops, list) or len(stops) < 2:
        return {"error": "stops 至少需要 2 個地點"}

    legs = []
    all_warnings = []
    total_minutes = 0
    ok_legs = 0

    for index in range(len(stops) - 1):
        origin = stops[index] if isinstance(stops[index], dict) else {"name": str(stops[index])}
        destination = stops[index + 1] if isinstance(stops[index + 1], dict) else {"name": str(stops[index + 1])}

        origin_name = (origin.get("name") or "").strip()
        dest_name = (destination.get("name") or "").strip()
        if not origin_name or not dest_name:
            legs.append({
                "from": origin_name or f"stop_{index}",
                "to": dest_name or f"stop_{index + 1}",
                "error": "缺少地點名稱",
            })
            continue

        leg = get_travel_route(
            origin_name,
            dest_name,
            mode=mode,
            origin_lat=origin.get("lat"),
            origin_lng=origin.get("lng"),
            destination_lat=destination.get("lat"),
            destination_lng=destination.get("lng"),
            near=near or "台灣",
        )

        if leg.get("error"):
            legs.append({
                "from": origin_name,
                "to": dest_name,
                "error": leg["error"],
            })
            continue

        warnings = leg.get("geocode_warnings") or []
        all_warnings.extend(warnings)
        minutes = leg.get("duration_minutes") or 0
        total_minutes += minutes
        ok_legs += 1
        legs.append({
            "from": origin_name,
            "to": dest_name,
            "mode_label": leg.get("mode_label"),
            "duration_minutes": minutes,
            "distance_km": leg.get("distance_km"),
            "origin": leg.get("origin"),
            "destination": leg.get("destination"),
            "geocode_warnings": warnings,
        })

    return {
        "legs": legs,
        "leg_count": len(legs),
        "ok_legs": ok_legs,
        "total_travel_minutes": total_minutes,
        "mode": mode,
        "geocode_warnings": all_warnings,
        "note": ITINERARY_LEGS_NOTE,
    }
