"""子 Agent 执行单元。"""

from typing import Protocol, overload

from pydantic import BaseModel, ValidationError

from deep_research.cross_cutting.budget import BudgetPool
from deep_research.cross_cutting.errors import BudgetExhausted, ValidationFailed
from deep_research.provider_pool import LLMRequest, LLMResponse
from deep_research.subagent.models import (
    BudgetTicket,
    ChatMessage,
    ChatPrompt,
    ValidationRetryContext,
)


class LLMProvider(Protocol):
    """subagent 依赖的 provider-pool 最小边界。"""

    async def call(self, request: LLMRequest) -> LLMResponse:
        """发起一次 LLM 调用。"""
        ...


class Subagent:
    """执行一次 prompt → provider 调用 → schema 校验 → 预算扣减。"""

    def __init__(
        self,
        *,
        provider: LLMProvider,
        budget: BudgetPool,
        default_model: str,
        max_retries: int = 1,
    ) -> None:
        self._provider = provider
        self._budget = budget
        self._default_model = default_model
        self._max_retries = max_retries
        self._last_budget_ticket: BudgetTicket | None = None

    @property
    def last_budget_ticket(self) -> BudgetTicket | None:
        return self._last_budget_ticket

    @overload
    async def run[T: BaseModel](
        self,
        prompt: str,
        *,
        schema: type[T],
        model: str | None = None,
        max_retries: int | None = None,
    ) -> T: ...

    @overload
    async def run(
        self,
        prompt: str,
        *,
        schema: None = None,
        model: str | None = None,
        max_retries: int | None = None,
    ) -> str: ...

    async def run(
        self,
        prompt: str,
        *,
        schema: type[BaseModel] | None = None,
        model: str | None = None,
        max_retries: int | None = None,
    ) -> BaseModel | str:
        retry_limit = self._max_retries if max_retries is None else max_retries
        current_prompt = prompt
        selected_model = self._default_model if model is None else model

        for attempt in range(retry_limit + 1):
            self._ensure_budget_available()
            response = await self._provider.call(
                LLMRequest(
                    model=selected_model,
                    messages=self._messages_for(current_prompt),
                )
            )
            self._charge(response)

            if schema is None:
                return response.text

            try:
                return schema.model_validate_json(response.text)
            except ValidationError as exc:
                if attempt == retry_limit:
                    raise ValidationFailed(f"子 Agent 输出校验失败：{exc}") from exc
                current_prompt = self._retry_prompt(
                    original_prompt=prompt,
                    context=ValidationRetryContext(
                        attempt=attempt + 1,
                        error=str(exc),
                        previous_output=response.text,
                    ),
                )

        raise ValidationFailed("子 Agent 输出校验失败")

    def _ensure_budget_available(self) -> None:
        if self._budget.remaining_usd() <= 0.0:
            raise BudgetExhausted("预算已耗尽，拒绝发起新的子 Agent 调用")

    def _charge(self, response: LLMResponse) -> None:
        self._budget.charge(response.usage)
        self._last_budget_ticket = BudgetTicket(
            usage=response.usage,
            spent_usd=self._budget.spent_usd,
            remaining_usd=self._budget.remaining_usd(),
        )

    def _messages_for(self, prompt: str) -> list[dict[str, str]]:
        chat_prompt = ChatPrompt(messages=[ChatMessage(role="user", content=prompt)])
        return [message.model_dump() for message in chat_prompt.messages]

    def _retry_prompt(self, *, original_prompt: str, context: ValidationRetryContext) -> str:
        return (
            f"{original_prompt}\n\n"
            "Previous response failed pydantic schema validation.\n"
            f"Retry attempt: {context.attempt}\n"
            "Validation error:\n"
            f"{context.error}\n\n"
            "Previous response:\n"
            f"{context.previous_output}\n\n"
            "Return only a corrected response that matches the requested schema."
        )
