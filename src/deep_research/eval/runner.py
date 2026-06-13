"""数据集评测与回归。"""

import re
from collections.abc import Sequence
from typing import Protocol

from deep_research.eval.models import (
    CaseEvalResult,
    EvalCase,
    EvalResult,
    JudgeAudit,
    JudgeDecision,
    JudgeDisagreement,
    ManualJudgement,
)
from deep_research.pipeline import Report


class ResearchTarget(Protocol):
    """eval 依赖的被测 pipeline 边界。"""

    async def research(self, question: str) -> Report:
        """运行一次完整研究任务。"""
        ...


class AnswerJudge(Protocol):
    """单题答案判定器。"""

    async def judge(self, answer: str, gold: str) -> bool:
        """判断 answer 是否匹配 gold。"""
        ...


class CostTracker(Protocol):
    """可观测累计成本的对象，例如 BudgetPool。"""

    @property
    def spent_usd(self) -> float:
        """累计花费。"""
        ...


class DeterministicJudge:
    """确定性规范化匹配 judge。"""

    async def judge(self, answer: str, gold: str) -> bool:
        normalized_answer = _normalize_answer(answer)
        normalized_gold = _normalize_answer(gold)
        return bool(normalized_gold) and normalized_gold in normalized_answer


class EvalRunner:
    """把完整 research pipeline 当作被测对象运行数据集评测。"""

    def __init__(
        self,
        *,
        pipeline: ResearchTarget,
        judge: AnswerJudge,
        cost_tracker: CostTracker | None = None,
    ) -> None:
        self._pipeline = pipeline
        self._judge = judge
        self._cost_tracker = cost_tracker

    async def run_eval(self, dataset: Sequence[EvalCase]) -> EvalResult:
        case_results: list[CaseEvalResult] = []
        for case in dataset:
            case_results.append(await self._run_case(case))

        correct = sum(result.correct for result in case_results)
        total = len(case_results)
        return EvalResult(
            cases=case_results,
            total=total,
            correct=correct,
            accuracy=correct / total if total else 0.0,
            cost_usd=sum(result.cost_usd for result in case_results),
        )

    async def _run_case(self, case: EvalCase) -> CaseEvalResult:
        before_cost = self._spent_usd()
        try:
            report = await self._pipeline.research(case.question)
            correct = await self._judge.judge(report.body, case.gold_answer)
            return CaseEvalResult(
                case_id=case.case_id,
                question=case.question,
                gold_answer=case.gold_answer,
                answer=report.body,
                correct=correct,
                cost_usd=self._spent_usd() - before_cost,
            )
        except Exception as exc:
            return CaseEvalResult(
                case_id=case.case_id,
                question=case.question,
                gold_answer=case.gold_answer,
                answer="",
                correct=False,
                cost_usd=self._spent_usd() - before_cost,
                error=str(exc),
            )

    def _spent_usd(self) -> float:
        if self._cost_tracker is None:
            return 0.0
        return self._cost_tracker.spent_usd


def audit_judge_consistency(
    *,
    judge_decisions: Sequence[JudgeDecision],
    manual_judgements: Sequence[ManualJudgement],
) -> JudgeAudit:
    manual_by_id = {judgement.case_id: judgement.correct for judgement in manual_judgements}
    disagreements: list[JudgeDisagreement] = []
    agreements = 0

    for decision in judge_decisions:
        manual_correct = manual_by_id[decision.case_id]
        if decision.correct == manual_correct:
            agreements += 1
        else:
            disagreements.append(
                JudgeDisagreement(
                    case_id=decision.case_id,
                    judge_correct=decision.correct,
                    manual_correct=manual_correct,
                )
            )

    total = len(judge_decisions)
    return JudgeAudit(
        total=total,
        agreements=agreements,
        agreement_rate=agreements / total if total else 0.0,
        disagreements=disagreements,
    )


def _normalize_answer(text: str) -> str:
    tokens = re.findall(r"[a-z0-9]+", text.casefold())
    return " ".join(tokens)
