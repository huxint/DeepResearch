# DeepResearch 开发引导文档框架 — 设计

- **日期**：2026-06-13
- **状态**：已通过 brainstorming 评审，待用户审阅
- **作者**：huxint + Claude

---

## 0. 这份文档在定义什么

**交付物不是 DeepResearch 系统代码，而是一套"开发引导文档框架"**（spec-driven development）：一组平台无关的规约 + 一层 Claude Code 适配，使得任意 AI 编码 agent 读了这套文档，就能高质量、一致、可复现地把 DeepResearch 这个"多智能体深度研究系统"造出来。

目标产品 DeepResearch 的画像（来自简历，作为本框架要引导 agent 实现的对象）：

> 对标 OpenAI Deep Research 的开源实现。给定开放性问题，**Plan → Search → Verify → Write** 四阶段多 Agent 协同，产出**带引用的研究报告**。三大特点：**控制流确定、故障可恢复、成本可治理**。技术栈 Python / asyncio / httpx / pydantic / SQLite / MCP。

### 四个奠基决策（brainstorming 已敲定）

1. **核心交付物**：开发引导文档框架本身（不写系统代码）。
2. **承载形态**：平台无关 markdown 规约为**主体（核心资产）**，外加 Claude Code 适配层（CLAUDE.md / skills / commands）作为**驱动层**。
3. **约束强度**：**架构级中等约束** —— 给职责/边界/关键接口/不变式/验收，签名与内部实现留给 agent；并显式列出"开放决策"。
4. **覆盖范围**：**WHAT（造什么）+ HOW（怎么造）双层** —— 既规约产品，也规约 agent 的开发操作模型。

### 跨切约定

- **文档语言**：中文为主，技术术语用英文；代码标识符/文件名/目录名用英文。
- **简历指标作为"目标值(target)"**写入 PRD 与质量门（GAIA 51.2%、对照 open-deep-research 55.15%、单题 \$0.18、引用错误率 <3%、16 路扇出、时延降 ~60%），由质量门跑出"实测值(actual)"如实报告，**绝不伪造**。

---

## 1. 框架整体结构

采用**方案 A：分层 Spec-Kit**（并以纯文档形式吸收"构建顺序用显式依赖图表达"的思路）。

```
DeepResearch/
├── CLAUDE.md                      # 适配层入口：项目宪法，告诉 agent 如何在本框架下工作
├── docs/
│   ├── spec/                      # ── WHAT 层（产品规约，平台无关）
│   │   ├── 00-vision-prd.md          # 愿景/目标/非目标/成功指标
│   │   ├── 01-glossary.md            # 术语表/领域语言
│   │   ├── 02-architecture.md        # 组件图 + 数据流 + 四阶段流水
│   │   ├── 03-cross-cutting.md       # 配置/可观测/错误分类/token 计费
│   │   └── modules/                  # 各子系统架构级规约（九段式）
│   │       ├── kernel.md                # Workflow 编排内核（agent/pipeline/parallel）
│   │       ├── provider-pool.md         # 多 Provider 号池
│   │       ├── journal.md               # SQLite 断点续跑
│   │       ├── subagent.md              # 子 Agent 框架（schema 校验/重试/预算池）
│   │       ├── verifier.md              # 引用溯源多视角核验
│   │       ├── pipeline.md              # 研究主流程（Plan→Search→Verify→Write）
│   │       ├── mcp-tools.md             # MCP 检索/抓取工具集成
│   │       └── eval.md                  # GAIA 评测 + 成本核算 + 回归
│   └── guide/                     # ── HOW 层（开发操作模型，平台无关）
│       ├── 00-operating-model.md     # 确定性开发循环
│       ├── 01-build-order.md         # 构建顺序依赖图 + tracer-bullet + 状态表
│       ├── 02-coding-conventions.md  # Python/asyncio/httpx/pydantic/SQLite 约定
│       └── 03-quality-gates.md       # 三层质量门 + DoD
└── .claude/                       # ── CC 适配层（驱动层，薄）
    ├── skills/                       # build-module / verify-citations
    └── commands/                     # /build-next、/spec-check、/eval、/gate
```

