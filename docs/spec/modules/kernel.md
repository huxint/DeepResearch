# kernel 规约 —— Workflow 编排内核

## 1 职责　（强）
提供 `agent` / `pipeline` / `parallel` 三个编排原语，以**确定性**方式组织子 Agent 执行。控制流由调用脚本驱动，模型只做单步推理；内核负责并发调度、Journal 缓存接入与结果聚合。

## 2 边界与非目标　（强）
- 不做 LLM 调用本身 —— 交给 [[subagent]]。
- 不做持久化 —— 缓存读写交给 [[journal]]。
- 不解析任何研究语义（什么是"子问题""引用"）—— 交给 [[pipeline]]。
- 不直接管 API Key —— 交给 [[provider-pool]]（经 [[subagent]] 间接使用）。

## 3 关键接口/契约　（中）
- `agent(prompt, *, schema?, model?) -> 结果`：派生一个子 Agent 做单步推理。给定 `schema` 则强制结构化输出，经 pydantic 校验后返回**校验对象**；否则返回文本。调用前先查 [[journal]]，命中即返回缓存、不实际调用。
- `pipeline(items, *stages) -> 结果[]`：每个条目独立穿过所有 stage，**阶段间无屏障**——条目 A 可在 stage 3 时条目 B 仍在 stage 1。某 stage 对某条目抛错→该条目后续 stage 跳过、结果降级为 `None`。
- `parallel(thunks) -> 结果[]`：屏障扇出，等全部完成后聚合返回。单个任务抛错降级为 `None`，**调用本身不抛**。

## 4 数据模型　（中）
- `AgentResult`：一次 agent 调用的产物（文本或校验对象 + token/耗时元数据）。
- `Stage`：阶段函数的类型别名（输入 → 输出，泛型）。
- 编排上下文：持有并发槽计数、可选的 phase 标签（用于日志归组）。

字段意图如上，精确定义见 §9。

## 5 不变式　（强）
1. pipeline 无屏障：条目 A 处于 stage 3 与条目 B 处于 stage 1 可同时成立。
2. 任一 `agent` 调用都**先查 [[journal]]**，命中即返回缓存。
3. 并发上限 = `min(16, cpu-2)`，超额调用排队等待空闲槽。
4. `parallel` 中单项抛错→该位置为 `None`，整个 `parallel` 调用不抛异常。

## 6 依赖　（强）
- 模块：[[subagent]]（执行体）、[[journal]]（缓存）。
- 库：标准库 `asyncio`（含 `TaskGroup`）。

## 7 失败语义　（中）
- `parallel` 单项失败 → 降级 `None`，不阻断其他项。
- `pipeline` 某 stage 对某条目抛错 → 该条目后续 stage 跳过、降级 `None`，其他条目不受影响。
- `agent` 的调用失败语义（重试/校验/预算）委托 [[subagent]]；内核不在此包防御性 try。

## 8 验收标准　（强）
- **given** 一个含多条目、多 stage 的 pipeline，**when** 各条目处理耗时不同，**then** 可观测到不同条目同时处于不同 stage（无屏障）。
- **given** 一组含一个会抛错的 thunk 的 parallel，**when** 执行，**then** 该位置为 `None` 且调用不抛、其余结果正常。
- **given** 超过并发上限的 agent 调用，**when** 执行，**then** 同时在跑的不超过 `min(16, cpu-2)`，其余排队。
- **given** 一个已在 [[journal]] 命中的 agent 调用，**when** 再次执行，**then** 直接返回缓存、不触发实际 [[subagent]] 调用。

## 9 开放决策　（——）
- 调度器内部用 `asyncio.Queue`、信号量还是 `TaskGroup` + Semaphore 组合。
- `agent` / `pipeline` / `parallel` 的精确泛型签名与 `Stage` 类型形态。
- 结果聚合所用的数据结构与顺序保证方式。
