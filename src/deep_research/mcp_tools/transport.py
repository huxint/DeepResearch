"""MCP client transport adapters."""

from datetime import timedelta
from typing import Protocol

from mcp import ClientSession
from mcp.shared.exceptions import McpError
from mcp.types import TextContent
from pydantic import TypeAdapter

from deep_research.cross_cutting.errors import Fatal
from deep_research.journal import JsonValue
from deep_research.mcp_tools.models import MCPToolResult

_JSON_OBJECT: TypeAdapter[dict[str, JsonValue]] = TypeAdapter(dict[str, JsonValue])


class MCPToolFailed(Fatal):
    """MCP 工具调用失败。"""


class MCPToolTransport(Protocol):
    """通过 MCP 协议调用工具的最小 transport 边界。"""

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, JsonValue],
        *,
        timeout_s: float,
    ) -> MCPToolResult:
        """调用一个 MCP tool。"""
        ...


class MCPClientSessionTransport:
    """把 MCP SDK 的 ClientSession 包成项目内严格类型 transport。"""

    def __init__(self, session: ClientSession) -> None:
        self._session = session

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, JsonValue],
        *,
        timeout_s: float,
    ) -> MCPToolResult:
        try:
            result = await self._session.call_tool(
                name,
                arguments,
                read_timeout_seconds=timedelta(seconds=timeout_s),
            )
        except TimeoutError as exc:
            raise MCPToolFailed(f"MCP tool 超时：{name}") from exc
        except McpError as exc:
            raise MCPToolFailed(f"MCP tool 调用失败：{name}") from exc

        if result.isError:
            raise MCPToolFailed(f"MCP tool 返回错误：{name}")

        text_chunks: list[str] = []
        for content in result.content:
            if isinstance(content, TextContent):
                text_chunks.append(content.text)

        structured_content = (
            None
            if result.structuredContent is None
            else _JSON_OBJECT.validate_python(result.structuredContent)
        )
        return MCPToolResult(text="\n".join(text_chunks), structured_content=structured_content)