三层职责：`docs/spec/` = **造什么**（架构级）；`docs/guide/` = **怎么造**（确定性开发纪律 + 构建顺序 + 约定 + 质量门）；`.claude/` = **驱动**（读了即按规约与纪律开工，复用现成 superpowers 技能而非重造）。

---

## 2. 模块规约模板（九段式）

`docs/spec/modules/*.md` 每份用同一套九段式骨架，压在"架构级中等约束"线上。模块之间用 `[[module]]` 双链交叉引用。

| 段 | 内容 | 约束强度 |
|---|---|---|
| 1 职责 | 一段话，单一目的 | 强（钉死） |
| 2 边界/非目标 | 明确**不做**什么、在哪交棒给别的模块 | 强 |
| 3 关键接口/契约 | 公开操作的**语义**（名字、输入产出、行为），**不写完整签名** | 中 |
| 4 数据模型 | 该模块拥有的关键 pydantic 模型（字段名+类型意图），精确定义交给 agent | 中 |
| 5 不变式 | 永远成立的性质 | 强 |
| 6 依赖 | 依赖哪些模块/库（汇成构建顺序 DAG） | 强 |
| 7 失败语义 | 错误如何传播、重试/熔断在契约层的行为 | 中 |
| 8 验收标准 | given/when/then 可测条件，挂质量门 | 强 |
| 9 开放决策 | **显式列出**留给 agent 自定的东西（签名、内部数据结构、算法细节） | —— |

第 9 段是"中等约束可控"的来源：把"什么钉死、什么放开"摊开写明。

### 示例片段（`kernel.md` 节选）

> **3 关键接口**　`agent(prompt, *, schema?, model?) -> 结果`：派生子 Agent 做单步推理；给了 `schema` 则强制结构化输出并经 pydantic 校验后返回校验对象，否则返回文本。`pipeline(items, *stages) -> 结果[]`：每个条目独立穿过所有阶段，**阶段间无屏障**。`parallel(thunks) -> 结果[]`：屏障扇出，全部完成后聚合；单个抛错降级为 `None`，调用本身不抛。
> **5 不变式**　① pipeline 中条目 A 可处于 stage 3 而条目 B 仍在 stage 1；② 任一 `agent` 调用都先查 Journal，命中即返回缓存（见 [[journal]]）；③ 并发上限 = `min(16, cpu-2)`，超额排队。
> **9 开放决策**　调度器内部用 asyncio.Queue 还是信号量、`Stage` 的具体泛型签名、结果聚合的数据结构 —— 由实现者定。

---

## 3. HOW 层：确定性开发循环 + 编码约定

### 3.A 确定性开发循环（`guide/00-operating-model.md`）

镜像产品哲学（控制流确定、每模块即检查点、可续跑）。每模块走同一闭环：

```
按 build-order DAG 取下一个模块
   → 读其规约 → 写验收测试 (TDD red)
   → 实现到测试通过 (green)
   → 自验证 + 质量门 (pyright --strict / 阶段性引用门 / 评测门)
   → 提交 + 更新构建状态表
```

模块间无共享状态、按 DAG 解锁，故中断后从"下一个未完成模块"接着跑——开发过程本身可断点续跑，与 Journal 同理。

### 3.B 复用 superpowers，不重造（`.claude/` 适配层）

HOW 层只定义 DeepResearch 专属物，通用纪律挂现成技能：

| 阶段 | 复用的现成技能 | 框架只补充 |
|---|---|---|
| 出规约 | `brainstorming` | 模块九段式模板 |
| 出计划 | `writing-plans` | 把 build-order DAG 喂进去 |
| 实现 | `test-driven-development` | 模块验收测试约定 |
| 收尾 | `verification-before-completion` | DeepResearch 质量门 |
| 合并前 | `requesting/receiving-code-review` | —— |

### 3.C 编码约定（`guide/02-coding-conventions.md`）

**异常处理纪律（1 号规则，置顶 CLAUDE.md，对抗模型过度谨慎）：**

