"""provider-pool 的边界数据模型。"""

from pydantic import BaseModel, Field, PositiveInt

from deep_research.cross_cutting.budget import Usage


class ProviderKeyConfig(BaseModel):
    """单个 Provider Key 的静态配置。"""

    key_id: str
    api_key: str
    rpm: PositiveInt
    max_concurrency: PositiveInt
    weight: PositiveInt = 1


class ProviderConfig(BaseModel):
    """单个 LLM provider 及其 Key 列表。"""

    name: str
    endpoint: str
    keys: list[ProviderKeyConfig]
    default_model: str
    headers: dict[str, str] = Field(default_factory=dict)


class LLMRequest(BaseModel):
    """一次 LLM 调用请求。"""

    model: str
    messages: list[dict[str, str]]
    temperature: float | None = None
    max_tokens: int | None = None


class LLMResponse(BaseModel):
    """一次 LLM 调用响应，含 token/成本元数据。"""

    text: str
    usage: Usage
    provider: str
    key_id: str
    status_code: int


class KeySnapshot(BaseModel):
    """单个 Key 的可观测状态快照。"""

    provider: str
    key_id: str
    in_flight: int
    is_circuited: bool
