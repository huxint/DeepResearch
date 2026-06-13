"""Workflow 编排内核。"""

import asyncio
import os
import time
from collections.abc import Sequence
from typing import Protocol, overload

from pydantic import BaseModel, TypeAdapter

from deep_research.journal import JsonValue, make_journal_hash, prompt_fingerprint
from deep_research.kernel.models import Stage, Thunk

_JSON_VALUE: TypeAdapter[JsonValue] = TypeAdapter(JsonValue)


class SubagentRunner(Protocol):
    """kernel 依赖的 subagent 最小边界。"""

    async def run(
        self,
        prompt: str,
        *,
        schema: type[BaseModel] | None = None,
        model: str | None = None,
        max_retries: int | None = None,
    ) -> BaseModel | str:
        """执行一次子 Agent。"""
        ...


class JournalStore(Protocol):
    """kernel 依赖的 journal 最小边界。"""

    def lookup(self, hash: str) -> JsonValue | None:
        """按 hash 查缓存。"""
        ...

    def append(
        self,
        hash: str,
        result: JsonValue,
        *,
        prompt_fingerprint: str = "",
        params: dict[str, JsonValue] | None = None,
    ) -> None:
        """追加一次缓存记录。"""
        ...


def default_concurrency_limit() -> int:
    """agent 并发上限：min(16, cpu-2)，至少保留 1 个槽避免低核机器死锁。"""

    cpu_count = os.cpu_count()
    if cpu_count is None:
        return 1
    return max(1, min(16, cpu_count - 2))


class Kernel:
    """提供 agent / pipeline / parallel 三个确定性编排原语。"""

    def __init__(
        self,
        *,
        subagent: SubagentRunner,
        journal: JournalStore,
        max_concurrency: int | None = None,
    ) -> None:
        self._subagent = subagent
        self._journal = journal
        self._agent_slots = asyncio.Semaphore(
            default_concurrency_limit() if max_concurrency is None else max_concurrency
        )

    @overload
    async def agent[T: BaseModel](
        self,
        prompt: str,
        *,
        schema: type[T],
        model: str | None = None,
    ) -> T: ...

    @overload
    async def agent(
        self,
        prompt: str,
        *,
        schema: None = None,
        model: str | None = None,
    ) -> str: ...

    async def agent(
        self,
        prompt: str,
        *,
        schema: type[BaseModel] | None = None,
        model: str | None = None,
    ) -> BaseModel | str:
        params = self._agent_cache_params(schema=schema, model=model)
        entry_hash = make_journal_hash(prompt=prompt, params=params)
        cached = self._journal.lookup(entry_hash)
        if cached is not None:
            return self._from_cache(cached, schema=schema)

        async with self._agent_slots:
            result = await self._subagent.run(prompt, schema=schema, model=model)

        self._journal.append(
            entry_hash,
            self._to_json_value(result),
            prompt_fingerprint=prompt_fingerprint(prompt),
            params=params,
        )
        return result

    async def pipeline(self, items: Sequence[object], *stages: Stage) -> list[object | None]:
        results: list[object | None] = [None] * len(items)

        async def run_item(index: int, item: object) -> None:
            current = item
            try:
                for stage in stages:
                    current = await stage(current)
                results[index] = current
            except Exception:
                results[index] = None

        async with asyncio.TaskGroup() as group:
            for index, item in enumerate(items):
                group.create_task(run_item(index, item))

        return results

    async def parallel[T](self, thunks: Sequence[Thunk[T]]) -> list[T | None]:
        results: list[T | None] = [None] * len(thunks)

        async def run_one(index: int, thunk: Thunk[T]) -> None:
            try:
                results[index] = await thunk()
            except Exception:
                results[index] = None

        async with asyncio.TaskGroup() as group:
            for index, thunk in enumerate(thunks):
                group.create_task(run_one(index, thunk))

        return results

    def _agent_cache_params(
        self,
        *,
        schema: type[BaseModel] | None,
        model: str | None,
    ) -> dict[str, JsonValue]:
        schema_name = None if schema is None else f"{schema.__module__}.{schema.__qualname__}"
        return {"schema": schema_name, "model": model}

    def _from_cache(
        self,
        cached: JsonValue,
        *,
        schema: type[BaseModel] | None,
    ) -> BaseModel | str:
        if schema is not None:
            return schema.model_validate(cached)
        if isinstance(cached, str):
            return cached
        raise TypeError("文本 agent 缓存必须是字符串")

    def _to_json_value(self, result: BaseModel | str) -> JsonValue:
        if isinstance(result, str):
            return result
        return _JSON_VALUE.validate_python(result.model_dump(mode="json"))


def monotonic_elapsed_s(start: float) -> float:
    """计算耗时，保留给后续日志/AgentResult 元数据使用。"""

    return time.monotonic() - start