- 错误处理**只允许出现在"弹性接缝 (resilience seams)"**：provider 调用（429/超时→熔断退避）、agent 输出校验（pydantic 失败→带错误上下文重试）、Journal IO、顶层 workflow runner。**这几处正是简历强调的韧性点，错误处理集中于此才显价值。**
- 其余所有地方：**fail-loud，零防御性 try**。不 catch-log-swallow，不为"类型/不变式已排除的情况"加守卫，不给纯逻辑包 try。
- **宁可响亮崩溃，不静默降级** —— 因为 Journal 续跑让崩溃恢复成本近乎为零，防御性 fallback 反而掩盖 bug。
- 信任 pydantic 校验后的数据，**校验过的边界内侧不再重复检查**。

**其余约定：**

- **Python 版本**：硬下限 **Python 3.14**（PEP 695 泛型贯穿内核、PEP 649 注解惰性求值利好 pydantic、错误信息更好）。**不追自由线程(no-GIL)构建** —— 纯 IO 密集、asyncio 单线程足够，走标准构建避免生态兼容风险。
- **类型**：`pyright --strict` 硬门、禁 `Any`、PEP 695 泛型、全边界 pydantic。
- **并发**：`asyncio.TaskGroup` 结构化并发，禁裸 `create_task` 泄漏；httpx 连接池 + 显式超时/取消语义。
- **布局/命名**：src layout，模块边界对齐 `docs/spec/modules/`，统一命名约定。

> **为何 Python 是此项目最优解**：系统纯 IO 密集（16 路扇出全程等 LLM/检索 API），GIL 与解释器性能均不构成瓶颈；而 pydantic（结构化输出事实标准）、MCP Python SDK、LLM provider SDK、GAIA/评测工具链、对照基线 open-deep-research 全为 Python-first。换语言要付生态代价却在真正瓶颈上一无所获。

---

## 4. 构建顺序 DAG（`guide/01-build-order.md`）

依赖关系由各模块规约"§6 依赖"汇成；本文件给拓扑视图 + tracer-bullet 纵切 + 构建状态表。

### 依赖分波

```
Wave 0  地基
  cross-cutting        config / 结构化日志 / 错误分类 / token 计费类型   (无内部依赖)

Wave 1  单调用能力 ───────── 三者可并行
  provider-pool ─▶ cross-cutting     先做"单 provider 单 key 能发请求"，调度/限流/熔断留接口
  journal       ─▶ cross-cutting     SQLite append + hash 键 + 命中查询
  mcp-tools     ─▶ cross-cutting     一个 search + 一个 fetch

Wave 2  Agent 执行单元 + 编排原语
  subagent      ─▶ provider-pool, cross-cutting   prompt 组装→调用→pydantic 校验→带上下文重试→预算扣减
  kernel        ─▶ subagent, journal              agent 原语=journal 缓存+subagent 执行；pipeline 无屏障；parallel 屏障；并发上限 min(16,cpu-2)

Wave 3  研究语义
  verifier      ─▶ kernel, mcp-tools              多视角扇出 + 逐条引用溯源
  pipeline      ─▶ kernel, subagent, mcp-tools, verifier   Plan→Search→Verify→Write 主流程脚本

Wave 4  评测闭环
  eval          ─▶ pipeline, provider-pool        GAIA 子集 + LLM-as-judge + 成本核算 + 回归
```

### Tracer-bullet：先打穿，再加厚

**不按波次逐个做完**，先拉最小纵切让系统尽早端到端可跑：

```
配置 → 单 key provider → 最小 subagent(单 schema) → 最小 kernel(只 agent+parallel)
     → 单 search 工具 → Plan / Search / Write 三段(Verify 先 stub)
     → 对一道题产出"粗糙但带引用"的报告 ✅ 端到端打通
```

打通后再回各模块**加厚**：号池（多 key / 滑窗限流 / 429 熔断换道 / 指数退避）→ Journal 续跑 → Verifier 全量多视角扇出 → pipeline 无屏障流水优化 → eval 评测门。"60% 时延 / 引用门 / 评测门"等指标在有可跑基线后才量、才优化。

### 构建状态表（文件内维护，驱动续跑）

