"""T2/T3 质量门的系统级可执行检查。"""

import asyncio
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import pytest
from pydantic import BaseModel

from deep_research.cross_cutting.budget import BudgetPool, Usage
from deep_research.cross_cutting.errors import BudgetExhausted
from deep_research.eval import DeterministicJudge, EvalCase, EvalRunner
from deep_research.journal import Journal
from deep_research.kernel import Kernel
from deep_research.mcp_tools import FetchedDoc, SearchHit
from deep_research.pipeline import Plan, Report, ReportDraft, ResearchPipeline
from deep_research.provider_pool import LLMRequest, ProviderConfig, ProviderKeyConfig, ProviderPool
from deep_research.verifier import Verifier


def _new_prompts() -> list[str]:
    return []


@dataclass(slots=True)
class _ScriptedSubagent:
    subquestions: list[str]
    calls: int = 0
    prompts: list[str] = field(default_factory=_new_prompts)

    async def run(
        self,
        prompt: str,
        *,
        schema: type[BaseModel] | None = None,
        model: str | None = None,
        max_retries: int | None = None,
    ) -> BaseModel | str:
        self.calls += 1
        self.prompts.append(prompt)
        if schema is Plan:
            return Plan(subquestions=self.subquestions)
        if schema is ReportDraft:
            return ReportDraft(body=prompt)
        return prompt


@dataclass(slots=True)
class _GateTools:
    hits: dict[str, list[SearchHit]]
    docs: dict[str, FetchedDoc]
    search_delay_s: float = 0.0

    async def search(self, query: str) -> list[SearchHit]:
        if self.search_delay_s > 0:
            await asyncio.sleep(self.search_delay_s)
        return self.hits[query]

    async def fetch(self, url: str) -> FetchedDoc:
        return self.docs[url]


def _hit(query: str, url: str, snippet: str) -> SearchHit:
    return SearchHit(title=query, url=url, snippet=snippet)


def _research_pipeline(
    tmp_path: Path,
    subagent: _ScriptedSubagent,
    tools: _GateTools,
) -> ResearchPipeline:
    kernel = Kernel(
        subagent=subagent,
        journal=Journal(tmp_path / "journal.sqlite3"),
        max_concurrency=8,
    )
    verifier = Verifier(kernel=kernel, tools=tools)
    return ResearchPipeline(kernel=kernel, tools=tools, verifier=verifier)


@pytest.mark.asyncio
async def test_t2_tracer_bullet_end_to_end_report_with_citation(tmp_path: Path) -> None:
    url = "https://example.test/ocean"
    pipeline = _research_pipeline(
        tmp_path,
        _ScriptedSubagent(subquestions=["ocean color"]),
        _GateTools(
            hits={"ocean color": [_hit("ocean color", url, "The ocean is blue")]},
            docs={url: FetchedDoc(url=url, content="The ocean is blue.")},
        ),
    )

    report = await pipeline.research("Why is the ocean blue?")

    assert isinstance(report, Report)
    assert report.citations[0].url == url
    assert "The ocean is blue" in report.body


@pytest.mark.asyncio
async def test_t2_journal_resume_hits_cache_without_subagent_rerun(tmp_path: Path) -> None:
    db_path = tmp_path / "journal.sqlite3"
    first_subagent = _ScriptedSubagent(subquestions=[])
    first_journal = Journal(db_path)
    first_kernel = Kernel(subagent=first_subagent, journal=first_journal, max_concurrency=2)
    first = await first_kernel.agent("cached call")
    first_journal.close()

    resumed_subagent = _ScriptedSubagent(subquestions=[])
    resumed_journal = Journal(db_path)
    resumed_kernel = Kernel(subagent=resumed_subagent, journal=resumed_journal, max_concurrency=2)
    resumed = await resumed_kernel.agent("cached call")
    resumed_journal.close()

    assert resumed == first
    assert first_subagent.calls == 1
    assert resumed_subagent.calls == 0


