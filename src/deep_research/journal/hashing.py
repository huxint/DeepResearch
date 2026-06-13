"""journal 哈希与 JSON 规范化。"""

import hashlib
import json

from pydantic import TypeAdapter

from deep_research.journal.models import JsonValue

_JSON_VALUE: TypeAdapter[JsonValue] = TypeAdapter(JsonValue)


def canonical_json(value: JsonValue) -> str:
    """把 JSON 载荷转成稳定字符串，供哈希与 SQLite 存储复用。"""

    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def parse_json_value(raw: str) -> JsonValue:
    """从 SQLite 文本字段恢复并校验 JSON 载荷。"""

    return _JSON_VALUE.validate_json(raw)


def prompt_fingerprint(prompt: str) -> str:
    """仅针对 prompt 文本的 sha256 指纹。"""

    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def make_journal_hash(*, prompt: str, params: dict[str, JsonValue]) -> str:
    """对 prompt 与参数做规范化 sha256，作为 Journal lookup key。"""

    payload: dict[str, JsonValue] = {"prompt": prompt, "params": params}
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
