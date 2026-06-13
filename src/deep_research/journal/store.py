"""SQLite-backed append-only Journal。"""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Self, cast

from deep_research.cross_cutting.errors import Fatal
from deep_research.journal.hashing import canonical_json, parse_json_value
from deep_research.journal.models import JournalEntry, JsonValue


class JournalIOFailed(Fatal):
    """SQLite 读写失败。"""


class Journal:
    """以 hash 为键的 append-only SQLite Journal。"""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        try:
            self._conn = sqlite3.connect(self._path)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS journal_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hash TEXT NOT NULL,
                    prompt_fingerprint TEXT NOT NULL,
                    params_json TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_journal_entries_hash ON journal_entries(hash)"
            )
            self._conn.commit()
        except sqlite3.Error as exc:
            raise JournalIOFailed(f"Journal 初始化失败：{self._path}") from exc

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def lookup(self, hash: str) -> JsonValue | None:
        """按 hash 查询最早一条记录的结果载荷；未命中返回 None。"""

        entry = self.lookup_entry(hash)
        if entry is None:
            return None
        return entry.result

    def lookup_entry(self, hash: str) -> JournalEntry | None:
        """按 hash 查询最早一条完整记录。"""

        try:
            row = self._conn.execute(
                """
                SELECT hash, prompt_fingerprint, params_json, result_json, created_at
                FROM journal_entries
                WHERE hash = ?
                ORDER BY id ASC
                LIMIT 1
                """,
                (hash,),
            ).fetchone()
        except sqlite3.Error as exc:
            raise JournalIOFailed(f"Journal 查询失败：{hash}") from exc

        if row is None:
            return None

        stored_hash, fingerprint, params_json, result_json, created_at = cast(
            tuple[str, str, str, str, str], row
        )
        return JournalEntry(
            hash=stored_hash,
            prompt_fingerprint=fingerprint,
            params=cast(dict[str, JsonValue], parse_json_value(params_json)),
            result=parse_json_value(result_json),
            created_at=datetime.fromisoformat(created_at),
        )

    def append(
        self,
        hash: str,
        result: JsonValue,
        *,
        prompt_fingerprint: str = "",
        params: dict[str, JsonValue] | None = None,
    ) -> None:
        """追加一次调用结果；重复 hash 不覆盖旧记录。"""

        params_payload = {} if params is None else params
        created_at = datetime.now(UTC).isoformat()
        try:
            self._conn.execute(
                """
                INSERT INTO journal_entries (
                    hash,
                    prompt_fingerprint,
                    params_json,
                    result_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    hash,
                    prompt_fingerprint,
                    canonical_json(params_payload),
                    canonical_json(result),
                    created_at,
                ),
            )
            self._conn.commit()
        except sqlite3.Error as exc:
            raise JournalIOFailed(f"Journal 写入失败：{hash}") from exc

    def close(self) -> None:
        self._conn.close()
