import httpx
from dotenv import load_dotenv
import os

load_dotenv(override=True)

TDX_AUTH_URL = "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token"
TDX_BASE_URL = "https://tdx.transportdata.tw/api/basic"


def get_tdx_token() -> str:
    resp = httpx.post(TDX_AUTH_URL, data={
        "grant_type": "client_credentials",
        "client_id": os.getenv("TDX_CLIENT_ID"),
        "client_secret": os.getenv("TDX_CLIENT_SECRET"),
    })
    resp.raise_for_status()
    return resp.json()["access_token"]


def search_attractions(city: str, keyword: str = "", limit: int = 5) -> list[dict]:
    token = get_tdx_token()
    headers = {"Authorization": f"Bearer {token}"}

    filter_query = f"contains(ScenicSpotName,'{keyword}')" if keyword else ""
    params = {
        "$top": limit,
        "$select": "ScenicSpotName,DescriptionDetail,Address,OpenTime,Picture,Class1",
        "$format": "JSON",
    }
    if filter_query:
        params["$filter"] = filter_query

    city_path = f"/{city}" if city else ""
    url = f"{TDX_BASE_URL}/v2/Tourism/ScenicSpot{city_path}"
    resp = httpx.get(url, headers=headers, params=params)
    resp.raise_for_status()

    results = []
    for spot in resp.json():
        results.append({
            "name": spot.get("ScenicSpotName", ""),
            "description": (spot.get("DescriptionDetail") or "")[:200],
            "address": spot.get("Address", ""),
            "open_time": spot.get("OpenTime", ""),
            "category": spot.get("Class1", ""),
            "image": spot.get("Picture", {}).get("PictureUrl1", ""),
        })
    return results
