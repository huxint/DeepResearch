"""provider-pool 的验收测试。

对应 docs/spec/modules/provider-pool.md：多 Provider/多 Key 调度、限流、熔断换道。
"""

import asyncio

import httpx
import pytest

from deep_research.cross_cutting.budget import Usage
from deep_research.cross_cutting.errors import NoKeysAvailable
from deep_research.provider_pool import (
    LLMRequest,
    LLMResponse,
    ProviderConfig,
    ProviderKeyConfig,
    ProviderPool,
)


def _config(*keys: ProviderKeyConfig) -> ProviderConfig:
    return ProviderConfig(
        name="openai",
        endpoint="https://api.example.test/v1/chat/completions",
        keys=list(keys),
        default_model="gpt-test",
    )


def test_provider_pool_models_are_public() -> None:
    config = ProviderConfig(
        name="openai",
        endpoint="https://api.example.test/v1/chat/completions",
        keys=[ProviderKeyConfig(key_id="key-a", api_key="secret-a", rpm=60, max_concurrency=2)],
        default_model="gpt-test",
    )
    request = LLMRequest(model="gpt-test", messages=[{"role": "user", "content": "hi"}])
    response = LLMResponse(
        text="hello",
        usage=Usage(input_tokens=1, output_tokens=1, cost_usd=0.0),
        provider="openai",
        key_id="key-a",
        status_code=200,
    )

    assert config.keys[0].weight == 1
    assert request.model == "gpt-test"
    assert response.usage.total_tokens == 2


@pytest.mark.asyncio
async def test_acquire_context_increments_and_releases_concurrency() -> None:
    pool = ProviderPool(
        [_config(ProviderKeyConfig(key_id="a", api_key="secret-a", rpm=60, max_concurrency=2))]
    )

    async with pool.acquire() as lease:
        assert lease.key_id == "a"
        assert pool.snapshot("a").in_flight == 1

    assert pool.snapshot("a").in_flight == 0


@pytest.mark.asyncio
async def test_acquire_prefers_key_with_less_current_concurrency() -> None:
    pool = ProviderPool(
        [
            _config(
                ProviderKeyConfig(key_id="a", api_key="secret-a", rpm=60, max_concurrency=2),
                ProviderKeyConfig(key_id="b", api_key="secret-b", rpm=60, max_concurrency=2),
            )
        ]
    )

    async with pool.acquire() as first:
        async with pool.acquire() as second:
            assert first.key_id == "a"
            assert second.key_id == "b"
            assert pool.snapshot("a").in_flight == 1
            assert pool.snapshot("b").in_flight == 1

        assert pool.snapshot("a").in_flight == 1
        assert pool.snapshot("b").in_flight == 0

    assert pool.snapshot("a").in_flight == 0


@pytest.mark.asyncio
async def test_equal_weight_keys_rotate() -> None:
    pool = ProviderPool(
        [
            _config(
                ProviderKeyConfig(key_id="a", api_key="secret-a", rpm=60, max_concurrency=10),
                ProviderKeyConfig(key_id="b", api_key="secret-b", rpm=60, max_concurrency=10),
            )
        ]
    )

    seen: list[str] = []
    for _ in range(4):
        async with pool.acquire() as lease:
            seen.append(lease.key_id)

    assert seen == ["a", "b", "a", "b"]


@pytest.mark.asyncio
async def test_weighted_keys_receive_weighted_turns() -> None:
    pool = ProviderPool(
        [
            _config(
                ProviderKeyConfig(
                    key_id="a",
                    api_key="secret-a",
                    rpm=60,
                    max_concurrency=10,
                    weight=2,
                ),
                ProviderKeyConfig(key_id="b", api_key="secret-b", rpm=60, max_concurrency=10),
            )
        ]
    )

    seen: list[str] = []
    for _ in range(6):
        async with pool.acquire() as lease:
            seen.append(lease.key_id)

    assert seen == ["a", "a", "b", "a", "a", "b"]