| 模块 | 依赖就绪 | 规约✓ | 测试✓ | 实现✓ | 质量门✓ |
|---|---|---|---|---|---|
| cross-cutting | — | ☐ | ☐ | ☐ | ☐ |
| provider-pool | ☐ | ☐ | ☐ | ☐ | ☐ |
| journal | ☐ | ☐ | ☐ | ☐ | ☐ |
| mcp-tools | ☐ | ☐ | ☐ | ☐ | ☐ |
| subagent | ☐ | ☐ | ☐ | ☐ | ☐ |
| kernel | ☐ | ☐ | ☐ | ☐ | ☐ |
| verifier | ☐ | ☐ | ☐ | ☐ | ☐ |
| pipeline | ☐ | ☐ | ☐ | ☐ | ☐ |
| eval | ☐ | ☐ | ☐ | ☐ | ☐ |

---

## 5. 质量门 + `.claude/` 适配层

### 5.A 质量门三层（`guide/03-quality-gates.md`）

| 层 | 触发时机 | 门 |
|---|---|---|
| **T1 模块门** | 每模块收尾 | `pyright --strict` 零报错 · 验收测试(§8)全绿 · 不变式(§5)有测试覆盖 · ruff/format clean · **防御性 try 审查** |
| **T2 集成门** | 波次边界 | tracer-bullet 端到端产出带引用报告 · Journal 续跑(杀进程→命中缓存不重跑) · 号池韧性(注入 429/超时→熔断换道+退避+零中断扇出) |
| **T3 系统门** | 系统成型后 | **引用门** 错误率<3%(基线17%) · **评测门** GAIA 准确率≥目标 51.2%(对照 55.15%) · **成本门** 单题≤\$0.18 · **时延门** 并行 vs 串行降~60% · WebWalkerQA 回归 |

> **诚实原则**：简历数字是"目标值(target)"，门负责跑出"实测值(actual)"并如实报告。打不到就是迭代项，不是既成事实——绝不伪造指标。

### 5.B `.claude/` 适配层（驱动层，**薄** —— 规约才是资产）

**`CLAUDE.md`（项目宪法，置顶硬规则）**
1. 异常处理只在弹性接缝；其余 fail-loud、零防御性 try
2. `pyright --strict` / 禁 `Any` / 全边界 pydantic
3. `asyncio.TaskGroup` 结构化并发，禁裸 `create_task`
4. **改任何模块前先读其规约 §1–§9；不得违反 §5 不变式；不得在 §9 之外擅自收紧约束**
5. 复用现成 superpowers 技能，不重造
6. 导航：指向 `docs/spec`、`docs/guide`、构建状态表

**`.claude/skills/`**（薄，包住通用技能）
- `build-module`：取 DAG 下一模块 → 读规约 → 调 `writing-plans` → TDD → 质量门 → 更新状态表
- `verify-citations`：独立跑引用溯源门

**`.claude/commands/`**（薄包装）
- `/build-next`（触发 build-module）· `/spec-check <module>`（校验实现 vs §3 契约/§5 不变式）· `/eval`（GAIA 子集，报准确率+成本）· `/gate <tier>`（跑某层门）

---

## 6. 本框架的产出清单（实现本设计时要创建的文件）

- `CLAUDE.md`
- `docs/spec/{00-vision-prd,01-glossary,02-architecture,03-cross-cutting}.md`
- `docs/spec/modules/{kernel,provider-pool,journal,subagent,verifier,pipeline,mcp-tools,eval}.md`（各按九段式）
- `docs/guide/{00-operating-model,01-build-order,02-coding-conventions,03-quality-gates}.md`
- `.claude/skills/{build-module,verify-citations}/`
- `.claude/commands/{build-next,spec-check,eval,gate}.md`

> 注意：本框架**不产出** DeepResearch 的 Python 系统代码。系统代码由后续 agent **在本框架引导下**实现。

---

## 7. 非目标（YAGNI）

- 不在本框架内实现 DeepResearch 系统代码。
- `.claude/` 适配层保持薄：只做 DeepResearch 专属 glue，不重造 TDD/计划/验证等通用能力。
- 不追求把模块规约写到"接口签名级"——保持架构级中等约束，签名/内部实现交给实现者。
- 不引入自由线程(no-GIL) Python 构建。
