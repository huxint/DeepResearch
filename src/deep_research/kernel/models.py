"""kernel 的边界数据模型与类型别名。"""

from collections.abc import Awaitable, Callable

from pydantic import BaseModel

from deep_research.cross_cutting.budget import Usage
from deep_research.journal import JsonValue

type Stage = Callable[[object], Awaitable[object]]
type Thunk[T] = Callable[[], Awaitable[T]]


class AgentResult(BaseModel):
    """一次 agent 调用的产物与元数据。"""

    value: JsonValue
    from_cache: bool
    elapsed_s: float
    usage: Usage | None = None


class OrchestrationContext(BaseModel):
    """编排上下文。"""

    max_concurrency: int
    phase: str | None = None
