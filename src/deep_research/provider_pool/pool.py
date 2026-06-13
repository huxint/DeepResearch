"""多 Provider/多 Key 调度池。"""

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from types import TracebackType

import httpx
from pydantic import BaseModel, Field

from deep_research.cross_cutting.budget import Usage
from deep_research.cross_cutting.errors import NoKeysAvailable, RateLimited, Timeout
from deep_research.provider_pool.models import (
    KeySnapshot,
    LLMRequest,
    LLMResponse,
    ProviderConfig,
    ProviderKeyConfig,
)


@dataclass(slots=True)
class KeyLease:
    """一次 acquire 得到的 Key 租约。"""

    provider: str
    key_id: str


def _new_window() -> deque[float]:
    return deque()


@dataclass(slots=True)
class _KeyState:
    provider: ProviderConfig
    config: ProviderKeyConfig
    in_flight: int = 0
    window_calls: deque[float] = field(default_factory=_new_window)
    circuit_until: float = 0.0


class _ProviderWireResponse(BaseModel):
    text: str
    usage: Usage


class _OpenAIUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0


class _OpenAIMessage(BaseModel):
    content: str


class _OpenAIChoice(BaseModel):
    message: _OpenAIMessage


class _OpenAIChatCompletion(BaseModel):
    choices: list[_OpenAIChoice] = Field(min_length=1)
    usage: _OpenAIUsage


class _AcquireContext:
    def __init__(self, pool: ProviderPool) -> None:
        self._pool = pool
        self._state: _KeyState | None = None

    async def __aenter__(self) -> KeyLease:
        state = await self._pool.acquire_state()
        self._state = state
        return KeyLease(provider=state.provider.name, key_id=state.config.key_id)

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._state is not None:
            await self._pool.release_state(self._state)


