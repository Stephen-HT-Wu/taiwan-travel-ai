# 台灣旅遊 AI 助理

用 Claude / Gemini 的 Tool Use，串接 **OpenStreetMap**、**交通部 TDX**、**中央氣象署** 等開放資料，打造能查詢景點、美食、天氣與交通的旅遊規劃對話助理。

## 功能

### 資料查詢

- 依縣市搜尋景點、古蹟、美食（**OpenStreetMap**，主資料源）
- 觀光署 TDX 登錄景點／餐飲（官方補充，覆蓋率有限）
- 36 小時天氣預報（中央氣象署）
- 市區公車路線、台鐵/高鐵時刻表（TDX）
- 兩地步行／開車／騎車路線時間（OSRM + Nominatim）
- **行程多段移動時間**（`get_itinerary_legs`，一日遊時段表）
- **附近公車/捷運站**與**簡化大眾運輸段估算**（TDX + OSRM，同路線直達／捷運 OD，不含複雜轉乘）

### Web 介面

- SSE 串流回答，顯示查詢階段（理解 → 查資料 → 生成）
- **Leaflet 地圖**：只顯示內文有提到的地點
- **內文地名 link ↔ 地圖標記**雙向對應（點內文聚焦地圖；點地圖標記開 **Google Maps**）
- 每位使用者獨立對話（瀏覽器 `localStorage` UUID session，後端記憶體分 session 存放）
- Markdown 渲染、資料來源面板

### Agent 行為

- **有一說一**：區分已查證工具資料與一般參考，不腦補時間／距離／店名
- 景點優先 OSM；TDX 結果標示為「觀光署登錄」
- 支援 **Anthropic Claude** 或 **Google Gemini** 後端（可切換）

## 技術架構

```
使用者（CLI 或 Web）
    ↓
Next.js（:3000）──SSE proxy──→ FastAPI（:8000）
    ↓                              ↓
Leaflet 地圖 / Chat UI         LLM Provider（Anthropic | Gemini）
                                    ↓ Tool Use
               ┌──────────────┬──────────────┬──────────────┬─────────────┬────────────┐
               │ OSM Places   │ TDX 交通/登錄 │ CWA 天氣     │ OSRM 路線   │ TDX 轉運   │
               │ (Overpass)   │              │              │ (Nominatim) │ (transit)  │
               └──────────────┴──────────────┴──────────────┴─────────────┴────────────┘
                                    ↓
               LLM 整合 → SSE 串流（status / tool_* / text_delta / done）
```

## 專案結構

```
taiwan-travel-ai/
├── agent.py                 # Agent、tools、SYSTEM_PROMPT、SSE 串流
├── api.py                   # FastAPI `/api/chat`（session 記憶體）
├── providers/               # LLM 抽象（anthropic / gemini）
├── osm_places.py            # OSM Nominatim + Overpass POI
├── tdx.py / cwa.py          # TDX、氣象署
├── routing.py               # Nominatim geocoding + OSRM
├── transit.py               # TDX 公車/捷運站與段時間估算
├── main.py                  # CLI 入口
├── web/
│   ├── app/api/chat/        # Next.js SSE proxy → 後端
│   ├── components/          # Chat、MapPanel、Markdown、地名 link
│   └── lib/                 # sessionId、googleMaps URL
└── tests/                   # pytest 整合測試（mock HTTP）
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

```env
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
| TDX / CWA / OSM / OSRM | 資料 | 免費 |
| Google Maps 深連結 | 地圖標記點擊 | 免費（未使用 Places API） |

**切換 LLM**：`.env` 設 `LLM_PROVIDER=anthropic` 或 `gemini`（Gemini 需 `pip install google-genai` 與 `GEMINI_API_KEY`）。修改 `.env` 後需**重啟 uvicorn**。

### 3. 執行

```bash
# 終端 1：後端
source venv/bin/activate
uvicorn api:app --reload --port 8000

# 終端 2：前端（需在 web/ 目錄）
cd web && npm install && npm run dev
```

開啟 [http://localhost:3000](http://localhost:3000)

> 前端透過 `web/app/api/chat/route.ts` 代理至 `http://127.0.0.1:8000`。請確認兩個服務都在跑。

### 4. CLI（可選）

```bash
source venv/bin/activate
python3 main.py
```

## Demo 劇本（面試／展示）

| 情境 | 範例問題 | 預期工具 | 展示重點 |
|------|----------|----------|----------|
| 古蹟 | 台南有什麼古蹟？ | `search_places` | OSM 找得到赤崁樓；地圖 pin 與內文 link 對應 |
| 美食 | 高雄有什麼必吃美食？ | `search_places` + TDX | OSM 主查詢；TDX 標示登錄補充 |
| 子區域 | 花蓮市有什麼餐廳？ | `search_places`（keyword） | 縣市 + 區名縮小 Overpass 範圍 |
| 台鐵 | 明天台北到台南有哪些班次？ | `search_train_schedule` | TDX 即時班次 |
| 路線 | 從捷運中山站到 OO 步行多久？ | `get_travel_route` | geocode 警告、不腦補時間 |
| 一日遊 | 台北到嘉義一日遊，含時段 | `search_places` + `get_itinerary_legs` + 高鐵 | 時段表、地圖 link |
| 大眾運輸 | 兩景點能搭公車嗎？ | `estimate_transit_segment` | 僅同路線直達；轉乘會標示無法估算 |
| 天氣 | 台北明天天氣如何？ | `get_weather_forecast` | CWA 36 小時預報 |

## Tools 一覽

| Tool | 資料來源 | 說明 |
|------|----------|------|
| `search_places` | OpenStreetMap | 景點／美食**主查詢**（優先） |
| `search_attractions` | TDX 觀光署 | 登錄景點（補充） |
| `search_restaurants` | TDX 觀光署 | 登錄餐飲（補充） |
| `get_weather_forecast` | CWA | 36 小時天氣 |
| `search_bus_routes` | TDX | 市區公車 |
| `search_train_schedule` | TDX | 台鐵時刻 |
| `search_hsr_schedule` | TDX | 高鐵時刻 |
| `get_travel_route` | OSRM / Nominatim | 單段路線時間 |
| `get_itinerary_legs` | OSRM / Nominatim | 行程多段移動時間 |
| `search_nearby_transit_stops` | TDX | 附近公車/捷運站 |
| `estimate_transit_segment` | TDX + OSRM | 大眾運輸段估算（簡化） |

`estimate_transit_segment` 限制：僅支援同路線公車直達或同系統捷運 OD；不含等車、轉乘與即時誤點。首次查某縣市公車站牌會快取 TDX 整包資料。

## 測試與 CI

```bash
source venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

GitHub Actions（`master` / `main`）會跑 Python 整合測試與 Next.js build。

## 已知限制

- **Session** 存在後端記憶體，重啟 uvicorn 會清空；多 instance 不共用
- **OSM Overpass** 大範圍查詢可能較慢；建議帶 `keyword`（區／市名）縮小範圍
- **TDX 觀光資料** 都會區常不全，不可當完整列表
- **Google Maps 深連結** 為關鍵字 + 座標模糊搜尋，不保證 100% 對到同一 POI
