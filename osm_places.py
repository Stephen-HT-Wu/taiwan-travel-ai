import re
import httpx
from typing import List, Optional, Tuple

from routing import USER_AGENT

OVERPASS_URLS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_TIMEOUT = 15.0
OVERPASS_TIMEOUT = 45.0
AREA_KEYWORD_RE = re.compile(r"(市|區|鄉|鎮|里)$")
# POI 類型關鍵字（非具體地名）；若用 Nominatim 縮小 bbox 常會對到錯誤的小點。
POI_CATEGORY_KEYWORDS = frozenset({
    "夜市", "商圈", "老街", "溫泉", "温泉", "市集", "傳統市場", "市場",
})
MARKET_NAME_KEYWORDS = frozenset({"夜市", "市集", "傳統市場", "市場"})

CITY_ZH = {
    "Taipei": "臺北市",
    "NewTaipei": "新北市",
    "Taoyuan": "桃園市",
    "Taichung": "臺中市",
    "Tainan": "臺南市",
    "Kaohsiung": "高雄市",
    "Keelung": "基隆市",
    "Hsinchu": "新竹市",
    "HsinchuCounty": "新竹縣",
    "MiaoliCounty": "苗栗縣",
    "ChanghuaCounty": "彰化縣",
    "NantouCounty": "南投縣",
    "YunlinCounty": "雲林縣",
    "Chiayi": "嘉義市",
    "ChiayiCounty": "嘉義縣",
    "PingtungCounty": "屏東縣",
    "YilanCounty": "宜蘭縣",
    "HualienCounty": "花蓮縣",
    "TaitungCounty": "臺東縣",
    "PenghuCounty": "澎湖縣",
    "KinmenCounty": "金門縣",
    "LienchiangCounty": "連江縣",
}


def _city_label(city: str) -> str:
    if city in CITY_ZH:
        return CITY_ZH[city]
    if city.endswith("County"):
        return city.replace("County", "縣")
    return city


