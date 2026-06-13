"""journal 的边界数据模型。"""

from datetime import datetime

from pydantic import BaseModel, Field

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]


class JournalEntry(BaseModel):
    """一次 agent 调用的 append-only 记录。"""

    hash: str
    prompt_fingerprint: str = ""
    params: dict[str, JsonValue] = Field(default_factory=dict)
    result: JsonValue
    created_at: datetime
