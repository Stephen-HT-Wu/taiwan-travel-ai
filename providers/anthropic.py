import os
from typing import Generator, List

import anthropic

from providers.base import TextBlock, ToolUseBlock, TurnResult


class AnthropicProvider:
    def __init__(self) -> None:
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")

    def stream_turn(
        self,
        *,
        system: str,
        tools: List[dict],
        messages: List[dict],
        max_tokens: int,
    ) -> Generator[dict, None, TurnResult]:
        tool_phase_started = False
        with self.client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            tools=tools,
            messages=messages,
        ) as stream:
            for event in stream:
                if event.type == "content_block_start":
                    block = event.content_block
                    if block.type == "tool_use" and not tool_phase_started:
                        tool_phase_started = True
                        yield {"event": "tool_use_start"}
                elif event.type == "content_block_delta" and event.delta.type == "text_delta":
                    yield {"event": "text_delta", "text": event.delta.text}
            final = stream.get_final_message()

        content = []
        for block in final.content:
            if block.type == "text":
                content.append(TextBlock(type="text", text=block.text))
            elif block.type == "tool_use":
                content.append(
                    ToolUseBlock(
                        type="tool_use",
                        id=block.id,
                        name=block.name,
                        input=dict(block.input),
                    )
                )

        return TurnResult(stop_reason=final.stop_reason, content=content)

    def create_turn(
        self,
        *,
        system: str,
        tools: List[dict],
        messages: List[dict],
        max_tokens: int,
    ) -> TurnResult:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            tools=tools,
            messages=messages,
        )

        content = []
        for block in response.content:
            if block.type == "text":
                content.append(TextBlock(type="text", text=block.text))
            elif block.type == "tool_use":
                content.append(
                    ToolUseBlock(
                        type="tool_use",
                        id=block.id,
                        name=block.name,
                        input=dict(block.input),
                    )
                )

        return TurnResult(stop_reason=response.stop_reason, content=content)
