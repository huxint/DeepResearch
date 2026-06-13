"""verifier 的验收测试。

对应 docs/spec/modules/verifier.md：引用溯源、多视角扇出、引用错误统计。
"""

from dataclasses import dataclass
from pathlib import Path

import pytest

from deep_research.journal import Journal
from deep_research.kernel import Kernel
from deep_research.mcp_tools import FetchedDoc
from deep_research.verifier import Citation, PerspectiveVerdict, Verdict, Verifier


@dataclass(slots=True)
class _FakeTools:
    docs: dict[str, FetchedDoc]
    fetch_calls: list[str]

    async def fetch(self, url: str) -> FetchedDoc:
        self.fetch_calls.append(url)
        return self.docs[url]


@dataclass(slots=True)
class _DummySubagent:
    async def run(self, prompt: str, **kwargs: object) -> str:
        return prompt


def _kernel(tmp_path: Path) -> Kernel:
    return Kernel(
        subagent=_DummySubagent(),
        journal=Journal(tmp_path / "journal.sqlite3"),
        max_concurrency=4,
    )


def _tools(*docs: FetchedDoc) -> _FakeTools:
    return _FakeTools(docs={doc.url: doc for doc in docs}, fetch_calls=[])


@pytest.mark.asyncio
async def test_fake_unsupported_citation_is_marked_as_citation_error(tmp_path: Path) -> None:
    url = "https://example.test/source"
    verifier = Verifier(
        kernel=_kernel(tmp_path),
        tools=_tools(FetchedDoc(url=url, content="Mars is red and dry.")),
    )
    citation = Citation(
        claim="The ocean is green.",
        url=url,
        snippet="The ocean is green.",
    )

    verdict = await verifier.verify(citation)

    assert verdict.supported is False
    assert verdict.citation_error is True
    assert sum(not perspective.supports for perspective in verdict.perspectives) >= 2


@pytest.mark.asyncio
async def test_supported_citation_passes(tmp_path: Path) -> None:
    url = "https://example.test/source"
    content = "The ocean is blue because water absorbs longer wavelengths of light."
    verifier = Verifier(
        kernel=_kernel(tmp_path),
        tools=_tools(FetchedDoc(url=url, content=content)),
    )
    citation = Citation(
        claim="The ocean is blue.",
        url=url,
        snippet="The ocean is blue",
    )

    verdict = await verifier.verify(citation)

    assert verdict.supported is True
    assert verdict.citation_error is False


@pytest.mark.asyncio
async def test_verify_all_reports_unsupported_citation_count(tmp_path: Path) -> None:
    good_url = "https://example.test/good"
    bad_url = "https://example.test/bad"
    verifier = Verifier(
        kernel=_kernel(tmp_path),
        tools=_tools(
            FetchedDoc(url=good_url, content="The ocean is blue."),
            FetchedDoc(url=bad_url, content="Mars is red."),
        ),
    )

    summary = await verifier.verify_all(
        [
            Citation(claim="The ocean is blue.", url=good_url, snippet="The ocean is blue"),
            Citation(claim="The ocean is green.", url=bad_url, snippet="The ocean is green"),
        ]
    )

    assert summary.total == 2
    assert summary.citation_errors == 1
    assert [verdict.citation_error for verdict in summary.verdicts] == [False, True]


@pytest.mark.asyncio
async def test_single_perspective_failure_does_not_block_aggregation(tmp_path: Path) -> None:
    url = "https://example.test/source"

    async def support(citation: Citation, doc: FetchedDoc) -> PerspectiveVerdict:
        return PerspectiveVerdict(
            perspective="support",
            supports=True,
            confidence=0.9,
            reason=f"{citation.url} supports claim in {doc.url}",
        )

    async def fail(citation: Citation, doc: FetchedDoc) -> PerspectiveVerdict:
        raise RuntimeError(f"failed on {citation.url} and {doc.url}")

    verifier = Verifier(
        kernel=_kernel(tmp_path),
        tools=_tools(FetchedDoc(url=url, content="The ocean is blue.")),
        perspectives=[support, fail, support],
    )

    verdict = await verifier.verify(Citation(claim="The ocean is blue.", url=url, snippet="x"))

    assert verdict.supported is True
    assert verdict.failed_perspectives == 1
    assert len(verdict.perspectives) == 2


def test_verdict_model_is_public() -> None:
    citation = Citation(claim="Claim", url="https://example.test", snippet="Claim")
    verdict = Verdict(
        citation=citation,
        supported=True,
        citation_error=False,
        confidence=1.0,
        perspectives=[],
        failed_perspectives=0,
    )

    assert verdict.citation == citation
