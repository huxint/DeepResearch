"""mcp-tools 的验收测试。

对应 docs/spec/modules/mcp-tools.md：search/fetch 结构化结果、MCP 工具封装、显式超时。
"""

import asyncio
from dataclasses import dataclass, field

import pytest

from deep_research.journal import JsonValue
from deep_research.mcp_tools import (
    FetchedDoc,
    MCPToolCall,
    MCPToolFailed,
    MCPToolResult,
    MCPTools,
    SearchHit,
)


def _new_calls() -> list[MCPToolCall]:
    return []


@dataclass(slots=True)
class _FakeTransport:
    result: MCPToolResult
    delay_s: float = 0.0
    calls: list[MCPToolCall] = field(default_factory=_new_calls)

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, JsonValue],
        *,
        timeout_s: float,
    ) -> MCPToolResult:
        self.calls.append(MCPToolCall(name=name, arguments=arguments, timeout_s=timeout_s))
        if self.delay_s > 0:
            await asyncio.sleep(self.delay_s)
        return self.result


@pytest.mark.asyncio
async def test_search_returns_structured_hits() -> None:
    transport = _FakeTransport(
        MCPToolResult(
            structured_content={
                "results": [
                    {
                        "title": "Deep research systems",
                        "url": "https://example.test/research",
                        "snippet": "A structured overview.",
                    }
                ]
            }
        )
    )
    tools = MCPTools(transport=transport, timeout_s=0.2)

    hits = await tools.search("deep research")

    assert hits == [
        SearchHit(
            title="Deep research systems",
            url="https://example.test/research",
            snippet="A structured overview.",
        )
    ]
    assert transport.calls == [
        MCPToolCall(name="search", arguments={"query": "deep research"}, timeout_s=0.2)
    ]


@pytest.mark.asyncio
async def test_fetch_returns_document_content() -> None:
    transport = _FakeTransport(
        MCPToolResult(
            structured_content={
                "url": "https://example.test/research",
                "content": "Full page text",
                "metadata": {"source": "example"},
            }
        )
    )
    tools = MCPTools(transport=transport, timeout_s=0.2)

    doc = await tools.fetch("https://example.test/research")

    assert doc == FetchedDoc(
        url="https://example.test/research",
        content="Full page text",
        metadata={"source": "example"},
    )
    assert transport.calls == [
        MCPToolCall(
            name="fetch",
            arguments={"url": "https://example.test/research"},
            timeout_s=0.2,
        )
    ]


@pytest.mark.asyncio
async def test_fetch_can_normalize_text_only_tool_result() -> None:
    transport = _FakeTransport(MCPToolResult(text="Full page text"))
    tools = MCPTools(transport=transport, timeout_s=0.2)

    doc = await tools.fetch("https://example.test/research")

    assert doc == FetchedDoc(url="https://example.test/research", content="Full page text")


@pytest.mark.asyncio
async def test_timeout_is_enforced_and_retried() -> None:
    transport = _FakeTransport(MCPToolResult(text="too late"), delay_s=0.2)
    tools = MCPTools(transport=transport, timeout_s=0.01, max_retries=1, backoff_s=0.0)

    with pytest.raises(MCPToolFailed):
        await tools.search("slow query")

    assert len(transport.calls) == 2
