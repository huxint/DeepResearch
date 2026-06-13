"""verifier 的边界数据模型。"""

from pydantic import BaseModel, Field


class Citation(BaseModel):
    """被核验的一条引用。"""

    claim: str
    url: str
    snippet: str


class PerspectiveVerdict(BaseModel):
    """单个核验视角的分裁决。"""

    perspective: str
    supports: bool
    confidence: float
    reason: str


def _new_perspectives() -> list[PerspectiveVerdict]:
    return []


class Verdict(BaseModel):
    """一条引用的聚合裁决。"""

    citation: Citation
    supported: bool
    citation_error: bool
    confidence: float
    perspectives: list[PerspectiveVerdict] = Field(default_factory=_new_perspectives)
    failed_perspectives: int = 0


class VerificationSummary(BaseModel):
    """批量引用核验摘要。"""

    verdicts: list[Verdict]
    total: int
    citation_errors: int
