"""错误分类 (error taxonomy) 的验收测试。

对应 docs/spec/03-cross-cutting.md「错误分类」：可重试 (Retryable) 与致命 (Fatal)
两支，弹性接缝据此做模式匹配。
"""

from deep_research.cross_cutting.errors import (
    BudgetExhausted,
    ConfigMissing,
    DeepResearchError,
    Fatal,
    NoKeysAvailable,
    RateLimited,
    Retryable,
    Timeout,
    ValidationFailed,
)


def test_retryable_and_fatal_share_a_common_base() -> None:
    assert issubclass(Retryable, DeepResearchError)
    assert issubclass(Fatal, DeepResearchError)


def test_retryable_and_fatal_are_distinct() -> None:
    assert not issubclass(Retryable, Fatal)
    assert not issubclass(Fatal, Retryable)


def test_retryable_errors_match_as_retryable() -> None:
    for exc in (RateLimited("429"), Timeout("slow"), ValidationFailed("bad schema")):
        assert isinstance(exc, Retryable)
        assert not isinstance(exc, Fatal)


def test_fatal_errors_match_as_fatal() -> None:
    for exc in (ConfigMissing("no key"), NoKeysAvailable("pool empty"), BudgetExhausted("over")):
        assert isinstance(exc, Fatal)
        assert not isinstance(exc, Retryable)


def test_seam_can_pattern_match_on_category() -> None:
    """弹性接缝可只凭 Retryable/Fatal 决定重试还是上抛。"""

    def classify(exc: DeepResearchError) -> str:
        match exc:
            case Retryable():
                return "retry"
            case Fatal():
                return "abort"
            case _:
                return "unknown"

    assert classify(Timeout("x")) == "retry"
    assert classify(BudgetExhausted("x")) == "abort"