class ProviderPool:
    """按最少并发优先 + 加权轮询调度 Provider Key。"""

    def __init__(
        self,
        providers: list[ProviderConfig],
        *,
        window_seconds: float = 60.0,
        circuit_seconds: float = 30.0,
        request_timeout_s: float = 30.0,
        backoff_base_s: float = 0.001,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._window_seconds = window_seconds
        self._circuit_seconds = circuit_seconds
        self._backoff_base_s = backoff_base_s
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(request_timeout_s),
            transport=transport,
        )
        self._condition = asyncio.Condition()
        self._states: list[_KeyState] = []
        self._state_by_key_id: dict[str, _KeyState] = {}
        self._rotation: list[str] = []
        self._rotation_index = 0

        for provider in providers:
            for key in provider.keys:
                if key.key_id in self._state_by_key_id:
                    raise ValueError(f"重复 key_id：{key.key_id}")
                state = _KeyState(provider=provider, config=key)
                self._states.append(state)
                self._state_by_key_id[key.key_id] = state
                self._rotation.extend([key.key_id] * key.weight)

        if not self._states:
            raise NoKeysAvailable("provider-pool 没有配置任何 Key")

    def acquire(self) -> _AcquireContext:
        """获取一个当前可用 Key，并在 async context 退出时释放并发计数。"""
        return _AcquireContext(self)

    async def call(self, request: LLMRequest) -> LLMResponse:
        """发起一次 LLM 调用；429/超时在本弹性接缝内熔断换道。"""
        for attempt in range(len(self._states)):
            try:
                return await self._call_once(request)
            except RateLimited, Timeout:
                if attempt < len(self._states) - 1:
                    await asyncio.sleep(self._backoff_seconds(attempt))

        raise NoKeysAvailable("所有 Key 均不可用")

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> ProviderPool:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    def snapshot(self, key_id: str) -> KeySnapshot:
        state = self._state_by_key_id[key_id]
        now = self._now()
        return KeySnapshot(
            provider=state.provider.name,
            key_id=state.config.key_id,
            in_flight=state.in_flight,
            is_circuited=state.circuit_until > now,
        )

    async def acquire_state(self) -> _KeyState:
        async with self._condition:
            while True:
                now = self._now()
                candidates = self._eligible_by_circuit(now)
                if not candidates:
                    raise NoKeysAvailable("所有 Key 均处于熔断状态")

                with_concurrency = [
                    state for state in candidates if state.in_flight < state.config.max_concurrency
                ]
                if not with_concurrency:
                    await self._condition.wait()
                    continue

                with_window = [
                    state
                    for state in with_concurrency
                    if self._has_window_capacity(state=state, now=now)
                ]
                if not with_window:
                    await asyncio.sleep(self._window_wait_seconds(states=with_concurrency, now=now))
                    continue

                selected = self._select_weighted(with_window)
                selected.in_flight += 1
                selected.window_calls.append(now)
                return selected

    async def release_state(self, state: _KeyState) -> None:
        async with self._condition:
            state.in_flight -= 1
            self._condition.notify_all()

    async def _call_once(self, request: LLMRequest) -> LLMResponse:
        async with self.acquire() as lease:
            state = self._state_by_key_id[lease.key_id]
            try:
                response = await self._client.post(
                    state.provider.endpoint,
                    headers=self._headers_for(state),
                    json=request.model_dump(exclude_none=True),
                )
            except httpx.TimeoutException as exc:
                await self._circuit(state)
                raise Timeout(
                    f"provider 调用超时：{state.provider.name}/{state.config.key_id}"
                ) from exc

            if response.status_code == 429:
                await self._circuit(state)
                raise RateLimited(f"provider 限流：{state.provider.name}/{state.config.key_id}")

            response.raise_for_status()
            return self._parse_response(
                payload=response.json(),
                state=state,
                status_code=response.status_code,
            )

    async def _circuit(self, state: _KeyState) -> None:
        async with self._condition:
            state.circuit_until = self._now() + self._circuit_seconds
            self._condition.notify_all()

    def _headers_for(self, state: _KeyState) -> dict[str, str]:
        headers = state.provider.headers.copy()
        headers["Authorization"] = f"Bearer {state.config.api_key}"
        return headers

    def _parse_response(
        self,
        *,
        payload: object,
        state: _KeyState,
        status_code: int,
    ) -> LLMResponse:
        if state.provider.response_format == "openai_chat":
            chat = _OpenAIChatCompletion.model_validate(payload)
            usage = Usage(
                input_tokens=chat.usage.prompt_tokens,
                output_tokens=chat.usage.completion_tokens,
                cost_usd=self._openai_chat_cost_usd(state=state, usage=chat.usage),
            )
            return LLMResponse(
                text=chat.choices[0].message.content,
                usage=usage,
                provider=state.provider.name,
                key_id=state.config.key_id,
                status_code=status_code,
            )

        wire_response = _ProviderWireResponse.model_validate(payload)
        return LLMResponse(
            text=wire_response.text,
            usage=wire_response.usage,
            provider=state.provider.name,
            key_id=state.config.key_id,
            status_code=status_code,
        )

    def _openai_chat_cost_usd(self, *, state: _KeyState, usage: _OpenAIUsage) -> float:
        input_cost = usage.prompt_tokens * state.provider.input_usd_per_1m / 1_000_000
        output_cost = usage.completion_tokens * state.provider.output_usd_per_1m / 1_000_000
        return input_cost + output_cost

    def _backoff_seconds(self, attempt: int) -> float:
        return self._backoff_base_s * (2**attempt)

    def _eligible_by_circuit(self, now: float) -> list[_KeyState]:
        return [state for state in self._states if state.circuit_until <= now]

    def _has_window_capacity(self, *, state: _KeyState, now: float) -> bool:
        self._prune_window(state=state, now=now)
        return len(state.window_calls) < state.config.rpm

    def _window_wait_seconds(self, *, states: list[_KeyState], now: float) -> float:
        next_times: list[float] = []
        for state in states:
            self._prune_window(state=state, now=now)
            if state.window_calls:
                next_times.append(state.window_calls[0] + self._window_seconds)
        return max(0.0, min(next_times) - now)

    def _prune_window(self, *, state: _KeyState, now: float) -> None:
        oldest_allowed = now - self._window_seconds
        while state.window_calls and state.window_calls[0] <= oldest_allowed:
            state.window_calls.popleft()

    def _select_weighted(self, candidates: list[_KeyState]) -> _KeyState:
        min_in_flight = min(state.in_flight for state in candidates)
        least_busy = {
            state.config.key_id for state in candidates if state.in_flight == min_in_flight
        }

        for offset in range(len(self._rotation)):
            index = (self._rotation_index + offset) % len(self._rotation)
            key_id = self._rotation[index]
            if key_id in least_busy:
                self._rotation_index = index + 1
                return self._state_by_key_id[key_id]

        raise NoKeysAvailable("没有可调度 Key")

    @classmethod
    def _now(cls) -> float:
        return time.monotonic()
