"""Plan→Search→Verify→Write 主流程。"""

from collections.abc import Sequence
from typing import Protocol

from deep_research.kernel import Kernel, Thunk
from deep_research.mcp_tools import FetchedDoc, SearchHit
from deep_research.pipeline.models import Plan, Report, ReportDraft, SearchResult, VerifiedClaim
from deep_research.verifier import Citation, VerificationSummary


class SearchTools(Protocol):
    """pipeline 依赖的 mcp-tools 最小边界。"""

    async def search(self, query: str) -> list[SearchHit]:
        """检索一个子问题。"""
        ...

    async def fetch(self, url: str) -> FetchedDoc:
        """抓取一个 URL。"""
        ...


class CitationVerifier(Protocol):
    """pipeline 依赖的 verifier 最小边界。"""

    async def verify_all(self, citations: Sequence[Citation]) -> VerificationSummary:
        """批量核验引用。"""
        ...


class ResearchPipeline:
    """研究主流程脚本。"""

    def __init__(
        self,
        *,
        kernel: Kernel,
        tools: SearchTools,
        verifier: CitationVerifier,
    ) -> None:
        self._kernel = kernel
        self._tools = tools
        self._verifier = verifier

    async def research(self, question: str) -> Report:
        plan = await self._kernel.agent(self._plan_prompt(question), schema=Plan)
        search_results = await self.search(plan.subquestions)
        citations = [citation for result in search_results for citation in result.citations]
        verification = await self._verifier.verify_all(citations)
        verified_claims = [
            VerifiedClaim(
                claim=verdict.citation.claim,
                citation=verdict.citation,
                confidence=verdict.confidence,
            )
            for verdict in verification.verdicts
            if verdict.supported and not verdict.citation_error
        ]
        draft = await self._kernel.agent(
            self._write_prompt(question=question, verified_claims=verified_claims),
            schema=ReportDraft,
        )
        return Report(
            question=question,
            body=draft.body,
            citations=[claim.citation for claim in verified_claims],
            verified_claims=verified_claims,
        )

    async def search(self, subquestions: Sequence[str]) -> list[SearchResult]:
        results = await self._kernel.pipeline(list(subquestions), self._search_stage)
        return [result for result in results if isinstance(result, SearchResult)]

    async def search_serial_baseline(self, subquestions: Sequence[str]) -> list[SearchResult]:
        results: list[SearchResult] = []
        for subquestion in subquestions:
            results.append(await self._search_subquestion(subquestion))
        return results

    async def _search_stage(self, item: object) -> object:
        if not isinstance(item, str):
            raise TypeError("Search stage expects subquestion strings")
        return await self._search_subquestion(item)

    async def _search_subquestion(self, subquestion: str) -> SearchResult:
        hits = await self._tools.search(subquestion)
        fetched_docs = await self._fetch_hits(hits)
        citations = [Citation(claim=hit.snippet, url=hit.url, snippet=hit.snippet) for hit in hits]
        return SearchResult(
            subquestion=subquestion,
            hits=hits,
            fetched_docs=fetched_docs,
            citations=citations,
        )

    async def _fetch_hits(self, hits: Sequence[SearchHit]) -> list[FetchedDoc]:
        results = await self._kernel.parallel([self._fetch_thunk(hit) for hit in hits])
        return [doc for doc in results if doc is not None]

    def _fetch_thunk(self, hit: SearchHit) -> Thunk[FetchedDoc]:
        async def run() -> FetchedDoc:
            return await self._tools.fetch(hit.url)

        return run

    def _plan_prompt(self, question: str) -> str:
        return (
            "Break the research question into focused search subquestions. "
            "Return JSON matching the Plan schema.\n"
            f"Question: {question}"
        )

    def _write_prompt(self, *, question: str, verified_claims: Sequence[VerifiedClaim]) -> str:
        claim_lines = "\n".join(
            f"- {claim.claim} [{claim.citation.url}]" for claim in verified_claims
        )
        return (
            "Write a concise research report using only the verified claims below. "
            "Do not introduce citations that are not listed.\n"
            f"Question: {question}\n"
            "Verified claims:\n"
            f"{claim_lines}"
        )
