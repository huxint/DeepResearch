"""eval 的验收测试。

对应 docs/spec/modules/eval.md：逐题对错、汇总、judge 一致性审计、单题失败继续。
"""

from dataclasses import dataclass

import pytest

from deep_research.eval import (
    DeterministicJudge,
    EvalCase,
    EvalRunner,
    JudgeDecision,
    ManualJudgement,
    audit_judge_consistency,
)
from deep_research.pipeline import Report


@dataclass(slots=True)
class _FakePipeline:
    answers: dict[str, str]
    failures: set[str]
    cost_tracker: _CostTracker

    async def research(self, question: str) -> Report:
        self.cost_tracker.spent_usd += 0.05
        if question in self.failures:
            raise RuntimeError(f"failed: {question}")
        return Report(question=question, body=self.answers[question])


@dataclass(slots=True)
class _CostTracker:
    spent_usd: float = 0.0


@pytest.mark.asyncio
async def test_run_eval_outputs_per_case_and_summary() -> None:
    cost_tracker = _CostTracker()
    pipeline = _FakePipeline(
        answers={
            "What color is the ocean?": "The ocean is blue.",
            "What color is Mars?": "Mars is blue.",
        },
        failures=set(),
        cost_tracker=cost_tracker,
    )
    runner = EvalRunner(
        pipeline=pipeline,
        judge=DeterministicJudge(),
        cost_tracker=cost_tracker,
    )

    result = await runner.run_eval(
        [
            EvalCase(case_id="1", question="What color is the ocean?", gold_answer="blue"),
            EvalCase(case_id="2", question="What color is Mars?", gold_answer="red"),
        ]
    )

    assert result.total == 2
    assert result.correct == 1
    assert result.accuracy == 0.5
    assert [case.correct for case in result.cases] == [True, False]
    assert [case.cost_usd for case in result.cases] == [0.05, 0.05]
    assert result.cost_usd == 0.1


def test_judge_audit_reports_human_agreement() -> None:
    audit = audit_judge_consistency(
        judge_decisions=[
            JudgeDecision(case_id="1", correct=True),
            JudgeDecision(case_id="2", correct=False),
        ],
        manual_judgements=[
            ManualJudgement(case_id="1", correct=True),
            ManualJudgement(case_id="2", correct=True),
        ],
    )

    assert audit.total == 2
    assert audit.agreements == 1
    assert audit.agreement_rate == 0.5
    assert [item.case_id for item in audit.disagreements] == ["2"]


@pytest.mark.asyncio
async def test_single_case_failure_is_marked_wrong_and_batch_continues() -> None:
    cost_tracker = _CostTracker()
    pipeline = _FakePipeline(
        answers={"ok": "answer"},
        failures={"boom"},
        cost_tracker=cost_tracker,
    )
    runner = EvalRunner(
        pipeline=pipeline,
        judge=DeterministicJudge(),
        cost_tracker=cost_tracker,
    )

    result = await runner.run_eval(
        [
            EvalCase(case_id="1", question="boom", gold_answer="answer"),
            EvalCase(case_id="2", question="ok", gold_answer="answer"),
        ]
    )

    assert result.total == 2
    assert result.correct == 1
    assert result.cases[0].correct is False
    assert result.cases[0].error == "failed: boom"
    assert result.cases[1].correct is True


@pytest.mark.asyncio
async def test_deterministic_judge_is_reproducible() -> None:
    judge = DeterministicJudge()

    first = await judge.judge("The answer is Blue.", "blue")
    second = await judge.judge("The answer is Blue.", "blue")

    assert first is True
    assert second is True
