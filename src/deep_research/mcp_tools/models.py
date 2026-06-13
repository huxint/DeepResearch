"""mcp-tools 的边界数据模型。"""

from pydantic import BaseModel, Field

from deep_research.journal import JsonValue


class SearchHit(BaseModel):
    """单条检索结果。"""

    title: str
    url: str
    snippet: str


class FetchedDoc(BaseModel):
    """抓取回的文档正文。"""

    url: str
    content: str
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class MCPToolResult(BaseModel):
    """MCP 工具调用结果的规范化形态。"""

    text: str = ""
    structured_content: dict[str, JsonValue] | None = None


class MCPToolCall(BaseModel):
    """一次发给 MCP transport 的工具调用。"""

    name: str
    arguments: dict[str, JsonValue]
    timeout_s: float
