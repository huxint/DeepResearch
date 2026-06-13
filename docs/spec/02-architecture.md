# 架构与数据流

## 组件图

系统分五层，下层为上层提供能力；箭头表示依赖。各模块详规见 `modules/`。

```
评测      [[eval]]
            │ 跑全系统打分 / 核成本
研究语义  [[pipeline]] ──────────────┐
            │ Plan→Search→Verify→Write │
          [[verifier]]                 │ 调原语
            │ 多视角引用核验            │
执行单元  [[kernel]] ─── agent/pipeline/parallel 三原语
            │                          │
          [[subagent]] ── prompt→调用→校验→重试→预算
            │                          │
单调用    [[provider-pool]]   [[journal]]   [[mcp-tools]]
            │ 多Key调度/限流    │ 哈希缓存    │ search/fetch
            │ /熔断/退避        │ 续跑        │
地基      03-cross-cutting.md —— config / 结构化日志 / 错误分类 / token 计费
```

- **地基层**：横切关注，所有模块共享（配置、日志、错误分类、token 计费）。
- **单调用层**：三者可并行开发 —— [[provider-pool]] 发 LLM 调用、[[journal]] 持久化、[[mcp-tools]] 检索抓取。
- **执行单元层**：[[subagent]] 把一次 LLM 调用做成"校验 + 重试 + 计费"的可靠单元；[[kernel]] 在其上提供编排原语并叠加 Journal 缓存。
- **研究语义层**：[[verifier]] 做引用核验；[[pipeline]] 用原语把四阶段串成主流程。
- **评测层**：[[eval]] 把整条流水线当作被测对象打分、核成本、回归。

## 四阶段数据流

```
question
   │
   ▼  Plan      —— [[subagent]] 把问题分解为子问题列表
sub-questions[]
   │
   ▼  Search    —— [[kernel]].parallel 多路并行，经 [[mcp-tools]] 检索/抓取
search-results[]
   │
   ▼  Verify    —— [[verifier]] 对每条引用多视角扇出溯源核验
verified-claims[]
   │
   ▼  Write     —— [[subagent]] 用已核验论断撰写带引用报告
report (带引用)
```

每条引用必须先通过 Verify 才能进入 Write —— 这是保证报告引用都经过核验、可溯源的结构性设计。

## 控制流确定性

- 编排由**脚本**驱动：哪些步骤、是无屏障流水（pipeline）还是屏障扇出（parallel），由 [[pipeline]] 的脚本写死。
- 模型只做**单步推理**：每次 agent 调用只回答"这一步"，不决定"下一步走哪"。
- 取舍：Search 的多路检索用 pipeline 让各子问题独立穿越各阶段、互不等待（多路并行让端到端明显快于串行的来源）；需要"凑齐全部结果再继续"的环节（如汇总去重）才用 parallel 屏障。

## 三大特点如何落到组件

| 特点 | 落地组件 | 机制 |
|---|---|---|
| 控制流确定 | [[kernel]] + [[pipeline]] | 脚本驱动的 agent/pipeline/parallel，模型只单步推理 |
| 故障可恢复 | [[journal]] | (prompt,参数) 哈希键 append-only 缓存，resume 命中未变更前缀 |
| 成本可治理 | [[provider-pool]] + token 预算池 + [[verifier]] | 池化抗限流、预算超限熔断、引用溯源核验 |
