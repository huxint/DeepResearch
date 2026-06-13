# 构建顺序 DAG + Tracer-bullet + 状态表

依赖关系由各模块规约的 §6 汇成；本文件给拓扑视图、最小纵切路径、以及驱动续跑的构建状态表。

## 依赖分波

粗箭头 = 依赖谁。同波内模块可并行开发。

```
Wave 0  地基
  cross-cutting        config / 结构化日志 / 错误分类 / token 计费类型   (无内部依赖)

Wave 1  单调用能力 ───────── 三者可并行
  provider-pool ─▶ cross-cutting   先做"单 provider 单 key 能发请求"，调度/限流/熔断留接口
  journal       ─▶ cross-cutting   SQLite append + hash 键 + 命中查询
  mcp-tools     ─▶ cross-cutting   一个 search + 一个 fetch

Wave 2  Agent 执行单元 + 编排原语
  subagent      ─▶ provider-pool, cross-cutting   prompt→调用→pydantic 校验→带上下文重试→预算扣减
  kernel        ─▶ subagent, journal              agent=journal 缓存+subagent 执行；pipeline 无屏障；parallel 屏障；并发上限 min(16,cpu-2)

Wave 3  研究语义
  verifier      ─▶ kernel, mcp-tools              多视角扇出 + 逐条引用溯源
  pipeline      ─▶ kernel, subagent, mcp-tools, verifier   Plan→Search→Verify→Write 主流程

Wave 4  评测闭环
  eval          ─▶ pipeline, provider-pool        在数据集上端到端评测 + 回归
```

## Tracer-bullet：先打穿，再加厚

**不按波次逐个做完**，先拉一条最小端到端纵切让系统尽早可跑：

```
配置 → 单 key provider → 最小 subagent(单 schema) → 最小 kernel(只 agent+parallel)
     → 单 search 工具 → Plan / Search / Write 三段(Verify 先 stub)
     → 对一道题产出"粗糙但带引用"的报告 ✅ 端到端打通
```

### 加厚顺序（打通后回各模块补强）

1. 号池：多 Key / 滑窗限流 / 429 熔断换道 / 指数退避。
2. [[journal]] 续跑：哈希键缓存 + resume 命中。
3. [[verifier]] 全量多视角扇出。
4. [[pipeline]] 无屏障流水优化（让多路并行真正快于串行）。
5. [[eval]] 能在数据集上端到端跑出结果。

指标不是开发目标；加厚是为了让功能真正成立（能并行、能续跑、能评测），不是为了凑数字。

## 构建状态表（驱动续跑）

每完成一格勾掉对应 `☐`。`/build-next` 据此取下一个模块。

| 模块 | 依赖就绪 | 规约✓ | 测试✓ | 实现✓ | 质量门✓ |
|---|---|---|---|---|---|
| cross-cutting | — | ✓ | ✓ | ✓ | ✓ |
| provider-pool | ✓ | ✓ | ✓ | ✓ | ✓ |
| journal | ✓ | ✓ | ✓ | ✓ | ✓ |
| mcp-tools | ✓ | ☐ | ☐ | ☐ | ☐ |
| subagent | ☐ | ☐ | ☐ | ☐ | ☐ |
| kernel | ☐ | ☐ | ☐ | ☐ | ☐ |
| verifier | ☐ | ☐ | ☐ | ☐ | ☐ |
| pipeline | ☐ | ☐ | ☐ | ☐ | ☐ |
| eval | ☐ | ☐ | ☐ | ☐ | ☐ |
