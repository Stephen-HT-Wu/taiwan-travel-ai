import json
import os
from dotenv import load_dotenv
import anthropic
from tdx import search_attractions

load_dotenv(override=True)

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

tools = [
    {
        "name": "search_attractions",
        "description": "搜尋台灣各縣市的觀光景點",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "縣市英文名，例如 Tainan、Taipei、Taichung、Hualien、Taitung",
                },
                "keyword": {
                    "type": "string",
                    "description": "景點名稱關鍵字（可選）",
                },
                "limit": {
                    "type": "integer",
                    "description": "回傳幾筆資料，預設 5",
                },
            },
            "required": ["city"],
        },
    }
]

SYSTEM_PROMPT = """你是一個台灣旅遊規劃助理。
當使用者詢問景點或行程時，使用 search_attractions 工具查詢真實資料，再根據資料給出建議。
回答時用繁體中文，口吻親切自然。"""


def run_agent(user_message: str, messages: list):
    print("-" * 40)
    messages.append({"role": "user", "content": user_message})

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=tools,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    print(block.text)
            break

        # 執行 tool call
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                print(f"[呼叫工具] {block.name}({block.input})")

                if block.name == "search_attractions":
                    result = search_attractions(**block.input)
                else:
                    result = {"error": f"未知工具 {block.name}"}

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })

        messages.append({"role": "user", "content": tool_results})


if __name__ == "__main__":
    print("🗺️  台灣旅遊助理（輸入 quit 離開）")
    print("=" * 40)
    messages = []
    while True:
        user_input = input("\n你：").strip()
        if user_input.lower() in ("quit", "exit", "離開", "q"):
            print("掰掰！旅途愉快 ✈️")
            break
        if not user_input:
            continue
        run_agent(user_input, messages)
