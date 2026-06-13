# 愿景与 PRD

## 项目身份

DeepResearch 是对标 OpenAI Deep Research 的开源实现。给定一个开放性问题，系统以 **Plan → Search → Verify → Write** 四阶段、多 Agent 协同的方式工作，最终产出一份**带引用的研究报告**。它不是聊天机器人，而是一条把"问题"确定性地编排成"可溯源报告"的流水线。

## 三大特点

- **控制流确定**：编排由脚本（[[kernel]] 的 agent / pipeline / parallel 三原语）驱动，模型只负责单步推理，不负责决定下一步走向。同样的输入与脚本得到同样的执行结构。
- **故障可恢复**：每次 agent 调用以 (prompt, 参数) 哈希为键写入 [[journal]]；任务中断后 resume 直接命中未变更前缀的缓存，仅重跑修改步骤，长任务失败的恢复成本近乎为零。
- **成本可治理**：[[provider-pool]] 池化多 Provider/多 Key 抗上游限流，共享 token 预算池超限熔断，[[verifier]] 对每条引用溯源核验，让质量与花费都在可观测、可设限的范围内。

## 目标 (Goals)

- 自研零框架依赖的 **Workflow 编排内核**（[[kernel]]），以 agent / pipeline / parallel 表达确定性编排。
- **多 Provider 号池**（[[provider-pool]]）：最少并发优先 + 加权轮询调度、按 Key 滑动窗口限流、429/超时熔断换道与指数退避，支撑多路子 Agent 并发扇出不中断。
- **Journal 断点续跑**（[[journal]]）：哈希键 append-only 缓存，resume 命中未变更前缀。
- **引用溯源核验**（[[verifier]]）：多视角扇出对每条引用核验，过滤掉不被来源支持的引用。
- **评测驱动**（[[eval]]）：能在 GAIA 文本子集等数据集上端到端跑出结果，便于回归。

## 非目标 (Non-Goals)

- 不做交互式多轮对话产品；输入是一个开放性问题，输出是一份报告。
- 不做图像/音视频多模态任务；聚焦 GAIA validation 的**文本子集**。
- 不追求自由线程（no-GIL）Python 构建；系统纯 IO 密集，asyncio 单线程足够。
- 本仓库不实现"通用 Agent 平台"，只实现深度研究这一条垂直流水线。

## 成功标准（功能性）

> 本项目以**做出能用的系统**为目标，不以任何指标数字为开发目标。下列是"算不算做成了"的功能性判断：

- 给定一个开放性问题，能端到端走完 Plan→Search→Verify→Write，产出一份**带引用的报告**。
- 报告里的引用都经过 [[verifier]] 核验，不被来源支持的引用会被过滤。
- 长任务中断后能**断点续跑**（[[journal]]），不从头再来。
- 号池（[[provider-pool]]）在上游限流/报错时能熔断换道、重试，**多路并发扇出不中断**。
- 能在 GAIA 文本子集等数据集上端到端跑出结果，便于回归（[[eval]]）。

## 技术栈与硬约束

- **Python 3.14** 为硬下限（PEP 695 泛型、PEP 649 注解惰性求值）。
- 运行时：`asyncio` / `httpx` / `pydantic` / `SQLite` / `MCP`。
- 编码硬约束见 `../guide/02-coding-conventions.md`（异常处理只在弹性接缝、`pyright --strict`、结构化并发）。
