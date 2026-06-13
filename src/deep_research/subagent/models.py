"""subagent 的边界数据模型。"""

from pydantic import BaseModel, Field, NonNegativeInt

from deep_research.cross_cutting.budget import Usage


class SubagentSpec(BaseModel):
    """一次子 Agent 执行规格。"""

    prompt: str
    model: str | None = None
    max_retries: NonNegativeInt = 1


class ValidationRetryContext(BaseModel):
    """注入重试 prompt 的上一次校验失败上下文。"""

    attempt: int
    error: str
    previous_output: str


class BudgetTicket(BaseModel):
    """一次调用后的预算扣减凭据。"""

    usage: Usage
    spent_usd: float
    remaining_usd: float


class ChatMessage(BaseModel):
    """传给 provider-pool 的单条 chat message。"""

    role: str
    content: str


def _new_messages() -> list[ChatMessage]:
    return []


class ChatPrompt(BaseModel):
    """provider-pool LLMRequest 的 messages 边界。"""

    messages: list[ChatMessage] = Field(default_factory=_new_messages)
