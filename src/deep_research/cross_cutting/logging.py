"""结构化日志（JSON 行）。

每个事件输出一行 JSON，含 ``level`` / ``event`` / ``task_id`` 及任意结构化字段。
``task_id`` 取自 contextvar，用于把一次研究任务的所有日志串联起来。
"""

import json
import logging
import sys
from contextvars import ContextVar
from typing import cast

#: 当前研究任务的关联 id；未设置时日志中 task_id 为 null。
task_id_var: ContextVar[str | None] = ContextVar("task_id", default=None)


class JsonFormatter(logging.Formatter):
    """把日志记录格式化为单行 JSON。"""

    def format(self, record: logging.LogRecord) -> str:
        event = record.__dict__.get("event", record.getMessage())
        payload: dict[str, object] = {
            "level": record.levelname,
            "event": event,
            "task_id": task_id_var.get(),
        }
        fields = record.__dict__.get("fields")
        if isinstance(fields, dict):
            for key, value in cast("dict[str, object]", fields).items():
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO") -> None:
    """在 stderr 上挂一个 JSON 行处理器，作为根日志配置。"""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_event(logger: logging.Logger, event: str, **fields: object) -> None:
    """发一条结构化事件日志。``event`` 为事件名，``fields`` 为附带字段。"""
    logger.info(event, extra={"event": event, "fields": fields})
