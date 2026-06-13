# 术语表 / 领域语言

本表是全项目共享的语言。规约与代码出现这些词时，含义以此处为准。模块间引用统一用 `[[module]]` 双链。

### Workflow 编排内核
零框架依赖的编排层（[[kernel]]），以 agent / pipeline / parallel 三原语把子 Agent 组织成确定性执行结构。

### agent 原语
派生一个子 Agent 做**单步推理**的调用。给定 schema 时强制结构化输出并经 pydantic 校验后返回校验对象，否则返回文本。

### pipeline 原语（无屏障）
让每个条目独立穿过所有阶段的流水编排：条目 A 可处于 stage 3，而条目 B 仍在 stage 1，互不等待。

### parallel 原语（屏障扇出）
并发扇出一组任务并等待全部完成后聚合的编排；单个任务抛错降级为 `None`，调用本身不抛。

### 子 Agent (subagent)
一次"prompt → provider 调用 → 校验 → 重试 → 预算扣减"的执行单元（[[subagent]]），是 agent 原语的执行体。

### 多 Provider 号池
对多提供商、多 API Key 做池化管理与调度的组件（[[provider-pool]]），用以规避上游 RPM 与并发限制。

### 滑动窗口限流
按单个 Key 维度、在滑动时间窗内计数并设上限的限流策略，防止触发上游 RPM。

### 熔断换道
某 Key/Provider 触发 429 或超时后暂时摘除（熔断），把请求切到其他可用通道（换道）。

### Journal（断点续跑）
以 (prompt, 参数) 哈希为键、append-only 写入 SQLite 的执行日志（[[journal]]），用于 resume 时命中缓存。

### 前缀命中缓存
resume 时，未变更的调用前缀直接命中 Journal 缓存返回，仅从第一个变更步骤起重跑。

### 四阶段（Plan / Search / Verify / Write）
研究主流程（[[pipeline]]）的四个阶段：规划子问题 → 多路并行检索 → 逐条引用溯源核验 → 撰写带引用报告。

### 引用溯源核验
对报告中每条引用回到来源核对其是否真正支持论断的过程（[[verifier]]）。

### 多视角扇出
对同一条引用从多个独立视角并发核验、再聚合裁决，以提高核验可靠性。

### MCP 工具
通过 Model Context Protocol 暴露的检索/抓取工具（[[mcp-tools]]），供 Search 阶段调用。

### token 预算池
全局共享的 token/成本预算，累计消耗超限即熔断后续调用，是成本治理的闸门。

### 弹性接缝 (resilience seam)
被指定**允许**做错误处理的少数边界：provider 调用、agent 输出校验、Journal IO、顶层 runner。此外一律 fail-loud。

### tracer-bullet
先拉一条最小端到端纵切让系统尽早可跑，再回各模块加厚的构建策略。

### 质量门 (quality gate)
模块/集成/系统三层的可执行验收闸门（见 `../guide/03-quality-gates.md`），检查功能是否成立并放行或拦截。

### 开放决策
模块规约 §9 中显式留给实现者自定的部分（签名、内部数据结构、算法细节）。
