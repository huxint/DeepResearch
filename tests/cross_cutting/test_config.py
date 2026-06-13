"""配置加载的验收测试。

对应 docs/spec/03-cross-cutting.md「配置」：pydantic Settings，从环境变量加载，
启动时校验，缺失必填项属致命错误 (ConfigMissing) 并 fail-loud。
"""

import pytest

from deep_research.cross_cutting.config import Settings, load_settings
from deep_research.cross_cutting.errors import ConfigMissing


def _close(actual: float, expected: float, tol: float = 1e-9) -> bool:
    return abs(actual - expected) <= tol


def test_load_settings_reads_required_fields_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DR_BUDGET_USD", "0.18")
    monkeypatch.setenv("DR_DEFAULT_MODEL", "claude-opus-4-8")
    settings = load_settings()
    assert isinstance(settings, Settings)
    assert _close(settings.budget_usd, 0.18)
    assert settings.default_model == "claude-opus-4-8"


def test_optional_fields_have_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DR_BUDGET_USD", "0.18")
    monkeypatch.setenv("DR_DEFAULT_MODEL", "claude-opus-4-8")
    settings = load_settings()
    assert _close(settings.request_timeout_s, 30.0)
    assert settings.log_level == "INFO"


def test_missing_required_field_raises_fatal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DR_BUDGET_USD", raising=False)
    monkeypatch.delenv("DR_DEFAULT_MODEL", raising=False)
    # fail-loud：缺必填项直接致命，不静默用默认值兜底
    with pytest.raises(ConfigMissing):
        load_settings()
