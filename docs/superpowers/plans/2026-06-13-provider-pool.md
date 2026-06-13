# Provider Pool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `provider-pool` module so one LLM call can be scheduled across multiple providers and keys with per-key concurrency, weighted selection, sliding-window RPM limits, and retry-on-429/timeout failover.

**Architecture:** Create a focused `deep_research.provider_pool` package. `models.py` owns pydantic boundary models, `pool.py` owns scheduling/state/retry behavior, and `__init__.py` exports the public API. Tests drive behavior through a small async fake transport so no network or real API keys are needed.

**Tech Stack:** Python 3.14, asyncio, httpx, pydantic, pytest, pyright strict, ruff.

---

## File Structure

- Create `src/deep_research/provider_pool/models.py`: `ProviderConfig`, `ProviderKeyConfig`, `LLMRequest`, `LLMResponse`, and `KeySnapshot`.
- Create `src/deep_research/provider_pool/pool.py`: `ProviderPool`, internal `KeyState`, weighted scheduler, sliding-window limiter, retry/failover seam, and HTTP request execution.
- Create `src/deep_research/provider_pool/__init__.py`: public exports.
- Create `tests/provider_pool/test_pool.py`: acceptance tests for §5 invariants and §8 behavior.
- Modify `docs/guide/01-build-order.md`: mark `provider-pool` cells complete after T1 gate passes.

## Acceptance Mapping

- 429 failover and circuit exclusion: `tests/provider_pool/test_pool.py::test_call_circuits_rate_limited_key_and_fails_over`.
- Concurrent acquire/release accounting: `test_acquire_context_increments_and_releases_concurrency`.
- Sliding-window RPM blocking per key: `test_acquire_waits_until_key_window_has_capacity`.
- Least-concurrency weighted distribution: `test_equal_weight_keys_rotate` and `test_weighted_keys_receive_weighted_turns`.

### Task 1: Public Models

**Files:**
- Create: `tests/provider_pool/test_pool.py`
- Create: `src/deep_research/provider_pool/models.py`
- Create: `src/deep_research/provider_pool/__init__.py`

- [ ] **Step 1: Write the failing model import test**

```python
from deep_research.provider_pool import (
    LLMRequest,
    LLMResponse,
    ProviderConfig,
    ProviderKeyConfig,
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
        usage={"input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0},
        provider="openai",
        key_id="key-a",
        status_code=200,
    )

    assert config.keys[0].weight == 1
    assert request.model == "gpt-test"
    assert response.usage.total_tokens == 2
```

- [ ] **Step 2: Run the test to verify RED**

Run: `uv run pytest tests/provider_pool/test_pool.py::test_provider_pool_models_are_public -q`
Expected: FAIL because `deep_research.provider_pool` does not exist.

- [ ] **Step 3: Implement minimal pydantic models**

Create `ProviderKeyConfig` with `key_id: str`, `api_key: str`, `rpm: int`, `max_concurrency: int`, `weight: int = 1`.
Create `ProviderConfig` with `name: str`, `endpoint: str`, `keys: list[ProviderKeyConfig]`, `default_model: str`, `headers: dict[str, str] = {}`.
Create `LLMRequest` with `model: str`, `messages: list[dict[str, str]]`, `temperature: float | None = None`, `max_tokens: int | None = None`.
Create `LLMResponse` with `text: str`, `usage: Usage`, `provider: str`, `key_id: str`, `status_code: int`.
Create `KeySnapshot` with `provider: str`, `key_id: str`, `in_flight: int`, `is_circuited: bool`.
Export all public names from `__init__.py`.

- [ ] **Step 4: Run the test to verify GREEN**

Run: `uv run pytest tests/provider_pool/test_pool.py::test_provider_pool_models_are_public -q`
Expected: PASS.

### Task 2: Acquire Scheduling And Release Accounting

**Files:**
- Modify: `tests/provider_pool/test_pool.py`
- Create: `src/deep_research/provider_pool/pool.py`
- Modify: `src/deep_research/provider_pool/__init__.py`

- [ ] **Step 1: Write the failing acquire accounting test**

```python
import asyncio

import pytest

from deep_research.provider_pool import ProviderConfig, ProviderKeyConfig, ProviderPool


def _config(*keys: ProviderKeyConfig) -> ProviderConfig:
    return ProviderConfig(
        name="openai",
        endpoint="https://api.example.test/v1/chat/completions",
        keys=list(keys),
        default_model="gpt-test",
    )


@pytest.mark.asyncio
async def test_acquire_context_increments_and_releases_concurrency() -> None:
    pool = ProviderPool(
        [_config(ProviderKeyConfig(key_id="a", api_key="secret-a", rpm=60, max_concurrency=2))]
    )

    async with pool.acquire() as lease:
        assert lease.key_id == "a"
        assert pool.snapshot("a").in_flight == 1

    assert pool.snapshot("a").in_flight == 0
```

- [ ] **Step 2: Run the test to verify RED**

Run: `uv run pytest tests/provider_pool/test_pool.py::test_acquire_context_increments_and_releases_concurrency -q`
Expected: FAIL because `ProviderPool` does not exist.

- [ ] **Step 3: Implement `ProviderPool.acquire` as an async context manager**

Create internal `KeyState` from each configured key. `acquire()` waits until a key has capacity, selects the eligible key with lowest `in_flight`, increments `in_flight`, records a call timestamp, and releases in `finally`. `snapshot(key_id)` returns `KeySnapshot`.

- [ ] **Step 4: Run the test to verify GREEN**

