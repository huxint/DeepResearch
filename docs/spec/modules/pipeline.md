# pipeline 规约 —— 研究主流程（Plan→Search→Verify→Write）

## 1 职责　（强）
研究主流程脚本：把一个开放性问题，经 **Plan → Search → Verify → Write** 四阶段确定性编排，产出一份带引用的研究报告。这是把所有模块串起来的顶层脚本。

## 2 边界与非目标　（强）
- 不实现编排原语 —— 用 [[kernel]] 的 agent/pipeline/parallel。
- 不实现检索/核验内部 —— 交给 [[mcp-tools]] / [[verifier]]。
- 不实现 LLM 调用细节 —— 交给 [[subagent]]。

## 3 关键接口/契约　（中）
- `research(question) -> 带引用报告`：执行完整四阶段。
  - Plan：用 [[subagent]] 把问题分解为子问题列表。
  - Search：用 [[kernel]].pipeline/parallel 多路并行，经 [[mcp-tools]] 检索/抓取。
  - Verify：用 [[verifier]] 对每条引用溯源核验。
  - Write：用 [[subagent]] 基于已核验论断撰写带引用报告。

## 4 数据模型　（中）
- `Plan`：子问题列表。
- `SearchResult`：某子问题的检索/抓取产物。
- `VerifiedClaim`：通过核验的论断及其引用。
- `Report`：最终带引用报告。

## 5 不变式　（强）
1. 控制流确定：阶段顺序与并行/串行结构由脚本写死，不由模型决定。
2. Search 阶段多路并行（让多路检索明显快于串行）。
3. 每条引用必须先通过 Verify，才能进入 Write。

## 6 依赖　（强）
- 模块：[[kernel]]、[[subagent]]、[[mcp-tools]]、[[verifier]]。

## 7 失败语义　（中）
- 各阶段内部失败委托对应模块的语义（重试/熔断/降级）。
- 顶层 runner（弹性接缝）兜底：捕获致命错误、记录、终止任务（依赖 [[journal]] 让重启恢复成本极低）。

## 8 验收标准　（强）
- **given** 一个开放性问题，**when** 调用 `research`，**then** 端到端产出一份带引用的报告。
- **given** 同一组子问题，**when** 分别用并行与串行检索执行，**then** 并行端到端时延显著低于串行基线。
- **given** 一条未通过 Verify 的引用，**when** 进入 Write，**then** 该引用不出现在最终报告中。

## 9 开放决策　（——）
- 四阶段的进一步细分粒度。
- 子问题分解策略与数量控制。
- 报告模板与引用标注格式。
