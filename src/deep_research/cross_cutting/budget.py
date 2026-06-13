"""token 计费与共享预算池。

每次 provider 调用产出一个 ``Usage``（token 数 + 估算成本）；``BudgetPool`` 累计成本，
超过上限即拒绝扣减并抛 ``BudgetExhausted``（致命）。这是成本治理（单题 ≤ \\$0.18 目标）的硬闸门。

预算池在 asyncio 单线程事件循环内使用，扣减为同步原子操作（中途不 await），无需加锁。
"""

from pydantic import BaseModel

from deep_research.cross_cutting.errors import BudgetExhausted

# 浮点成本比较容差（亚分级精度），避免 0.1+0.08 之类的二进制误差误判超限。
_EPS = 1e-9


class Usage(BaseModel):
    """一次调用的 token 消耗与估算成本。"""

    input_tokens: int
    output_tokens: int
    cost_usd: float

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class BudgetPool:
    """共享成本预算池：累计扣减，超限熔断。"""

    def __init__(self, limit_usd: float) -> None:
        self._limit_usd = limit_usd
        self._spent_usd = 0.0

    @property
    def spent_usd(self) -> float:
        return self._spent_usd

    def remaining_usd(self) -> float:
        return self._limit_usd - self._spent_usd

    def would_exceed(self, cost_usd: float) -> bool:
        """预判扣减 ``cost_usd`` 是否会超限，不改变状态。"""
        return self._spent_usd + cost_usd > self._limit_usd + _EPS

    def charge(self, usage: Usage) -> None:
        """扣减一次用量；若会超限则抛 ``BudgetExhausted`` 且不改变已花费额。"""
        if self.would_exceed(usage.cost_usd):
            raise BudgetExhausted(
                f"预算超限：已花费 {self._spent_usd:.4f}，"
                f"本次 {usage.cost_usd:.4f}，上限 {self._limit_usd:.4f} (USD)"
            )
        self._spent_usd += usage.cost_usd