Run: `uv run pytest tests/provider_pool/test_pool.py::test_acquire_context_increments_and_releases_concurrency -q`
Expected: PASS.

### Task 3: Weighted Least-Concurrency Selection

**Files:**
- Modify: `tests/provider_pool/test_pool.py`
- Modify: `src/deep_research/provider_pool/pool.py`

- [ ] **Step 1: Write failing distribution tests**

```python
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
                ProviderKeyConfig(key_id="a", api_key="secret-a", rpm=60, max_concurrency=10, weight=2),
                ProviderKeyConfig(key_id="b", api_key="secret-b", rpm=60, max_concurrency=10, weight=1),
            )
        ]
    )

    seen: list[str] = []
    for _ in range(6):
        async with pool.acquire() as lease:
            seen.append(lease.key_id)

    assert seen == ["a", "a", "b", "a", "a", "b"]
```

- [ ] **Step 2: Run the tests to verify RED**

Run: `uv run pytest tests/provider_pool/test_pool.py::test_equal_weight_keys_rotate tests/provider_pool/test_pool.py::test_weighted_keys_receive_weighted_turns -q`
Expected: at least one FAIL because initial selection always picks the first key.

- [ ] **Step 3: Implement weighted round-robin among equal `in_flight` keys**

Maintain a per-pool rotation sequence expanded by positive key weight, e.g. `["a", "a", "b"]`. Filter candidates by the minimum `in_flight`, then choose the next rotation entry present in that candidate set.

- [ ] **Step 4: Run the tests to verify GREEN**

Run: `uv run pytest tests/provider_pool/test_pool.py::test_equal_weight_keys_rotate tests/provider_pool/test_pool.py::test_weighted_keys_receive_weighted_turns -q`
Expected: PASS.

### Task 4: Sliding-Window RPM Limiting

**Files:**
- Modify: `tests/provider_pool/test_pool.py`
- Modify: `src/deep_research/provider_pool/pool.py`

- [ ] **Step 1: Write the failing sliding-window test**

```python
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
```

- [ ] **Step 2: Run the test to verify RED**

Run: `uv run pytest tests/provider_pool/test_pool.py::test_acquire_waits_until_key_window_has_capacity -q`
Expected: FAIL because second acquire does not wait.

- [ ] **Step 3: Enforce per-key sliding window**

Store monotonic timestamps on each key. Before selection, prune timestamps older than `window_seconds`; a key is eligible only if `len(window_calls) < rpm`. If no key is eligible, wait until the earliest blocked key leaves its window.

- [ ] **Step 4: Run the test to verify GREEN**

Run: `uv run pytest tests/provider_pool/test_pool.py::test_acquire_waits_until_key_window_has_capacity -q`
Expected: PASS.

### Task 5: Call Failover, Circuit Breaker, And Response Parsing

**Files:**
- Modify: `tests/provider_pool/test_pool.py`
- Modify: `src/deep_research/provider_pool/pool.py`

- [ ] **Step 1: Write the failing 429 failover test**

```python
import httpx

from deep_research.cross_cutting.errors import NoKeysAvailable


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

    response = await pool.call(LLMRequest(model="gpt-test", messages=[{"role": "user", "content": "hi"}]))

    assert response.text == "ok"
    assert response.provider == "openai"
    assert response.key_id == "b"
    assert requested_keys == ["Bearer secret-a", "Bearer secret-b"]
    assert pool.snapshot("a").is_circuited is True
```

- [ ] **Step 2: Run the test to verify RED**

Run: `uv run pytest tests/provider_pool/test_pool.py::test_call_circuits_rate_limited_key_and_fails_over -q`
Expected: FAIL because `call` and circuiting are not implemented.

- [ ] **Step 3: Implement provider seam retry/failover**

In `call`, acquire a key, POST the pydantic request payload to the provider endpoint with `Authorization: Bearer <api_key>`, timeout via `httpx.Timeout`, parse JSON `text` and `usage`, and return `LLMResponse`. On HTTP 429 or `httpx.TimeoutException`, circuit that key until `now + circuit_seconds`, release it, sleep exponential backoff, and retry on another key. If all keys are unavailable, raise `NoKeysAvailable`.

- [ ] **Step 4: Run the test to verify GREEN**

Run: `uv run pytest tests/provider_pool/test_pool.py::test_call_circuits_rate_limited_key_and_fails_over -q`
Expected: PASS.

### Task 6: Verification And Status Table

**Files:**
- Modify: `docs/guide/01-build-order.md`

- [ ] **Step 1: Run provider-pool acceptance tests**

Run: `uv run pytest tests/provider_pool -q`
Expected: all provider-pool tests pass.

- [ ] **Step 2: Run T1 quality gate**

Run:

```bash
uv run pyright --strict
uv run pytest
uv run ruff check .
uv run ruff format --check .
rg -n "try:|except " src/deep_research tests
```

Expected: pyright, pytest, ruff check, and ruff format all exit 0. `rg` may find only allowed resilience-seam `try/except` instances; each hit must be reviewed against `docs/guide/02-coding-conventions.md`.

- [ ] **Step 3: Mark provider-pool complete**

Change the `provider-pool` row in `docs/guide/01-build-order.md` to `✓ | ✓ | ✓ | ✓ | ✓`.

- [ ] **Step 4: Commit**

Run:

```bash
git add docs/guide/01-build-order.md docs/superpowers/plans/2026-06-13-provider-pool.md src/deep_research/provider_pool tests/provider_pool
git commit -m "feat: implement provider pool"
```