@pytest.mark.asyncio
async def test_t2_provider_pool_resilience_fails_over_after_429() -> None:
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
                "usage": {"input_tokens": 1, "output_tokens": 1, "cost_usd": 0.001},
            },
        )

    pool = ProviderPool(
        [
            ProviderConfig(
                name="openai",
                endpoint="https://api.example.test/v1/chat/completions",
                keys=[
                    ProviderKeyConfig(
                        key_id="a",
                        api_key="secret-a",
                        rpm=60,
                        max_concurrency=1,
                    ),
                    ProviderKeyConfig(
                        key_id="b",
                        api_key="secret-b",
                        rpm=60,
                        max_concurrency=1,
                    ),
                ],
                default_model="gpt-test",
            )
        ],
        transport=httpx.MockTransport(handler),
        circuit_seconds=0.1,
    )

    response = await pool.call(
        LLMRequest(model="gpt-test", messages=[{"role": "user", "content": "hi"}])
    )

    assert response.key_id == "b"
    assert requested_keys == ["Bearer secret-a", "Bearer secret-b"]


@pytest.mark.asyncio
async def test_t3_citation_gate_filters_unsupported_sources(tmp_path: Path) -> None:
    good_url = "https://example.test/good"
    bad_url = "https://example.test/bad"
    subagent = _ScriptedSubagent(subquestions=["mixed"])
    pipeline = _research_pipeline(
        tmp_path,
        subagent,
        _GateTools(
            hits={
                "mixed": [
                    _hit("good", good_url, "The ocean is blue"),
                    _hit("bad", bad_url, "The ocean is green"),
                ]
            },
            docs={
                good_url: FetchedDoc(url=good_url, content="The ocean is blue."),
                bad_url: FetchedDoc(url=bad_url, content="Mars is red."),
            },
        ),
    )

    report = await pipeline.research("What color is the ocean?")

    assert [citation.url for citation in report.citations] == [good_url]
    assert bad_url not in report.body
    assert bad_url not in subagent.prompts[-1]


@pytest.mark.asyncio
async def test_t3_eval_gate_runs_text_subset_and_regression_is_stable(tmp_path: Path) -> None:
    url = "https://example.test/ocean"
    pipeline = _research_pipeline(
        tmp_path,
        _ScriptedSubagent(subquestions=["ocean color"]),
        _GateTools(
            hits={"ocean color": [_hit("ocean color", url, "The ocean is blue")]},
            docs={url: FetchedDoc(url=url, content="The ocean is blue.")},
        ),
    )
    runner = EvalRunner(pipeline=pipeline, judge=DeterministicJudge())
    dataset = [EvalCase(case_id="gaia-text-1", question="Ocean color?", gold_answer="blue")]

    first = await runner.run_eval(dataset)
    second = await runner.run_eval(dataset)

    assert first.correct == 1
    assert second.correct == 1
    assert first.model_dump() == second.model_dump()


def test_t3_cost_gate_budget_pool_fuses_when_limit_is_exceeded() -> None:
    budget = BudgetPool(limit_usd=0.05)
    budget.charge(Usage(input_tokens=1, output_tokens=1, cost_usd=0.05))

    with pytest.raises(BudgetExhausted):
        budget.charge(Usage(input_tokens=1, output_tokens=1, cost_usd=0.001))


@pytest.mark.asyncio
async def test_t3_latency_gate_parallel_search_beats_serial_baseline(tmp_path: Path) -> None:
    subquestions = [f"topic {index}" for index in range(5)]
    hits = {
        subquestion: [_hit(subquestion, f"https://example.test/{index}", f"{subquestion} fact")]
        for index, subquestion in enumerate(subquestions)
    }
    docs = {
        hit.url: FetchedDoc(url=hit.url, content=hit.snippet)
        for subquestion_hits in hits.values()
        for hit in subquestion_hits
    }
    pipeline = _research_pipeline(
        tmp_path,
        _ScriptedSubagent(subquestions=subquestions),
        _GateTools(hits=hits, docs=docs, search_delay_s=0.02),
    )

    parallel_started = time.monotonic()
    await pipeline.search(subquestions)
    parallel_elapsed = time.monotonic() - parallel_started

    serial_started = time.monotonic()
    await pipeline.search_serial_baseline(subquestions)
    serial_elapsed = time.monotonic() - serial_started

    assert parallel_elapsed < serial_elapsed * 0.75
