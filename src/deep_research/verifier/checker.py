"""引用溯源多视角核验。"""

import re
from collections.abc import Awaitable, Callable, Sequence
from typing import Protocol

from deep_research.kernel import Thunk
from deep_research.mcp_tools import FetchedDoc
from deep_research.verifier.models import (
    Citation,
    PerspectiveVerdict,
    Verdict,
    VerificationSummary,
)

type Perspective = Callable[[Citation, FetchedDoc], Awaitable[PerspectiveVerdict]]


class ParallelKernel(Protocol):
    """verifier 依赖的 kernel.parallel 最小边界。"""

    async def parallel[T](self, thunks: Sequence[Thunk[T]]) -> list[T | None]:
        """并发执行 thunks，单项失败降级为 None。"""
        ...


class FetchTools(Protocol):
    """verifier 依赖的 mcp-tools 最小边界。"""

    async def fetch(self, url: str) -> FetchedDoc:
        """抓取引用来源正文。"""
        ...


class Verifier:
    """对引用执行多视角溯源核验。"""

    def __init__(
        self,
        *,
        kernel: ParallelKernel,
        tools: FetchTools,
        perspectives: Sequence[Perspective] | None = None,
    ) -> None:
        self._kernel = kernel
        self._tools = tools
        self._perspectives = (
            [source_reachable, snippet_present, claim_terms_present]
            if perspectives is None
            else list(perspectives)
        )

    async def verify(self, citation: Citation) -> Verdict:
        doc = await self._tools.fetch(citation.url)
        thunks = [self._thunk_for(perspective, citation, doc) for perspective in self._perspectives]
        results = await self._kernel.parallel(thunks)
        return aggregate_verdict(citation=citation, results=results, total_perspectives=len(thunks))

    async def verify_all(self, citations: Sequence[Citation]) -> VerificationSummary:
        thunks = [self._verify_thunk(citation) for citation in citations]
        results = await self._kernel.parallel(thunks)
        verdicts = [verdict for verdict in results if verdict is not None]
        citation_errors = sum(verdict.citation_error for verdict in verdicts)
        return VerificationSummary(
            verdicts=verdicts,
            total=len(citations),
            citation_errors=citation_errors,
        )

    def _thunk_for(
        self,
        perspective: Perspective,
        citation: Citation,
        doc: FetchedDoc,
    ) -> Thunk[PerspectiveVerdict]:
        async def run() -> PerspectiveVerdict:
            return await perspective(citation, doc)

        return run

    def _verify_thunk(self, citation: Citation) -> Thunk[Verdict]:
        async def run() -> Verdict:
            return await self.verify(citation)

        return run


async def source_reachable(citation: Citation, doc: FetchedDoc) -> PerspectiveVerdict:
    supports = bool(doc.content.strip())
    return PerspectiveVerdict(
        perspective="source_reachable",
        supports=supports,
        confidence=1.0 if supports else 0.0,
        reason=f"{citation.url} returned non-empty content" if supports else "source was empty",
    )


async def snippet_present(citation: Citation, doc: FetchedDoc) -> PerspectiveVerdict:
    normalized_snippet = _normalize(citation.snippet)
    normalized_doc = _normalize(doc.content)
    supports = bool(normalized_snippet) and normalized_snippet in normalized_doc
    return PerspectiveVerdict(
        perspective="snippet_present",
        supports=supports,
        confidence=0.9 if supports else 0.1,
        reason="citation snippet appears in source" if supports else "citation snippet missing",
    )


async def claim_terms_present(citation: Citation, doc: FetchedDoc) -> PerspectiveVerdict:
    claim_terms = _terms(citation.claim)
    doc_terms = _terms(doc.content)
    overlap = claim_terms & doc_terms
    supports = bool(claim_terms) and len(overlap) >= max(1, len(claim_terms) // 2)
    confidence = len(overlap) / len(claim_terms) if claim_terms else 0.0
    return PerspectiveVerdict(
        perspective="claim_terms_present",
        supports=supports,
        confidence=confidence,
        reason=f"{len(overlap)}/{len(claim_terms)} claim terms found in source",
    )


def aggregate_verdict(
    *,
    citation: Citation,
    results: Sequence[PerspectiveVerdict | None],
    total_perspectives: int,
) -> Verdict:
    perspectives = [result for result in results if result is not None]
    failed_perspectives = total_perspectives - len(perspectives)
    unsupported_votes = sum(not verdict.supports for verdict in perspectives)
    supported_votes = sum(verdict.supports for verdict in perspectives)
    citation_error = unsupported_votes > supported_votes
    supported = supported_votes > 0 and not citation_error
    confidence_denominator = len(perspectives) if perspectives else 1
    confidence = (
        supported_votes / confidence_denominator
        if supported
        else unsupported_votes / confidence_denominator
    )
    return Verdict(
        citation=citation,
        supported=supported,
        citation_error=citation_error,
        confidence=confidence,
        perspectives=perspectives,
        failed_perspectives=failed_perspectives,
    )


def _normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def _terms(text: str) -> set[str]:
    return {
        match.group(0)
        for match in re.finditer(r"[a-z0-9]+", text.casefold())
        if len(match.group(0)) >= 4
    }
