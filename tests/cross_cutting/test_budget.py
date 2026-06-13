"""token 计费与共享预算池的验收测试。

对应 docs/spec/03-cross-cutting.md「token 计费」：每次调用产出 token/成本，
共享预算池累计，超限熔断（致命）。
"""

import pytest

from deep_research.cross_cutting.budget import BudgetPool, Usage
from deep_research.cross_cutting.errors import BudgetExhausted


def _close(actual: float, expected: float, tol: float = 1e-9) -> bool:
    return abs(actual - expected) <= tol


def test_usage_reports_total_tokens() -> None:
    usage = Usage(input_tokens=100, output_tokens=40, cost_usd=0.01)
    assert usage.total_tokens == 140


def test_charge_accumulates_spent_and_reduces_remaining() -> None:
    pool = BudgetPool(limit_usd=1.0)
    pool.charge(Usage(input_tokens=0, output_tokens=0, cost_usd=0.30))
    pool.charge(Usage(input_tokens=0, output_tokens=0, cost_usd=0.20))
    assert _close(pool.spent_usd, 0.50)
    assert _close(pool.remaining_usd(), 0.50)


def test_charge_up_to_the_limit_is_allowed() -> None:
    pool = BudgetPool(limit_usd=0.18)
    pool.charge(Usage(input_tokens=0, output_tokens=0, cost_usd=0.18))
    assert _close(pool.remaining_usd(), 0.0)


def test_charge_over_limit_raises_fatal_and_does_not_apply() -> None:
    pool = BudgetPool(limit_usd=0.18)
    pool.charge(Usage(input_tokens=0, output_tokens=0, cost_usd=0.10))
    with pytest.raises(BudgetExhausted):
        pool.charge(Usage(input_tokens=0, output_tokens=0, cost_usd=0.20))
    # 拒绝的扣减不应改变已花费额
    assert _close(pool.spent_usd, 0.10)


def test_would_exceed_predicts_without_charging() -> None:
    pool = BudgetPool(limit_usd=0.18)
    pool.charge(Usage(input_tokens=0, output_tokens=0, cost_usd=0.10))
    assert pool.would_exceed(0.09) is True
    assert pool.would_exceed(0.08) is False
    assert _close(pool.spent_usd, 0.10)
