"""Runtime bootstrap tests for real configurable execution."""

from dataclasses import dataclass, field
from pathlib import Path

import httpx
import pytest

from deep_research.cross_cutting.config import Settings
from deep_research.cross_cutting.errors import ConfigMissing
from deep_research.journal import JsonValue
from deep_research.mcp_tools import FetchedDoc, SearchHit
from deep_research.provider_pool import ProviderConfig, ProviderKeyConfig
from deep_research.runtime import build_research_pipeline, run_research


def _new_fetch_calls() -> list[str]:
    return []


@dataclass(slots=True)
class _RuntimeTools:
    fetch_calls: list[str] = field(default_factory=_new_fetch_calls)

    async def search(self, query: str) -> list[SearchHit]:
        return [
            SearchHit(
                title=query,
                url="https://example.test/ocean",
                snippet="The ocean is blue",
            )
        ]

    async def fetch(self, url: str) -> FetchedDoc:
        self.fetch_calls.append(url)
        return FetchedDoc(url=url, content="The ocean is blue because water absorbs red light.")


def _settings(tmp_path: Path) -> Settings:
    return Settings.model_validate(
        {
            "budget_usd": 1.0,
            "default_model": "gpt-test",
            "journal_path": str(tmp_path / "journal.sqlite3"),
            "request_timeout_s": 1.0,
            "providers": [
                ProviderConfig(
                    name="openai",
                    endpoint="https://api.example.test/v1/chat/completions",
                    keys=[
                        ProviderKeyConfig(
                            key_id="main",
                            api_key="secret",
                            rpm=60,
                            max_concurrency=2,
                        )
                    ],
                    default_model="gpt-test",
                    response_format="openai_chat",
                    input_usd_per_1m=1.0,
                    output_usd_per_1m=2.0,
                )
            ],
        }
    )


def _openai_chat_response(content: str) -> dict[str, JsonValue]:
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50},
    }


@pytest.mark.asyncio
async def test_run_research_bootstraps_provider_journal_and_pipeline(tmp_path: Path) -> None:
    responses = [
        '{"subquestions":["ocean color"]}',
        '{"body":"The ocean is blue [https://example.test/ocean]."}',
    ]
    requested_auth: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requested_auth.append(request.headers["Authorization"])
        return httpx.Response(200, json=_openai_chat_response(responses.pop(0)))

    tools = _RuntimeTools()

    report = await run_research(
        "Why is the ocean blue?",
        settings=_settings(tmp_path),
        tools=tools,
        provider_transport=httpx.MockTransport(handler),
    )

    assert report.question == "Why is the ocean blue?"
    assert "ocean is blue" in report.body
    assert [citation.url for citation in report.citations] == ["https://example.test/ocean"]
    assert requested_auth == ["Bearer secret", "Bearer secret"]
    assert tools.fetch_calls == [
        "https://example.test/ocean",
        "https://example.test/ocean",
    ]


@pytest.mark.asyncio
async def test_runtime_requires_mcp_server_when_tools_are_not_injected(tmp_path: Path) -> None:
    with pytest.raises(ConfigMissing):
        async with build_research_pipeline(
            _settings(tmp_path),
            provider_transport=httpx.MockTransport(
                lambda request: httpx.Response(500, json={"error": "unused"})
            ),
        ):
            pass
