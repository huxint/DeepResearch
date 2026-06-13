"""eval 的边界数据模型。"""

from pydantic import BaseModel, Field


class EvalCase(BaseModel):
    """单条评测样本。"""

    case_id: str
    question: str
    gold_answer: str


class CaseEvalResult(BaseModel):
    """单题评测结果。"""

    case_id: str
    question: str
    gold_answer: str
    answer: str
    correct: bool
    cost_usd: float = 0.0
    error: str | None = None


def _new_case_results() -> list[CaseEvalResult]:
    return []


class EvalResult(BaseModel):
    """评测汇总。"""

    cases: list[CaseEvalResult] = Field(default_factory=_new_case_results)
    total: int
    correct: int
    accuracy: float
    cost_usd: float = 0.0


class JudgeDecision(BaseModel):
    """judge 对某题的判定。"""

    case_id: str
    correct: bool


class ManualJudgement(BaseModel):
    """人工抽检判定。"""

    case_id: str
    correct: bool


class JudgeDisagreement(BaseModel):
    """judge 与人工不一致的样本。"""

    case_id: str
    judge_correct: bool
    manual_correct: bool


def _new_disagreements() -> list[JudgeDisagreement]:
    return []


class JudgeAudit(BaseModel):
    """judge/人工一致性审计结果。"""

    total: int
    agreements: int
    agreement_rate: float
    disagreements: list[JudgeDisagreement] = Field(default_factory=_new_disagreements)
