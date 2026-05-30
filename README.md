# 台灣旅遊 AI 助理

用 Claude AI 的 Tool Use 功能，串接台灣政府開放資料（TDX、中央氣象署），打造能查詢真實景點、美食、天氣與交通資訊的旅遊規劃對話助理。

## 功能

- 依縣市搜尋觀光景點（TDX）
- 依縣市搜尋餐廳、小吃（TDX）
- 查詢 36 小時天氣預報（中央氣象署）
- 查詢市區公車路線、台鐵時刻表（TDX）
- 多輪對話，記住上下文
- AI 自動判斷何時需要查詢資料、查什麼
- Next.js 網頁介面 + SSE 串流輸出

## 技術架構

```
使用者（CLI 或 Web）
    ↓
Claude API (claude-sonnet-4-5) + Tool Use
    ↓
┌─────────────┬──────────────┬─────────────┐
│  TDX 景點   │  TDX 餐廳    │  CWA 天氣   │
│  TDX 公車   │  TDX 台鐵    │             │
└─────────────┴──────────────┴─────────────┘
    ↓
Claude 整合資料，生成回答（串流）
```

## 專案結構

```
taiwan-travel-ai/
├── agent.py          # Claude agent 邏輯、tools 定義、串流
├── api.py            # FastAPI 後端（SSE 串流 API）
├── main.py           # CLI 主程式
├── tdx.py            # TDX API（景點、餐廳、公車、台鐵）
├── cwa.py            # 中央氣象署天氣 API
├── requirements.txt
├── web/              # Next.js 前端
│   ├── app/
│   └── components/
├── .env.example
└── .gitignore
```

## 環境設定

### 1. Python 後端

```bash
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 設定 API Keys

複製 `.env.example` 為 `.env`，填入你的 keys：

```
TDX_CLIENT_ID=your_tdx_client_id
TDX_CLIENT_SECRET=your_tdx_client_secret
ANTHROPIC_API_KEY=your_anthropic_api_key
CWA_API_KEY=your_cwa_api_key
```

- **TDX**：至 [tdx.transportdata.tw](https://tdx.transportdata.tw) 註冊，建立應用程式取得 Client ID / Secret
- **Anthropic**：至 [console.anthropic.com](https://console.anthropic.com/settings/keys) 建立 API key
- **CWA**：至 [opendata.cwa.gov.tw](https://opendata.cwa.gov.tw) 註冊，取得授權碼

### 3. 執行 CLI

```bash
python3 main.py
```

### 4. 執行 Web 版

需要 Node.js >= 18.15（建議 18.17+）。

終端機 1 — 啟動後端：

```bash
source venv/bin/activate
uvicorn api:app --reload --port 8000
```

終端機 2 — 啟動前端：

```bash
cd web
npm install
npm run dev
```

開啟 [http://localhost:3000](http://localhost:3000)

## 使用範例

```
你：我想去台南玩兩天，有什麼景點推薦？
[呼叫工具] search_attractions({'city': 'Tainan', 'limit': 10})

你：那邊有什麼必吃美食？
[呼叫工具] search_restaurants({'city': 'Tainan', 'limit': 5})

你：後天會下雨嗎？
[呼叫工具] get_weather_forecast({'city': 'Tainan'})

你：從台北到台南有哪些台鐵班次？
[呼叫工具] search_train_schedule({'origin': '台北', 'destination': '台南'})
```

## Tools 一覽

| Tool | 資料來源 | 說明 |
|------|----------|------|
| `search_attractions` | TDX | 搜尋觀光景點 |
| `search_restaurants` | TDX | 搜尋餐廳、小吃 |
| `get_weather_forecast` | CWA | 36 小時天氣預報 |
| `search_bus_routes` | TDX | 市區公車路線 |
| `search_train_schedule` | TDX | 台鐵站間時刻表 |
