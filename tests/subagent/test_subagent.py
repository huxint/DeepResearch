"""subagent 的验收测试。

对应 docs/spec/modules/subagent.md：LLM 调用、pydantic 校验、错误上下文重试、预算扣减。
"""

from dataclasses import dataclass, field

import pytest
from pydantic import BaseModel

from deep_research.cross_cutting.budget import BudgetPool, Usage
from deep_research.cross_cutting.errors import BudgetExhausted, ValidationFailed
from deep_research.provider_pool import LLMRequest, LLMResponse
from deep_research.subagent import Subagent


class _Answer(BaseModel):
    answer: str


def _new_requests() -> list[LLMRequest]:
    return []


@dataclass(slots=True)
class _FakeProvider:
    responses: list[LLMResponse]
    requests: list[LLMRequest] = field(default_factory=_new_requests)

    async def call(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return self.responses.pop(0)


def _response(text: str, cost_usd: float = 0.01) -> LLMResponse:
    return LLMResponse(
        text=text,
        usage=Usage(input_tokens=3, output_tokens=5, cost_usd=cost_usd),
        provider="test",
        key_id="key-a",
        status_code=200,
    )


@pytest.mark.asyncio
async def test_schema_validation_failure_retries_with_error_context() -> None:
    provider = _FakeProvider(
        responses=[
            _response('{"not_answer": "bad"}'),
            _response('{"answer": "ok"}'),
        ]
    )
    budget = BudgetPool(limit_usd=1.0)
    subagent = Subagent(provider=provider, budget=budget, default_model="gpt-test", max_retries=1)

    result = await subagent.run("Return JSON.", schema=_Answer)

    assert result == _Answer(answer="ok")
    assert len(provider.requests) == 2
    retry_prompt = provider.requests[1].messages[0]["content"]
    assert "Validation error" in retry_prompt
    assert '{"not_answer": "bad"}' in retry_prompt
    assert abs(budget.spent_usd - 0.02) <= 1e-9


@pytest.mark.asyncio
async def test_always_invalid_output_raises_after_retry_limit() -> None:
    provider = _FakeProvider(
        responses=[
            _response('{"not_answer": "bad"}'),
            _response('{"still_bad": "bad"}'),
        ]
    )
    subagent = Subagent(
        provider=provider,
        budget=BudgetPool(limit_usd=1.0),
        default_model="gpt-test",
        max_retries=1,
    )

    with pytest.raises(ValidationFailed):
        await subagent.run("Return JSON.", schema=_Answer)

    assert len(provider.requests) == 2


@pytest.mark.asyncio
async def test_exhausted_budget_aborts_before_provider_call() -> None:
    provider = _FakeProvider(responses=[_response('{"answer": "ok"}')])
    subagent = Subagent(
        provider=provider,
        budget=BudgetPool(limit_usd=0.0),
        default_model="gpt-test",
    )

    with pytest.raises(BudgetExhausted):
        await subagent.run("Return JSON.", schema=_Answer)

    assert provider.requests == []


@pytest.mark.asyncio
async def test_valid_schema_output_returns_validated_object() -> None:
    provider = _FakeProvider(responses=[_response('{"answer": "ok"}')])
    subagent = Subagent(
        provider=provider,
        budget=BudgetPool(limit_usd=1.0),
        default_model="gpt-test",
    )

    result = await subagent.run("Return JSON.", schema=_Answer)

    assert result == _Answer(answer="ok")
    assert provider.requests[0].model == "gpt-test"
    prompt = provider.requests[0].messages[0]["content"]
    assert "valid JSON object" in prompt
    assert "json.loads" in prompt
    assert "Escape newlines and quotes" in prompt


@pytest.mark.asyncio
async def test_schema_output_can_be_wrapped_in_json_fence() -> None:
    provider = _FakeProvider(responses=[_response('```json\n{"answer": "ok"}\n```')])
    subagent = Subagent(
        provider=provider,
        budget=BudgetPool(limit_usd=1.0),
        default_model="gpt-test",
    )

    result = await subagent.run("Return JSON.", schema=_Answer)

    assert result == _Answer(answer="ok")


@pytest.mark.asyncio
async def test_without_schema_returns_text() -> None:
    provider = _FakeProvider(responses=[_response("plain text")])
    subagent = Subagent(
        provider=provider,
        budget=BudgetPool(limit_usd=1.0),
        default_model="gpt-test",
    )

    result = await subagent.run("Return text.")

    assert result == "plain text"
