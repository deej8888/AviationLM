from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AEROLM_", env_file=".env", extra="ignore")
    backend: Literal["rules", "hf"] = "rules"
    model_id: str = "Qwen/Qwen3-0.6B"
    model_revision: str = "main"
    adapter_path: str | None = None
    device: Literal["cpu", "cuda", "auto"] = "cpu"
    precision: Literal["auto", "float32", "bfloat16", "float16"] = "auto"
    cpu_threads: int | None = Field(default=None, ge=1, le=256)
    evidence_policy: Literal["warn", "reject"] = "warn"
    few_shot_path: str | None = None
    structured_output: bool = False
    cors_origins: list[str] = ["http://localhost:3000"]
    api_key: str = ""
    max_input_tokens: int = Field(default=4096, ge=512, le=32768)
    max_new_tokens: int = Field(default=1024, ge=128, le=4096)
