"""配置加载的验收测试。

对应 docs/spec/03-cross-cutting.md「配置」：pydantic Settings，从环境变量加载，
启动时校验，缺失必填项属致命错误 (ConfigMissing) 并 fail-loud。
"""

import pytest

from deep_research.cross_cutting.config import MCPStdioServerConfig, Settings, load_settings
from deep_research.cross_cutting.errors import ConfigMissing

_PROVIDERS_JSON = """
[
  {
    "name": "openai",
    "endpoint": "https://api.openai.test/v1/chat/completions",
    "default_model": "gpt-test",
    "response_format": "openai_chat",
    "input_usd_per_1m": 1.0,
    "output_usd_per_1m": 2.0,
    "keys": [
      {
        "key_id": "main",
        "api_key": "secret",
        "rpm": 60,
        "max_concurrency": 2
      }
    ]
  }
]
"""

_MCP_SERVER_JSON = """
{
  "command": "uvx",
  "args": ["search-server"],
  "env": {"TOKEN": "secret"}
}
"""


def _set_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DR_BUDGET_USD", "0.18")
    monkeypatch.setenv("DR_DEFAULT_MODEL", "gpt-test")
    monkeypatch.setenv("DR_PROVIDERS", _PROVIDERS_JSON)


def _close(actual: float, expected: float, tol: float = 1e-9) -> bool:
    return abs(actual - expected) <= tol


def test_load_settings_reads_required_fields_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    settings = load_settings()
    assert isinstance(settings, Settings)
    assert _close(settings.budget_usd, 0.18)
    assert settings.default_model == "gpt-test"
    assert settings.providers[0].response_format == "openai_chat"
    assert settings.providers[0].keys[0].key_id == "main"


def test_optional_fields_have_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    settings = load_settings()
    assert _close(settings.request_timeout_s, 30.0)
    assert settings.log_level == "INFO"
    assert settings.journal_path == ".deep_research/journal.sqlite3"
    assert settings.mcp_server is None


def test_mcp_server_config_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv("DR_MCP_SERVER", _MCP_SERVER_JSON)

    settings = load_settings()

    assert settings.mcp_server == MCPStdioServerConfig(
        command="uvx",
        args=["search-server"],
        env={"TOKEN": "secret"},
    )


def test_missing_required_field_raises_fatal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DR_BUDGET_USD", raising=False)
    monkeypatch.delenv("DR_DEFAULT_MODEL", raising=False)
    monkeypatch.delenv("DR_PROVIDERS", raising=False)
    # fail-loud：缺必填项直接致命，不静默用默认值兜底
    with pytest.raises(ConfigMissing):
        load_settings()
