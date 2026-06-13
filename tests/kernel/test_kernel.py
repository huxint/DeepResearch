"""kernel 的验收测试。

对应 docs/spec/modules/kernel.md：agent/journal 缓存、无屏障 pipeline、parallel 降级、
agent 并发上限。
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path

import pytest
from pydantic import BaseModel

from deep_research.cross_cutting.budget import Usage
from deep_research.journal import Journal
from deep_research.kernel import Kernel


@dataclass(slots=True)
class _FakeSubagent:
    response_text: str = "ok"
    delay_s: float = 0.0
    calls: int = 0
    active: int = 0
    max_active: int = 0

    async def run(
        self,
        prompt: str,
        *,
        schema: type[BaseModel] | None = None,
        model: str | None = None,
        max_retries: int | None = None,
    ) -> BaseModel | str:
        self.calls += 1
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        if self.delay_s > 0:
            await asyncio.sleep(self.delay_s)
        self.active -= 1
        if schema is None:
            return f"{self.response_text}:{prompt}"
        return schema.model_validate_json(self.response_text)


def _kernel(
    tmp_path: Path,
    subagent: _FakeSubagent | None = None,
    max_concurrency: int = 4,
) -> Kernel:
    return Kernel(
        subagent=_FakeSubagent() if subagent is None else subagent,
        journal=Journal(tmp_path / "journal.sqlite3"),
        max_concurrency=max_concurrency,
    )


@pytest.mark.asyncio
async def test_pipeline_has_no_stage_barrier(tmp_path: Path) -> None:
    kernel = _kernel(tmp_path)
    events: list[str] = []
    slow_stage1_started = asyncio.Event()
    fast_stage2_started = asyncio.Event()

    async def stage1(item: object) -> object:
        if item == "slow":
            events.append("slow:stage1:start")
            slow_stage1_started.set()
            await fast_stage2_started.wait()
            events.append("slow:stage1:end")
            return item

        await slow_stage1_started.wait()
        events.append("fast:stage1")
        return item

    async def stage2(item: object) -> object:
        events.append(f"{item}:stage2")
        if item == "fast":
            fast_stage2_started.set()
        return f"{item}:done"

    async with asyncio.timeout(0.2):
        results = await kernel.pipeline(["slow", "fast"], stage1, stage2)

    assert results == ["slow:done", "fast:done"]
    assert events.index("fast:stage2") < events.index("slow:stage1:end")


@pytest.mark.asyncio
async def test_parallel_item_failure_becomes_none(tmp_path: Path) -> None:
    kernel = _kernel(tmp_path)

    async def first() -> int:
        return 1

    async def broken() -> int:
        raise RuntimeError("boom")

    async def third() -> int:
        return 3

    results = await kernel.parallel([first, broken, third])

    assert results == [1, None, 3]


@pytest.mark.asyncio
async def test_agent_concurrency_limit_queues_excess_calls(tmp_path: Path) -> None:
    subagent = _FakeSubagent(delay_s=0.02)
    kernel = _kernel(tmp_path, subagent=subagent, max_concurrency=2)
    prompts = [f"prompt-{index}" for index in range(6)]
    results: list[str | None] = [None] * len(prompts)

    async def run_one(index: int, prompt: str) -> None:
        results[index] = await kernel.agent(prompt)

    async with asyncio.TaskGroup() as group:
        for index, prompt in enumerate(prompts):
            group.create_task(run_one(index, prompt))

    assert results == [f"ok:{prompt}" for prompt in prompts]
    assert subagent.calls == len(prompts)
    assert subagent.max_active == 2


@pytest.mark.asyncio
async def test_agent_hits_journal_before_subagent_call(tmp_path: Path) -> None:
    subagent = _FakeSubagent()
    kernel = _kernel(tmp_path, subagent=subagent)

    first = await kernel.agent("cached prompt")
    second = await kernel.agent("cached prompt")

    assert first == "ok:cached prompt"
    assert second == first
    assert subagent.calls == 1


def test_agent_result_model_carries_metadata() -> None:
    from deep_research.kernel import AgentResult

    result = AgentResult(
        value="ok",
        from_cache=True,
        elapsed_s=0.01,
        usage=Usage(input_tokens=1, output_tokens=2, cost_usd=0.001),
    )

    assert result.from_cache is True
    assert result.usage is not None
    assert result.usage.total_tokens == 3
