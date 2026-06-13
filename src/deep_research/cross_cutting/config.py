"""配置加载。

从环境变量（前缀 ``DR_``）与可选 ``.env`` 加载并经 pydantic 校验。缺失必填项是
**致命错误**：``load_settings`` 在 config 接缝把 pydantic 的 ``ValidationError`` 翻译成
``ConfigMissing`` 并 fail-loud，不静默用默认值兜底。

Provider/Key 的精确配置形态归 [[provider-pool]] 拥有（见 modules/provider-pool.md §4），
本处聚合启动所需配置并在进程入口一次性校验。
"""

from pydantic import BaseModel, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from deep_research.cross_cutting.errors import ConfigMissing
from deep_research.provider_pool import ProviderConfig


def _new_args() -> list[str]:
    return []


class MCPStdioServerConfig(BaseModel):
    """MCP stdio server 启动配置。"""

    command: str
    args: list[str] = Field(default_factory=_new_args)
    env: dict[str, str] | None = None
    cwd: str | None = None


class Settings(BaseSettings):
    """全局运行配置。"""

    model_config = SettingsConfigDict(env_prefix="DR_", env_file=".env", extra="ignore")

    budget_usd: float
    default_model: str
    providers: list[ProviderConfig] = Field(min_length=1)
    mcp_server: MCPStdioServerConfig | None = None
    journal_path: str = ".deep_research/journal.sqlite3"
    request_timeout_s: float = 30.0
    log_level: str = "INFO"


def load_settings() -> Settings:
    """加载并校验配置；缺失必填项 → ``ConfigMissing``（致命）。"""
    try:
        return Settings()  # pyright: ignore[reportCallIssue]  # 字段由环境变量注入
    except ValidationError as exc:
        raise ConfigMissing(f"配置校验失败：{exc}") from exc
