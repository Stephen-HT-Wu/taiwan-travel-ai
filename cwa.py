import os
import httpx
from dotenv import load_dotenv

load_dotenv()

CWA_BASE_URL = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001"

# 縣市中文名稱對照（CWA API 使用「臺」）
CITY_NAMES = {
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


def get_weather_forecast(city: str = "", location_name: str = "") -> dict:
    api_key = os.getenv("CWA_API_KEY")
    if not api_key:
        return {
            "error": "未設定 CWA_API_KEY，請至 https://opendata.cwa.gov.tw 申請授權碼並加入 .env",
        }

    target = location_name or CITY_NAMES.get(city, city)
    if not target:
        return {"error": "請提供 city（英文縣市名）或 location_name（中文縣市名）"}

    resp = httpx.get(CWA_BASE_URL, params={
        "Authorization": api_key,
        "format": "JSON",
        "locationName": target,
    })
    resp.raise_for_status()
    data = resp.json()

    locations = data.get("records", {}).get("location", [])
    if not locations:
        return {"error": f"找不到 {target} 的天氣資料"}

    loc = locations[0]
    elements = {el["elementName"]: el for el in loc.get("weatherElement", [])}

    periods = []
    wx = elements.get("Wx", {}).get("time", [])
    for i, period in enumerate(wx[:3]):
        start = period.get("startTime", "")
        end = period.get("endTime", "")
        weather = period.get("parameter", {}).get("parameterName", "")

        pop = elements.get("PoP", {}).get("time", [])
        min_t = elements.get("MinT", {}).get("time", [])
        max_t = elements.get("MaxT", {}).get("time", [])

        periods.append({
            "start": start,
            "end": end,
            "weather": weather,
            "rain_probability": pop[i]["parameter"]["parameterName"] if i < len(pop) else "",
            "min_temp": min_t[i]["parameter"]["parameterName"] if i < len(min_t) else "",
            "max_temp": max_t[i]["parameter"]["parameterName"] if i < len(max_t) else "",
        })

    return {
        "location": loc.get("locationName", target),
        "forecast": periods,
    }
