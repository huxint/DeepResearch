"""CLI entrypoint tests."""

import pytest

from deep_research import cli
from deep_research.pipeline import Report


def test_research_command_prints_json_report(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_run_research(question: str) -> Report:
        return Report(question=question, body="answer")

    monkeypatch.setattr(cli, "run_research", fake_run_research)

    exit_code = cli.main(["research", "What happened?", "--json"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"question": "What happened?"' in captured.out
    assert '"body": "answer"' in captured.out
    assert captured.err == ""
