from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _detect_root_dir() -> Path:
    """Resolve project root for local (`…/backend/src/…`) and Docker (`/app/src/…`)."""
    here = Path(__file__).resolve()
    local_root = here.parents[4]  # <repo>/backend/src/deepsupport_os/core → <repo>
    docker_root = here.parents[3]  # /app/src/deepsupport_os/core → /app
    # Local checkout: repo has backend/ + skills/ (or compose)
    if (local_root / "backend").is_dir() and (
        (local_root / "skills").is_dir() or (local_root / "docker-compose.yml").is_file()
    ):
        return local_root
    if (docker_root / "src" / "deepsupport_os").is_dir() and (
        docker_root / "pyproject.toml"
    ).is_file():
        return docker_root
    return local_root


ROOT_DIR = _detect_root_dir()


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

    # Cap single completion length (does not stop tool loops by itself).
    llm_max_tokens: int = 2048
    # LangGraph agent step cap (hard-stops infinite recursion).
    agent_recursion_limit: int = 40
    # Main-agent tool-call budget per turn (subagents use their own middleware).
    agent_max_tool_calls: int = 24

    # RAGLab HTTP client (do not copy RAGLab source / local model paths)
    raglab_base_url: str = "http://127.0.0.1:8001"
    # Logical KB name on shared RAGLab instance (must match RAGLab KbName)
    raglab_kb: str = "deepsupport"
    # Shown in UI when RAGLab is down (e.g. slim 2G VPS without local models).
    raglab_unavailable_hint: str = ""

    # Mock enterprise DB
    database_url: str = "sqlite:///data/deepsupport.db"

    # Agent workspace (filesystem context / offloading; local fallback)
    workspace_dir: str = "workspace"

    # HTTP bind — default loopback for local demo; Docker sets API_HOST=0.0.0.0
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    # When set, mutating /api/meta/* and /admin/seed require header X-Admin-Token
    admin_token: str = ""
    # Shared demo passphrase for conversation APIs. Empty = open (local).
    # Cookie is httponly HMAC, not the plaintext passphrase.
    demo_access_token: str = ""
    demo_cookie_path: str = "/"

    # Daytona: keep as lightweight sidecar (local Skills/workspace are primary)
    daytona_enabled: bool = True
    daytona_api_key: str = ""
    daytona_sandbox_name: str = "deepsupport-sandbox"
    daytona_api_url: str = "https://app.daytona.io/api"
    daytona_target: str = ""
    # sidecar = local primary + /sandbox/ route (recommended on 1vCPU/1GiB)
    # off = local only; full = entire FS on Daytona (slow, not recommended)
    daytona_mode: str = "sidecar"
    # Sandbox writable isolation (AR-07 / R2-4):
    #   local  = /sandbox/ → workspace/{tid}/sandbox/ (default, no cross-thread share)
    #   off    = no /sandbox/ route
    #   shared = legacy single Daytona sandbox (explicit opt-in)
    #   thread = one Daytona sandbox name per thread_id (cloud cost)
    daytona_sandbox_scope: str = "local"

    # Skills: multi-source progressive disclosure
    skills_imported_enabled: bool = True

    # MCP: in-process mock tools + optional remote MultiServerMCPClient
    mcp_local_tools: bool = True
    mcp_remote_enabled: bool = False
    mcp_servers_config: str = "config/mcp_servers.json"

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Rate limiting
    rate_limit_per_minute: int = 60

    # Session management
    session_timeout_minutes: int = 30

    # Performance monitoring
    enable_metrics: bool = True

    # Rate limiting
    rate_limit_per_minute: int = 60

    # Session management
    session_timeout_minutes: int = 30

    # Performance monitoring
    enable_metrics: bool = True

    # Rate limiting
    rate_limit_per_minute: int = 60

    # Session management
    session_timeout_minutes: int = 30

    # Performance monitoring
    enable_metrics: bool = True

    # Rate limiting
    rate_limit_per_minute: int = 60

    # Session management
    session_timeout_minutes: int = 30

    # Debug mode
    debug: bool = False

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
