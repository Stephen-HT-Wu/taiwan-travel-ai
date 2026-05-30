import json
import os
import uuid
from typing import Generator, List

from providers.base import TextBlock, ToolUseBlock, TurnResult


def _friendly_gemini_error(exc: Exception) -> RuntimeError:
    message = str(exc)
    upper = message.upper()
    if "429" in message or "RESOURCE_EXHAUSTED" in upper:
        return RuntimeError(
            "Gemini API 配額已用完（429 RESOURCE_EXHAUSTED）。"
            "Free tier 每日請求數有限，且 agent 每輪對話會消耗多次 API。"
            "可等到太平洋時間午夜 quota 重置、在 AI Studio 儲值，"
            "或將 .env 的 LLM_PROVIDER 改為 anthropic 後重啟 backend。"
        )
    return RuntimeError(message)


def _tools_to_gemini(tools: List[dict]) -> list:
    declarations = []
    for tool in tools:
        declarations.append({
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": tool.get("input_schema") or {"type": "object", "properties": {}},
        })
    return declarations


def _anthropic_messages_to_gemini(messages: List[dict]) -> list:
    contents = []
    for message in messages:
        role = message.get("role")
        content = message.get("content")

        if role == "user" and isinstance(content, str):
            contents.append({"role": "user", "parts": [{"text": content}]})
            continue

        if role == "assistant" and isinstance(content, list):
            parts = []
            for block in content:
                block_type = getattr(block, "type", None) or block.get("type")
                if block_type == "text":
                    text = getattr(block, "text", None) or block.get("text", "")
                    parts.append({"text": text})
                elif block_type == "tool_use":
                    name = getattr(block, "name", None) or block.get("name")
                    tool_input = getattr(block, "input", None) or block.get("input") or {}
                    tool_id = getattr(block, "id", None) or block.get("id") or str(uuid.uuid4())
                    parts.append({
                        "function_call": {
                            "name": name,
                            "args": tool_input,
                            "id": tool_id,
                        }
                    })
            if parts:
                contents.append({"role": "model", "parts": parts})
            continue

        if role == "user" and isinstance(content, list):
            parts = []
            for item in content:
                if item.get("type") != "tool_result":
                    continue
                parts.append({
                    "function_response": {
                        "name": item.get("name") or "tool",
                        "response": {"result": item.get("content", "")},
                        "id": item.get("tool_use_id", str(uuid.uuid4())),
                    }
                })
            if parts:
                contents.append({"role": "user", "parts": parts})

    return contents


class GeminiProvider:
    def __init__(self) -> None:
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise RuntimeError(
                "Gemini provider requires google-genai. Install with: pip install google-genai"
            ) from exc

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini")

        self._types = types
        self.client = genai.Client(api_key=api_key)
        self.model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    def _config(self, system: str, tools: List[dict], max_tokens: int):
        return self._types.GenerateContentConfig(
            system_instruction=system,
            tools=[self._types.Tool(function_declarations=_tools_to_gemini(tools))],
            max_output_tokens=max_tokens,
        )

    def stream_turn(
        self,
        *,
        system: str,
        tools: List[dict],
        messages: List[dict],
        max_tokens: int,
    ) -> Generator[dict, None, TurnResult]:
        contents = _anthropic_messages_to_gemini(messages)
        config = self._config(system, tools, max_tokens)

        text_parts: List[str] = []
        function_calls = []
        tool_phase_started = False

        try:
            stream = self.client.models.generate_content_stream(
                model=self.model,
                contents=contents,
                config=config,
            )
        except Exception as exc:
            raise _friendly_gemini_error(exc) from exc

        try:
            for chunk in stream:
                if getattr(chunk, "text", None):
                    text_parts.append(chunk.text)
                    yield {"event": "text_delta", "text": chunk.text}

                for candidate in getattr(chunk, "candidates", None) or []:
                    content = getattr(candidate, "content", None)
                    for part in getattr(content, "parts", None) or []:
                        function_call = getattr(part, "function_call", None)
                        if not function_call:
                            continue
                        function_calls.append(function_call)
                        if not tool_phase_started:
                            tool_phase_started = True
                            yield {"event": "tool_use_start"}
        except Exception as exc:
            raise _friendly_gemini_error(exc) from exc

        return self._build_turn_result(text_parts, function_calls)

    def create_turn(
        self,
        *,
        system: str,
        tools: List[dict],
        messages: List[dict],
        max_tokens: int,
    ) -> TurnResult:
        contents = _anthropic_messages_to_gemini(messages)
        config = self._config(system, tools, max_tokens)
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=config,
            )
        except Exception as exc:
            raise _friendly_gemini_error(exc) from exc

        text_parts = []
        function_calls = []
        for candidate in response.candidates or []:
            for part in candidate.content.parts or []:
                if getattr(part, "text", None):
                    text_parts.append(part.text)
                function_call = getattr(part, "function_call", None)
                if function_call:
                    function_calls.append(function_call)

        return self._build_turn_result(text_parts, function_calls)

    def _build_turn_result(self, text_parts: List[str], function_calls: list) -> TurnResult:
        content = []
        if function_calls:
            stop_reason = "tool_use"
            for call in function_calls:
                content.append(
                    ToolUseBlock(
                        type="tool_use",
                        id=str(uuid.uuid4()),
                        name=call.name,
                        input=dict(call.args or {}),
                    )
                )
        else:
            stop_reason = "end_turn"
            if text_parts:
                content.append(TextBlock(type="text", text="".join(text_parts)))

        return TurnResult(stop_reason=stop_reason, content=content)
