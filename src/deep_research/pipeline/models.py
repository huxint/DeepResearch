"""pipeline 的边界数据模型。"""

from pydantic import BaseModel, Field

from deep_research.mcp_tools import FetchedDoc, SearchHit
from deep_research.verifier import Citation


def _new_subquestions() -> list[str]:
    return []


def _new_hits() -> list[SearchHit]:
    return []


def _new_docs() -> list[FetchedDoc]:
    return []


def _new_citations() -> list[Citation]:
    return []


def _new_verified_claims() -> list[VerifiedClaim]:
    return []


class Plan(BaseModel):
    """Plan 阶段输出：确定性子问题列表。"""

    subquestions: list[str] = Field(default_factory=_new_subquestions)


class SearchResult(BaseModel):
    """单个子问题的 Search 阶段结果。"""

    subquestion: str
    hits: list[SearchHit] = Field(default_factory=_new_hits)
    fetched_docs: list[FetchedDoc] = Field(default_factory=_new_docs)
    citations: list[Citation] = Field(default_factory=_new_citations)


class VerifiedClaim(BaseModel):
    """已通过引用核验的论断。"""

    claim: str
    citation: Citation
    confidence: float


class ReportDraft(BaseModel):
    """Write 阶段模型输出。"""

    body: str


class Report(BaseModel):
    """最终带引用报告。"""

    question: str
    body: str
    citations: list[Citation] = Field(default_factory=_new_citations)
    verified_claims: list[VerifiedClaim] = Field(default_factory=_new_verified_claims)
