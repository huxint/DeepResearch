# 运行 DeepResearch

本页描述真实运行入口，不是测试用 fake 组件。

## 安装/同步

```bash
uv sync
```

`pyproject.toml` 已声明 build backend 与 console script，同步后可使用：

```bash
uv run deep-research --help
```

## 配置

配置从环境变量或 `.env` 读取，前缀为 `DR_`。

最小示例：

```bash
DR_BUDGET_USD=1.0
DR_DEFAULT_MODEL=gpt-4o-mini
DR_REQUEST_TIMEOUT_S=30
DR_JOURNAL_PATH=.deep_research/journal.sqlite3

DR_PROVIDERS='[
  {
    "name": "openai",
    "endpoint": "https://api.openai.com/v1/chat/completions",
    "default_model": "gpt-4o-mini",
    "response_format": "openai_chat",
    "input_usd_per_1m": 0.15,
    "output_usd_per_1m": 0.60,
    "keys": [
      {
        "key_id": "main",
        "api_key": "sk-...",
        "rpm": 60,
        "max_concurrency": 4
      }
    ]
  }
]'

DR_MCP_SERVER='{
  "command": "uvx",
  "args": ["your-mcp-search-server"],
  "env": {"SEARCH_API_KEY": "..."}
}'
```

## Provider 响应格式

`ProviderConfig.response_format` 支持两种格式：

- `openai_chat`：解析 OpenAI Chat Completions 响应的 `choices[0].message.content` 与 `usage.prompt_tokens` / `usage.completion_tokens`。
- `deep_research`：兼容测试/内部 adapter，响应体为 `{"text": "...", "usage": {"input_tokens": 1, "output_tokens": 1, "cost_usd": 0.001}}`。

成本由 `input_usd_per_1m` 和 `output_usd_per_1m` 估算并写入共享预算池。

## MCP 工具要求

`DR_MCP_SERVER` 启动的 MCP server 必须暴露两个工具：

- `search`：输入 `{"query": "..."}`，返回结构化内容 `{"results": [{"title": "...", "url": "...", "snippet": "..."}]}`。
- `fetch`：输入 `{"url": "..."}`，返回结构化内容 `{"url": "...", "content": "...", "metadata": {...}}`；也可只返回文本内容。

## 运行

```bash
uv run deep-research research "What changed in the latest OpenAI Deep Research architecture?" --json
```

不加 `--json` 时只打印报告正文和引用列表。
