from dataclasses import dataclass, field
from typing import Any, Dict, Generator, List, Optional, Protocol


@dataclass
class ToolUseBlock:
    type: str
    id: str
    name: str
    input: Dict[str, Any]


@dataclass
class TextBlock:
    type: str
    text: str


@dataclass
class TurnResult:
    stop_reason: str
    content: List[Any] = field(default_factory=list)


def content_blocks_to_api(blocks: List[Any]) -> List[dict]:
    """Convert provider blocks to Anthropic-compatible message content dicts."""
    api_blocks: List[dict] = []
    for block in blocks:
        if isinstance(block, dict):
            api_blocks.append(block)
            continue
        block_type = getattr(block, "type", None)
        if block_type == "text":
            api_blocks.append({"type": "text", "text": block.text})
        elif block_type == "tool_use":
            api_blocks.append({
                "type": "tool_use",
                "id": block.id,
                "name": block.name,
                "input": block.input,
            })
    return api_blocks


def sanitize_messages(messages: List[dict]) -> None:
    """Normalize in-memory session history for Anthropic API compatibility."""
    for index, message in enumerate(messages):
        content = message.get("content")
        if not isinstance(content, list):
            continue
        if message.get("role") == "assistant":
            messages[index] = {**message, "content": content_blocks_to_api(content)}
            continue
        if message.get("role") == "user":
            cleaned = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "tool_result":
                    cleaned.append({
                        "type": "tool_result",
                        "tool_use_id": item["tool_use_id"],
                        "content": item["content"],
                    })
                else:
                    cleaned.append(item)
            messages[index] = {**message, "content": cleaned}


class LLMProvider(Protocol):
    def stream_turn(
        self,
        *,
        system: str,
        tools: List[dict],
        messages: List[dict],
        max_tokens: int,
    ) -> Generator[dict, None, TurnResult]:
        ...
