"""结构化日志的验收测试。

对应 docs/spec/03-cross-cutting.md「可观测」：JSON 行结构化日志，可按任务关联 id
串联，事件带结构化字段。
"""

import io
import json
import logging

from deep_research.cross_cutting.logging import (
    JsonFormatter,
    log_event,
    task_id_var,
)


def _capture(logger_name: str) -> tuple[logging.Logger, io.StringIO]:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger(logger_name)
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger, stream


def test_log_event_emits_valid_json_with_event_and_fields() -> None:
    logger, stream = _capture("test.json.fields")
    log_event(logger, "agent_call", tokens=140, cached=False)
    record = json.loads(stream.getvalue())
    assert record["event"] == "agent_call"
    assert record["level"] == "INFO"
    assert record["tokens"] == 140
    assert record["cached"] is False


def test_log_event_carries_task_id_from_contextvar() -> None:
    logger, stream = _capture("test.json.taskid")
    token = task_id_var.set("task-abc")
    try:
        log_event(logger, "phase_enter", phase="Search")
    finally:
        task_id_var.reset(token)
    record = json.loads(stream.getvalue())
    assert record["task_id"] == "task-abc"
    assert record["phase"] == "Search"


def test_task_id_absent_when_not_set() -> None:
    logger, stream = _capture("test.json.notaskid")
    log_event(logger, "boot")
    record = json.loads(stream.getvalue())
    assert record["task_id"] is None
