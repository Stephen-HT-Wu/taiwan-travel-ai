import httpx
from dotenv import load_dotenv
import os
from datetime import date
from typing import Optional, Union, List, Dict

load_dotenv()

TDX_AUTH_URL = "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token"
TDX_BASE_URL = "https://tdx.transportdata.tw/api/basic"

_token_cache: Optional[str] = None


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


def search_attractions(city: str, keyword: str = "", limit: int = 5) -> List[dict]:
    params = {
        "$top": limit,
        "$select": "ScenicSpotName,DescriptionDetail,Address,OpenTime,Picture,Class1",
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
        }
        for spot in spots
    ]


def search_restaurants(city: str, keyword: str = "", limit: int = 5) -> List[dict]:
    params = {
        "$top": limit,
        "$select": "RestaurantName,Description,Address,OpenTime,Phone,City",
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


# 常用台鐵站代碼（避免每次查詢站名列表）
STATION_IDS = {
    "台北": "1000", "臺北": "1000",
    "台中": "3300", "臺中": "3300",
    "台南": "4220", "臺南": "4220",
    "高雄": "4210",
    "花蓮": "7000",
    "台東": "6000", "臺東": "6000",
    "新竹": "1200",
    "嘉義": "4080",
    "基隆": "0900",
    "宜蘭": "1300",
    "彰化": "3360",
    "屏東": "5000",
}


def search_train_schedule(
    origin: str,
    destination: str,
    travel_date: str = "",
    limit: int = 5,
) -> List[dict]:
    origin_id = STATION_IDS.get(origin)
    dest_id = STATION_IDS.get(destination)
    if not origin_id or not dest_id:
        supported = "、".join(sorted(set(STATION_IDS.keys())))
        return [{"error": f"請使用支援的站名，例如：{supported}"}]

    query_date = travel_date or date.today().strftime("%Y-%m-%d")
    params = {"$top": limit, "$format": "JSON"}
    trains = _tdx_get(
        f"/v3/Rail/TRA/DailyTrainTimetable/OD/{origin_id}/to/{dest_id}/{query_date}",
        params,
    )

    results = []
    for train in trains:
        stop_times = train.get("DailyTrainInfo", {}).get("StopTimes", [])
        if not stop_times:
            stop_times = train.get("StopTimes", [])

        departure = stop_times[0].get("DepartureTime", "") if stop_times else ""
        arrival = stop_times[-1].get("ArrivalTime", "") if stop_times else ""
        train_info = train.get("DailyTrainInfo", train)

        results.append({
            "train_no": train_info.get("TrainNo", ""),
            "train_type": train_info.get("TrainTypeName", {}).get("Zh_tw", ""),
            "departure_time": departure,
            "arrival_time": arrival,
            "duration_minutes": train_info.get("JourneyTime", ""),
            "origin": origin,
            "destination": destination,
            "date": query_date,
        })
    return results
