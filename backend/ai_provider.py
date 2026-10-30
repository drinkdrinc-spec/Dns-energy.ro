"""Small OpenAI-compatible streaming adapter replacing Emergent's private LLM wrapper.

Set OPENAI_API_KEY and OPENAI_MODEL in the deployment environment.
"""
import os
from dataclasses import dataclass
from typing import Any

from openai import AsyncOpenAI


@dataclass
class TextDelta:
    content: str


@dataclass
class StreamDone:
    pass


@dataclass
class ImageContent:
    image_base64: str


@dataclass
class FileContentWithMimeType:
    file_path: str
    mime_type: str


@dataclass
class UserMessage:
    text: str
    file_contents: list[Any] | None = None


class LlmChat:
    def __init__(self, api_key: str, session_id: str, system_message: str,
                 initial_messages: list[dict] | None = None):
        self.api_key = api_key
        self.session_id = session_id
        self.system_message = system_message
        self.messages = list(initial_messages or [{"role": "system", "content": system_message}])
        self.model = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
        self.client = AsyncOpenAI(api_key=api_key)

    def with_model(self, provider: str, model: str):
        # Provider/model aliases from the old integration are intentionally not
        # forwarded; the deployment's OPENAI_MODEL is the single source of truth.
        return self

    async def stream_message(self, message: UserMessage):
        content: Any = message.text
        parts = []
        for item in message.file_contents or []:
            if isinstance(item, ImageContent):
                parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{item.image_base64}"},
                })
            elif isinstance(item, FileContentWithMimeType):
                if item.mime_type.startswith("image/"):
                    import base64
                    with open(item.file_path, "rb") as handle:
                        encoded = base64.b64encode(handle.read()).decode("ascii")
                    parts.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{item.mime_type};base64,{encoded}"},
                    })
                else:
                    raise ValueError("Only image attachments are supported by the OpenAI adapter; convert PDF pages to images first.")
        if parts:
            content = [{"type": "text", "text": message.text}] + parts
        self.messages.append({"role": "user", "content": content})
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=self.messages,
            stream=True,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if isinstance(delta, str) and delta:
                yield TextDelta(delta)
        yield StreamDone()