def _escape_overpass(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _is_area_keyword(keyword: str) -> bool:
    return bool(AREA_KEYWORD_RE.search(keyword.strip()))


def _is_poi_category_keyword(keyword: str) -> bool:
    return keyword.strip() in POI_CATEGORY_KEYWORDS


def _market_related_filter(name_filter: str) -> bool:
    if not name_filter:
        return False
    if name_filter in MARKET_NAME_KEYWORDS:
        return True
    return "夜市" in name_filter or "市場" in name_filter


def _bbox_span(area: dict) -> float:
    return (area["north"] - area["south"]) * (area["east"] - area["west"])


def _nominatim_search(query: str) -> Optional[dict]:
    resp = httpx.get(
        NOMINATIM_URL,
        params={
            "q": query,
            "format": "json",
            "limit": 1,
            "countrycodes": "tw",
        },
        headers={"User-Agent": USER_AGENT},
        timeout=NOMINATIM_TIMEOUT,
    )
    resp.raise_for_status()
    hits = resp.json()
    if not hits:
        return None

    hit = hits[0]
    bbox = hit.get("boundingbox") or []
    if len(bbox) != 4:
        return None

    south, north, west, east = map(float, bbox)
    return {
        "name": hit.get("display_name", query),
        "south": south,
        "west": west,
        "north": north,
        "east": east,
    }


def _resolve_search_area(city_zh: str, keyword: str = "") -> Optional[dict]:
    county = _nominatim_search(city_zh)
    if not county:
        return None

    keyword = keyword.strip()
    if not keyword:
        return {**county, "name_filter": ""}

    if _is_poi_category_keyword(keyword):
        return {**county, "name_filter": keyword}

    county_span = _bbox_span(county)

    if _is_area_keyword(keyword):
        for query in (f"{keyword}, {city_zh}, 台灣", f"{keyword}, 台灣"):
            sub = _nominatim_search(query)
            if sub and _bbox_span(sub) < county_span * 0.5:
                return {**sub, "name_filter": ""}
        return {**county, "name_filter": ""}

    for query in (f"{keyword}, {city_zh}, 台灣", f"{keyword}, 台灣"):
        sub = _nominatim_search(query)
        if sub and _bbox_span(sub) < county_span * 0.8:
            return {**sub, "name_filter": keyword}

    return {**county, "name_filter": keyword}


def _filter_lines(
    base_tags: List[Tuple[str, str]],
    name_filter: str,
    bbox: Tuple[float, float, float, float],
) -> str:
    south, west, north, east = bbox
    bbox_part = f"({south},{west},{north},{east})"
    keyword_part = ""
    if name_filter:
        escaped = _escape_overpass(name_filter)
        keyword_part = f'["name"~"{escaped}",i]'

    kinds = ("node", "way")
    lines = []
    for kind in kinds:
        for tag in base_tags:
            lines.append(f'{kind}["{tag[0]}"="{tag[1]}"]{keyword_part}{bbox_part};')
    return "\n  ".join(lines)


def _build_query(area: dict, place_type: str, limit: int) -> str:
    name_filter = area.get("name_filter", "")

    if place_type == "restaurant":
        tags = [("amenity", "restaurant"), ("amenity", "cafe"), ("amenity", "fast_food")]
    elif place_type == "attraction":
        tags = [("tourism", "attraction"), ("tourism", "museum"), ("historic", "monument"), ("historic", "castle")]
        if _market_related_filter(name_filter):
            tags.append(("amenity", "marketplace"))
    else:
        tags = [
            ("tourism", "attraction"),
            ("tourism", "museum"),
            ("historic", "monument"),
            ("historic", "castle"),
            ("amenity", "restaurant"),
            ("amenity", "cafe"),
        ]

    bbox = (area["south"], area["west"], area["north"], area["east"])
    body = _filter_lines(tags, name_filter, bbox)
    overpass_timeout = 25 if _bbox_span(area) < 0.05 else 45
    return f"""
[out:json][timeout:{overpass_timeout}];
(
  {body}
);
out center {limit};
"""


def _element_name(tags: dict) -> str:
    for key in ("name:zh-TW", "name:zh", "name:zh_tw", "name"):
        value = tags.get(key)
        if value:
            return value.strip()
    return ""


def _element_type(tags: dict, requested: str) -> str:
    if tags.get("amenity") in {"restaurant", "cafe", "fast_food"}:
        return "restaurant"
    if requested == "restaurant":
        return "restaurant"
    return "attraction"


def _parse_elements(
    elements: list,
    place_type: str,
    name_filter: str,
    limit: int,
) -> List[dict]:
    results = []
    seen = set()

    for element in elements:
        tags = element.get("tags") or {}
        name = _element_name(tags)
        if not name:
            continue

        if name_filter and name_filter not in name:
            continue

        lat = element.get("lat")
        lng = element.get("lon")
        if lat is None or lng is None:
            center = element.get("center") or {}
            lat = center.get("lat")
            lng = center.get("lon")
        if lat is None or lng is None:
            continue

        key = (round(float(lat), 5), round(float(lng), 5), name)
        if key in seen:
            continue
        seen.add(key)

        mapped_type = _element_type(tags, place_type)
        if place_type in {"attraction", "restaurant"} and mapped_type != place_type:
            continue

        address_parts = [
            tags.get("addr:city"),
            tags.get("addr:district"),
            tags.get("addr:street"),
            tags.get("addr:housenumber"),
        ]
        address = "".join(part for part in address_parts if part)

        results.append({
            "name": name,
            "lat": float(lat),
            "lng": float(lng),
            "address": address,
            "type": mapped_type,
            "source": "OpenStreetMap",
            "category": tags.get("tourism") or tags.get("historic") or tags.get("amenity") or "",
        })
        if len(results) >= limit:
            break

    return results


def _run_overpass(query: str) -> dict:
    last_error: Optional[Exception] = None
    for url in OVERPASS_URLS:
        try:
            resp = httpx.post(
                url,
                data={"data": query},
                headers={"User-Agent": USER_AGENT},
                timeout=OVERPASS_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json()
        except (httpx.TimeoutException, httpx.HTTPError) as exc:
            last_error = exc
            continue

    if last_error:
        raise last_error
    raise RuntimeError("Overpass query failed")


def search_places(
    city: str,
    keyword: str = "",
    place_type: str = "all",
    limit: int = 20,
) -> List[dict]:
    """
    Search attractions or restaurants in a Taiwan city using OpenStreetMap Overpass.
    place_type: all | attraction | restaurant
    """
    normalized_type = (place_type or "all").lower()
    if normalized_type not in {"all", "attraction", "restaurant"}:
        return [{"error": f"不支援的 place_type「{place_type}」，請使用 all、attraction 或 restaurant"}]

    city_zh = _city_label(city)
    area = _resolve_search_area(city_zh, keyword.strip())
    if not area:
        return [{"error": f"無法定位縣市區域：{city_zh}"}]

    query = _build_query(area, normalized_type, limit)
    try:
        payload = _run_overpass(query)
    except httpx.TimeoutException:
        return [{"error": "OpenStreetMap 查詢逾時，請縮小範圍（例如指定區/市關鍵字）或稍後再試"}]
    except httpx.HTTPError as exc:
        return [{"error": str(exc)}]

    elements = payload.get("elements") or []
    if not elements:
        return []

    return _parse_elements(elements, normalized_type, area.get("name_filter", ""), limit)
