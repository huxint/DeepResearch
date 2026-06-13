# mcp-tools 规约 —— MCP 检索/抓取工具集成

## 1 职责　（强）
通过 Model Context Protocol 集成外部检索/抓取工具（至少 `search` 与 `fetch`），供 [[pipeline]] 的 Search 阶段调用，把"开放性问题"连接到外部信息源。

## 2 边界与非目标　（强）
- 不做编排 —— 交给 [[kernel]]。
- 不做研究语义（如何分解子问题、如何核验）—— 交给 [[pipeline]] / [[verifier]]。
- 不缓存调用结果（缓存语义属 [[journal]] 层）。

## 3 关键接口/契约　（中）
- `search(query) -> 结果[]`：检索，返回结构化命中列表。
- `fetch(url) -> 内容`：抓取单个 URL 的正文内容。
- 工具调用经 MCP 客户端封装，统一超时控制。

## 4 数据模型　（中）
- `SearchHit`：单条检索结果（标题、url、摘要片段）。
- `FetchedDoc`：抓取回的文档（url、正文、可选元数据）。

## 5 不变式　（强）
1. 工具调用通过 MCP 协议进行（不绕过协议直连）。
2. 每次调用受显式超时约束，不会无限挂起。

## 6 依赖　（强）
- 模块：cross-cutting（config）。
- 库：MCP Python SDK、`httpx`。

## 7 失败语义（弹性接缝）　（中）
- 网络/工具错误在本模块处理（超时、有限次重试）。
- 这是允许做错误处理的接缝之一；上层不为单次工具调用包防御性 try。

## 8 验收标准　（强）
- **given** 一个查询，**when** 调用 `search`，**then** 返回结构化 `SearchHit` 列表。
- **given** 一个 URL，**when** 调用 `fetch`，**then** 取回正文内容。
- **given** 配置的超时，**when** 工具长时间无响应，**then** 超时生效并按失败语义处理。

## 9 开放决策　（——）
- 选用哪些 MCP server（搜索引擎/抓取后端）。
- `SearchHit` / `FetchedDoc` 的规范化字段细节。
- 是否对抓取内容做去重/截断。
