# 台灣旅遊 AI 助理

用 Claude AI 的 Tool Use 功能，串接台灣政府開放資料（TDX），打造能查詢真實景點資訊的旅遊規劃對話助理。

## 功能

- 依縣市搜尋觀光景點（資料來源：TDX 運輸資料流通服務）
- 多輪對話，記住上下文
- AI 自動判斷何時需要查詢資料、查什麼

## 技術架構

```
使用者輸入
    ↓
Claude API (claude-sonnet-4-5)
    ↓ tool use
TDX API（景點資料）
    ↓
Claude 整合資料，生成回答
```

## 專案結構

```
taiwan-travel-ai/
├── main.py       # 主程式，Claude tool use 對話邏輯
├── tdx.py        # TDX API 認證與景點查詢
├── .env          # API keys（不進 git）
└── .gitignore
```

## 環境設定

### 1. 建立虛擬環境並安裝套件

```bash
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install anthropic httpx python-dotenv
```

### 2. 設定 API Keys

複製 `.env.example` 為 `.env`，填入你的 keys：

```
TDX_CLIENT_ID=your_tdx_client_id
TDX_CLIENT_SECRET=your_tdx_client_secret
ANTHROPIC_API_KEY=your_anthropic_api_key
```

- **TDX**：至 [tdx.transportdata.tw](https://tdx.transportdata.tw) 註冊，建立應用程式取得 Client ID / Secret
- **Anthropic**：至 [console.anthropic.com](https://console.anthropic.com/settings/keys) 建立 API key

### 3. 執行

```bash
python3 main.py
```

## 使用範例

```
🗺️  台灣旅遊助理（輸入 quit 離開）
========================================

你：我想去台南玩兩天，有什麼景點推薦？
[呼叫工具] search_attractions({'city': 'Tainan', 'limit': 10})
台南真是個玩兩天剛剛好的地方！...

你：古蹟的部分可以多說一點嗎？
（記住上下文，不需要重複說台南）
```

## 下一步計畫

- [ ] 加入天氣查詢 tool（中央氣象署 API）
- [ ] 加入餐廳查詢 tool（TDX 觀光資料）
- [ ] 加入大眾交通查詢 tool（TDX 公車 / 台鐵）
- [ ] Next.js 網頁介面
- [ ] 串流輸出（Streaming）讓回應更即時
