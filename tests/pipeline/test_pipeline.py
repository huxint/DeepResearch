"""pipeline 的验收测试。

对应 docs/spec/modules/pipeline.md：Plan→Search→Verify→Write、并行检索、未核验引用过滤。
"""

import asyncio
import time
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from pydantic import BaseModel

from deep_research.journal import Journal
from deep_research.kernel import Kernel
from deep_research.mcp_tools import FetchedDoc, SearchHit
from deep_research.pipeline import Plan, Report, ReportDraft, ResearchPipeline


def _new_prompts() -> list[str]:
    return []


@dataclass(slots=True)
class _PipelineSubagent:
    subquestions: list[str]
    prompts: list[str] = field(default_factory=_new_prompts)

    async def run(
        self,
        prompt: str,
        *,
        schema: type[BaseModel] | None = None,
        model: str | None = None,
        max_retries: int | None = None,
    ) -> BaseModel | str:
        self.prompts.append(prompt)
        if schema is Plan:
            return Plan(subquestions=self.subquestions)
        if schema is ReportDraft:
            return ReportDraft(body=prompt)
        return prompt


@dataclass(slots=True)
class _FakeTools:
    hits: dict[str, list[SearchHit]]
    docs: dict[str, FetchedDoc]
    search_delay_s: float = 0.0
    fetch_delay_s: float = 0.0

    async def search(self, query: str) -> list[SearchHit]:
        if self.search_delay_s > 0:
            await asyncio.sleep(self.search_delay_s)
        return self.hits[query]

    async def fetch(self, url: str) -> FetchedDoc:
        if self.fetch_delay_s > 0:
            await asyncio.sleep(self.fetch_delay_s)
        return self.docs[url]


def _kernel(tmp_path: Path, subagent: _PipelineSubagent) -> Kernel:
    return Kernel(
        subagent=subagent,
        journal=Journal(tmp_path / "journal.sqlite3"),
        max_concurrency=8,
    )


def _hit(query: str, url: str, snippet: str) -> SearchHit:
    return SearchHit(title=query, url=url, snippet=snippet)


def _pipeline(tmp_path: Path, subagent: _PipelineSubagent, tools: _FakeTools) -> ResearchPipeline:
    from deep_research.verifier import Verifier

    kernel = _kernel(tmp_path, subagent)
    verifier = Verifier(kernel=kernel, tools=tools)
    return ResearchPipeline(kernel=kernel, tools=tools, verifier=verifier)


@pytest.mark.asyncio
async def test_research_returns_report_with_verified_citations(tmp_path: Path) -> None:
    subagent = _PipelineSubagent(subquestions=["ocean color"])
    url = "https://example.test/ocean"
    tools = _FakeTools(
        hits={"ocean color": [_hit("ocean color", url, "The ocean is blue")]},
        docs={url: FetchedDoc(url=url, content="The ocean is blue because of light absorption.")},
    )
    pipeline = _pipeline(tmp_path, subagent, tools)

    report = await pipeline.research("Why is the ocean blue?")

    assert isinstance(report, Report)
    assert report.question == "Why is the ocean blue?"
    assert len(report.citations) == 1
    assert report.citations[0].url == url
    assert "The ocean is blue" in report.body


@pytest.mark.asyncio
async def test_parallel_search_is_faster_than_serial_baseline(tmp_path: Path) -> None:
    subquestions = [f"topic {index}" for index in range(4)]
    subagent = _PipelineSubagent(subquestions=subquestions)
    hits = {
        subquestion: [_hit(subquestion, f"https://example.test/{index}", f"{subquestion} fact")]
        for index, subquestion in enumerate(subquestions)
    }
    docs = {
        hit.url: FetchedDoc(url=hit.url, content=hit.snippet)
        for subquestion_hits in hits.values()
        for hit in subquestion_hits
    }
    pipeline = _pipeline(
        tmp_path,
        subagent,
        _FakeTools(hits=hits, docs=docs, search_delay_s=0.03),
    )

    parallel_started = time.monotonic()
    await pipeline.search(subquestions)
    parallel_elapsed = time.monotonic() - parallel_started

    serial_started = time.monotonic()
    await pipeline.search_serial_baseline(subquestions)
    serial_elapsed = time.monotonic() - serial_started

    assert parallel_elapsed < serial_elapsed * 0.75


@pytest.mark.asyncio
async def test_unverified_citation_does_not_enter_write_or_report(tmp_path: Path) -> None:
    subagent = _PipelineSubagent(subquestions=["mixed citations"])
    good_url = "https://example.test/good"
    bad_url = "https://example.test/bad"
    tools = _FakeTools(
        hits={
            "mixed citations": [
                _hit("good", good_url, "The ocean is blue"),
                _hit("bad", bad_url, "The ocean is green"),
            ]
        },
        docs={
            good_url: FetchedDoc(url=good_url, content="The ocean is blue."),
            bad_url: FetchedDoc(url=bad_url, content="Mars is red."),
        },
    )
    pipeline = _pipeline(tmp_path, subagent, tools)

    report = await pipeline.research("What color is the ocean?")

    assert [citation.url for citation in report.citations] == [good_url]
    assert good_url in report.body
    assert bad_url not in report.body
    assert bad_url not in subagent.prompts[-1]
