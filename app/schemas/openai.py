from __future__ import annotations

import time
import uuid
from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "local-qwen2.5-coder-7b-rag"
    messages: list[ChatMessage]
    workspace: str | None = None
    stream: bool = False


class ChatChoice(BaseModel):
    index: int = 0
    finish_reason: str = "stop"
    message: ChatMessage


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:24]}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str = "local-qwen2.5-coder-7b-rag"
    choices: list[ChatChoice]
    usage: Usage = Field(default_factory=Usage)


class ModelItem(BaseModel):
    id: str
    object: str = "model"
    owned_by: str = "local"


class ModelsResponse(BaseModel):
    object: str = "list"
    data: list[ModelItem]