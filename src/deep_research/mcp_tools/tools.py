"""Search/fetch tools exposed through MCP."""

import asyncio

from pydantic import BaseModel

from deep_research.journal import JsonValue
from deep_research.mcp_tools.models import FetchedDoc, MCPToolResult, SearchHit
from deep_research.mcp_tools.transport import MCPToolFailed, MCPToolTransport


class _SearchPayload(BaseModel):
    results: list[SearchHit]


class MCPTools:
    """面向 pipeline Search 阶段的 MCP 工具封装。"""

    def __init__(
        self,
        *,
        transport: MCPToolTransport,
        timeout_s: float,
        max_retries: int = 1,
        backoff_s: float = 0.05,
    ) -> None:
        self._transport = transport
        self._timeout_s = timeout_s
        self._max_retries = max_retries
        self._backoff_s = backoff_s

    async def search(self, query: str) -> list[SearchHit]:
        result = await self._call("search", {"query": query})
        structured_content = self._require_structured(result, tool_name="search")
        return _SearchPayload.model_validate(structured_content).results

    async def fetch(self, url: str) -> FetchedDoc:
        result = await self._call("fetch", {"url": url})
        if result.structured_content is None:
            return FetchedDoc(url=url, content=result.text)
        return FetchedDoc.model_validate(result.structured_content)

    async def _call(self, name: str, arguments: dict[str, JsonValue]) -> MCPToolResult:
        for attempt in range(self._max_retries + 1):
            try:
                async with asyncio.timeout(self._timeout_s):
                    return await self._transport.call_tool(
                        name,
                        arguments,
                        timeout_s=self._timeout_s,
                    )
            except TimeoutError as exc:
                if attempt == self._max_retries:
                    raise MCPToolFailed(f"MCP tool 超时：{name}") from exc
            except MCPToolFailed:
                if attempt == self._max_retries:
                    raise

            await asyncio.sleep(self._backoff_s)

        raise MCPToolFailed(f"MCP tool 调用失败：{name}")

    def _require_structured(self, result: MCPToolResult, *, tool_name: str) -> dict[str, JsonValue]:
        if result.structured_content is None:
            raise MCPToolFailed(f"MCP tool 缺少结构化结果：{tool_name}")
        return result.structured_content
