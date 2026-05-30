# 台灣旅遊 AI 助理

用 Claude / Gemini 的 Tool Use，串接 **OpenStreetMap**、**交通部 TDX**、**中央氣象署** 等資料，打造能查詢景點、美食、天氣與交通的旅遊規劃對話助理。

## 功能

- 依縣市搜尋景點、古蹟、美食（OpenStreetMap，主資料源）
- 觀光署 TDX 登錄景點／餐飲（官方補充，覆蓋率有限）
- 查詢 36 小時天氣預報（中央氣象署）
- 查詢市區公車路線、台鐵時刻表（TDX）
- 兩地步行／開車／騎車路線時間（OSRM + Nominatim）
- 多輪對話、SSE 串流、Leaflet 地圖與內文地名連動
- **有一說一**：區分已查證資料與一般參考

## 技術架構

```
使用者（CLI 或 Web）
    ↓
LLM Provider（Anthropic Claude / Google Gemini）
    ↓ Tool Use
┌──────────────┬──────────────┬──────────────┬─────────────┐
│ OSM Places   │ TDX 交通/登錄 │ CWA 天氣     │ OSRM 路線   │
│ (Overpass)   │              │              │ (Nominatim) │
└──────────────┴──────────────┴──────────────┴─────────────┘
    ↓
LLM 整合資料，生成回答（SSE 串流）
```

## 專案結構

```
taiwan-travel-ai/
├── agent.py              # Agent 邏輯、tools、SSE 串流
├── providers/            # LLM backend 抽象（anthropic / gemini）
├── osm_places.py         # OpenStreetMap Overpass POI 查詢
├── api.py                # FastAPI 後端
├── tdx.py                # TDX API
├── cwa.py                # 中央氣象署
├── routing.py            # Nominatim + OSRM
├── web/                  # Next.js 前端
└── tests/
```

## 環境設定

### 1. Python 後端

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. 設定 API Keys

複製 `.env.example` 為 `.env`：

```
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=...
ANTHROPIC_MODEL=claude-sonnet-4-5
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.0-flash
TDX_CLIENT_ID=...
TDX_CLIENT_SECRET=...
CWA_API_KEY=...
```

| Key | 用途 | 費用 |
|-----|------|------|
| Anthropic / Gemini | LLM | 付費（Gemini 有免費額度） |
| TDX / CWA / OSM | 資料 | 免費 |

**切換 LLM**：`LLM_PROVIDER=anthropic` 或 `gemini`（需 `google-genai` 與 `GEMINI_API_KEY`）。

### 3. 執行

```bash
# CLI
python3 main.py

# Web 後端
uvicorn api:app --reload --port 8000

# Web 前端
cd web && npm install && npm run dev
```

開啟 [http://localhost:3000](http://localhost:3000)

## Demo 劇本（面試展示）

1. **台南古蹟**：「台南有什麼古蹟？」→ 應 call `search_places`，可找到赤崁樓等 OSM 地點；TDX 可能不全。
2. **台鐵**：「明天台北到台南有哪些班次？」→ `search_train_schedule`（TDX）。
3. **路線**：「從捷運中山站到 OO 步行多久？」→ `get_travel_route`，注意 geocode 警告。

## Tools 一覽

| Tool | 資料來源 | 說明 |
|------|----------|------|
| `search_places` | OpenStreetMap | 景點／美食主查詢（優先） |
| `search_attractions` | TDX 觀光署 | 登錄景點（補充） |
| `search_restaurants` | TDX 觀光署 | 登錄餐飲（補充） |
| `get_weather_forecast` | CWA | 36 小時天氣 |
| `search_bus_routes` | TDX | 市區公車 |
| `search_train_schedule` | TDX | 台鐵時刻 |
| `get_travel_route` | OSRM / Nominatim | 路線時間 |

## 測試

```bash
pytest
```
