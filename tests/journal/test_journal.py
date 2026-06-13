"""journal 的验收测试。

对应 docs/spec/modules/journal.md：SQLite append-only 缓存、前缀命中续跑、重复写入幂等。
"""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from deep_research.journal import Journal, JsonValue, make_journal_hash, prompt_fingerprint


@dataclass(frozen=True, slots=True)
class _Step:
    prompt: str
    params: dict[str, JsonValue]


def _compute_result(step: _Step) -> dict[str, JsonValue]:
    return {"text": f"{step.prompt}:{step.params['q']}"}


def _resume(journal: Journal, steps: Sequence[_Step]) -> tuple[list[JsonValue], list[str]]:
    results: list[JsonValue] = []
    actual_calls: list[str] = []
    cache_enabled = True

    for step in steps:
        entry_hash = make_journal_hash(prompt=step.prompt, params=step.params)
        cached = journal.lookup(entry_hash) if cache_enabled else None
        if cached is not None:
            results.append(cached)
            continue

        cache_enabled = False
        result = _compute_result(step)
        actual_calls.append(step.prompt)
        journal.append(
            entry_hash,
            result,
            prompt_fingerprint=prompt_fingerprint(step.prompt),
            params=step.params,
        )
        results.append(result)

    return results, actual_calls


def test_hash_is_stable_for_canonical_prompt_and_params() -> None:
    left = make_journal_hash(prompt="search", params={"q": "alpha", "page": 1})
    right = make_journal_hash(prompt="search", params={"page": 1, "q": "alpha"})

    assert left == right
    assert len(left) == 64


def test_resume_hits_unchanged_prefix_after_process_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "journal.sqlite3"
    steps = [
        _Step(prompt="plan", params={"q": "open question"}),
        _Step(prompt="search", params={"q": "sub question"}),
        _Step(prompt="write", params={"q": "verified claims"}),
    ]

    first = Journal(db_path)
    initial_results, initial_calls = _resume(first, steps)
    first.close()

    resumed = Journal(db_path)
    resumed_results, resumed_calls = _resume(resumed, steps)
    resumed.close()

    assert initial_calls == ["plan", "search", "write"]
    assert resumed_calls == []
    assert resumed_results == initial_results


def test_resume_reruns_from_first_changed_step(tmp_path: Path) -> None:
    db_path = tmp_path / "journal.sqlite3"
    original_steps = [
        _Step(prompt="plan", params={"q": "open question"}),
        _Step(prompt="search", params={"q": "sub question"}),
        _Step(prompt="write", params={"q": "verified claims"}),
    ]
    changed_steps = [
        _Step(prompt="plan", params={"q": "open question"}),
        _Step(prompt="search", params={"q": "changed sub question"}),
        _Step(prompt="write", params={"q": "verified claims"}),
    ]

    first = Journal(db_path)
    _resume(first, original_steps)
    first.close()

    resumed = Journal(db_path)
    _, resumed_calls = _resume(resumed, changed_steps)
    resumed.close()

    assert resumed_calls == ["search", "write"]


def test_duplicate_append_keeps_lookup_correct(tmp_path: Path) -> None:
    journal = Journal(tmp_path / "journal.sqlite3")
    entry_hash = make_journal_hash(prompt="plan", params={"q": "open question"})

    journal.append(entry_hash, {"text": "first"})
    journal.append(entry_hash, {"text": "second"})
    result = journal.lookup(entry_hash)
    journal.close()

    assert result == {"text": "first"}


def test_lookup_entry_returns_stored_metadata(tmp_path: Path) -> None:
    journal = Journal(tmp_path / "journal.sqlite3")
    entry_hash = make_journal_hash(prompt="plan", params={"q": "open question"})
    fingerprint = prompt_fingerprint("plan")

    journal.append(
        entry_hash,
        {"text": "ok"},
        prompt_fingerprint=fingerprint,
        params={"q": "open question"},
    )
    entry = journal.lookup_entry(entry_hash)
    journal.close()

    assert entry is not None
    assert entry.hash == entry_hash
    assert entry.prompt_fingerprint == fingerprint
    assert entry.params == {"q": "open question"}
    assert entry.result == {"text": "ok"}
