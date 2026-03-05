from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    host: str = Field(default="127.0.0.1", validation_alias=AliasChoices("AGENT_HOST", "LOCAL_AGENT_HOST"))
    port: int = Field(default=3210, validation_alias=AliasChoices("AGENT_PORT", "LOCAL_AGENT_PORT"))

    agent_home: Path = Path.home() / ".local-agent"
    qdrant_url: str = Field(
        default="http://127.0.0.1:6333",
        validation_alias=AliasChoices("QDRANT_URL", "LOCAL_AGENT_QDRANT_URL"),
    )
    ollama_base_url: str = Field(
        default="http://127.0.0.1:11434",
        validation_alias=AliasChoices("OLLAMA_BASE_URL", "LOCAL_AGENT_OLLAMA_BASE_URL"),
    )

    chat_model: str = Field(
        default="qwen2.5-coder:7b",
        validation_alias=AliasChoices("OLLAMA_MODEL", "LOCAL_AGENT_CHAT_MODEL"),
    )
    embedding_model: str = Field(
        default="nomic-embed-text",
        validation_alias=AliasChoices("EMBEDDING_MODEL", "LOCAL_AGENT_EMBEDDING_MODEL"),
    )
    vector_size: int = Field(default=384, validation_alias=AliasChoices("VECTOR_SIZE", "LOCAL_AGENT_VECTOR_SIZE"))

    chunk_lines: int = Field(default=80, validation_alias=AliasChoices("CHUNK_LINES", "LOCAL_AGENT_CHUNK_LINES"))
    chunk_overlap_lines: int = Field(
        default=20,
        validation_alias=AliasChoices("CHUNK_OVERLAP_LINES", "LOCAL_AGENT_CHUNK_OVERLAP_LINES"),
    )
    max_file_bytes: int = Field(default=1_000_000, validation_alias=AliasChoices("MAX_FILE_BYTES", "LOCAL_AGENT_MAX_FILE_BYTES"))
    top_k: int = Field(default=10, validation_alias=AliasChoices("RAG_TOP_K", "LOCAL_AGENT_TOP_K"))


settings = Settings()
settings.agent_home.mkdir(parents=True, exist_ok=True)
(settings.agent_home / "policies").mkdir(parents=True, exist_ok=True)