@pytest.mark.asyncio
async def test_acquire_waits_until_key_window_has_capacity() -> None:
    pool = ProviderPool(
        [_config(ProviderKeyConfig(key_id="a", api_key="secret-a", rpm=1, max_concurrency=1))],
        window_seconds=0.05,
    )

    async with pool.acquire():
        pass

    started = asyncio.Event()
    acquired = asyncio.Event()

    async def acquire_again() -> None:
        started.set()
        async with pool.acquire():
            acquired.set()

    async with asyncio.TaskGroup() as group:
        group.create_task(acquire_again())
        await started.wait()
        await asyncio.sleep(0.01)
        assert acquired.is_set() is False
        await asyncio.sleep(0.06)

    assert acquired.is_set() is True


@pytest.mark.asyncio
async def test_call_circuits_rate_limited_key_and_fails_over() -> None:
    requested_keys: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        auth = request.headers["Authorization"]
        requested_keys.append(auth)
        if auth == "Bearer secret-a":
            return httpx.Response(429, json={"error": "rate limited"})
        return httpx.Response(
            200,
            json={
                "text": "ok",
                "usage": {"input_tokens": 3, "output_tokens": 4, "cost_usd": 0.01},
            },
        )

    pool = ProviderPool(
        [
            _config(
                ProviderKeyConfig(key_id="a", api_key="secret-a", rpm=60, max_concurrency=1),
                ProviderKeyConfig(key_id="b", api_key="secret-b", rpm=60, max_concurrency=1),
            )
        ],
        circuit_seconds=0.1,
        transport=httpx.MockTransport(handler),
    )

    response = await pool.call(
        LLMRequest(model="gpt-test", messages=[{"role": "user", "content": "hi"}])
    )

    assert response.text == "ok"
    assert response.provider == "openai"
    assert response.key_id == "b"
    assert response.usage.total_tokens == 7
    assert requested_keys == ["Bearer secret-a", "Bearer secret-b"]
    assert pool.snapshot("a").is_circuited is True


@pytest.mark.asyncio
async def test_call_circuits_timed_out_key_and_fails_over() -> None:
    requested_keys: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        auth = request.headers["Authorization"]
        requested_keys.append(auth)
        if auth == "Bearer secret-a":
            raise httpx.ReadTimeout("slow", request=request)
        return httpx.Response(
            200,
            json={
                "text": "ok",
                "usage": {"input_tokens": 5, "output_tokens": 8, "cost_usd": 0.02},
            },
        )

    pool = ProviderPool(
        [
            _config(
                ProviderKeyConfig(key_id="a", api_key="secret-a", rpm=60, max_concurrency=1),
                ProviderKeyConfig(key_id="b", api_key="secret-b", rpm=60, max_concurrency=1),
            )
        ],
        circuit_seconds=0.1,
        transport=httpx.MockTransport(handler),
    )

    response = await pool.call(
        LLMRequest(model="gpt-test", messages=[{"role": "user", "content": "hi"}])
    )

    assert response.text == "ok"
    assert response.key_id == "b"
    assert response.usage.total_tokens == 13
    assert requested_keys == ["Bearer secret-a", "Bearer secret-b"]
    assert pool.snapshot("a").is_circuited is True


@pytest.mark.asyncio
async def test_call_raises_fatal_when_all_keys_are_unavailable() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate limited"})

    pool = ProviderPool(
        [
            _config(
                ProviderKeyConfig(key_id="a", api_key="secret-a", rpm=60, max_concurrency=1),
                ProviderKeyConfig(key_id="b", api_key="secret-b", rpm=60, max_concurrency=1),
            )
        ],
        circuit_seconds=0.1,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(NoKeysAvailable):
        await pool.call(LLMRequest(model="gpt-test", messages=[{"role": "user", "content": "hi"}]))
