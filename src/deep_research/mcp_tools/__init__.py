"""MCP 检索/抓取工具集成。"""

from deep_research.mcp_tools.models import FetchedDoc, MCPToolCall, MCPToolResult, SearchHit
from deep_research.mcp_tools.tools import MCPTools
from deep_research.mcp_tools.transport import (
    MCPClientSessionTransport,
    MCPToolFailed,
    MCPToolTransport,
)

__all__ = [
    "FetchedDoc",
    "MCPClientSessionTransport",
    "MCPToolCall",
    "MCPToolFailed",
    "MCPToolResult",
    "MCPToolTransport",
    "MCPTools",
    "SearchHit",
]
