from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/src/deepsupport_os/core/config.py → repo root
ROOT_DIR = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    project_name: str = "DeepSupport OS"
    root_dir: Path = Field(default_factory=lambda: ROOT_DIR)

    # LLM (OpenAI-compatible; default DeepSeek)
    llm_provider: str = "deepseek"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    ollama_base_url: str = "http://127.0.0.1:11434/v1"
    ollama_model: str = "qwen3:4b"
    ollama_api_key: str = "ollama"

    # RAGLab HTTP client (do not copy RAGLab code — call its API)
    raglab_base_url: str = "http://127.0.0.1:8001"
    raglab_root: str = r"D:\2026AppDev\RAGLab"
    # Local models live under RAGLab; we only reference paths
    embedding_model_path: str = r"D:\2026AppDev\RAGLab\models\bge-small-zh-v1.5"
    reranker_model_path: str = r"D:\2026AppDev\RAGLab\models\bge-reranker-v2-m3"

    # Mock enterprise DB
    database_url: str = "sqlite:///data/deepsupport.db"

    # Agent workspace (filesystem context / offloading; local fallback)
    workspace_dir: str = "workspace"

    # Daytona: keep as lightweight sidecar (local Skills/workspace are primary)
    daytona_enabled: bool = True
    daytona_api_key: str = ""
    daytona_sandbox_name: str = "deepsupport-sandbox"
    daytona_api_url: str = "https://app.daytona.io/api"
    daytona_target: str = ""
    # sidecar = local primary + /sandbox/ route (recommended on 1vCPU/1GiB)
    # off = local only; full = entire FS on Daytona (slow, not recommended)
    daytona_mode: str = "sidecar"

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    def resolve(self, path: str | Path) -> Path:
        p = Path(path)
        if p.is_absolute():
            return p
        return (self.root_dir / p).resolve()

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def llm_credentials(self) -> tuple[str, str, str]:
        if self.llm_provider == "ollama":
            return (
                self.ollama_api_key or "ollama",
                self.ollama_base_url.rstrip("/"),
                self.ollama_model,
            )
        return (
            self.deepseek_api_key,
            self.deepseek_base_url.rstrip("/"),
            self.deepseek_model,
        )

    @property
    def llm_configured(self) -> bool:
        if self.llm_provider == "ollama":
            return bool(self.ollama_base_url and self.ollama_model)
        return bool(self.deepseek_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
