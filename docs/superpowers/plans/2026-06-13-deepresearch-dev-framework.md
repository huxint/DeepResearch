# DeepResearch 开发引导文档框架 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 产出一套"开发引导文档框架"（~18 份 markdown + `.claude/` 适配层），使 AI 编码 agent 读了即能高质量、一致、可复现地实现 DeepResearch 系统。

**Architecture:** 方案 A 分层 Spec-Kit —— `docs/spec/`（WHAT，九段式模块规约×8 + PRD/术语/架构/横切）+ `docs/guide/`（HOW，开发循环/构建DAG/编码约定/质量门）+ `.claude/`（CC 驱动层，薄）。

**Tech Stack:** Markdown + Claude Code（CLAUDE.md / skills / commands）。被引导实现的目标系统栈为 Python 3.14 / asyncio / httpx / pydantic / SQLite / MCP，但本框架**不产出系统代码**。

**关于"测试"：** 本计划交付物是文档，无 pytest。每个任务的验证步骤是**结构/一致性检查**：grep 占位符为空、必需章节齐全、`[[module]]` 双链可解析。设计源文档：`docs/superpowers/specs/2026-06-13-deepresearch-dev-framework-design.md`。

---

### Task 1: 仓库脚手架 + 工具基线

**Files:**
- Create: `pyproject.toml`、`.gitignore`、目录树占位 `docs/spec/modules/.gitkeep`、`docs/guide/.gitkeep`、`.claude/skills/.gitkeep`、`.claude/commands/.gitkeep`

> 说明：本框架不写系统代码，但提供 `pyproject.toml`（工具配置骨架）是编码约定的**执行牙齿**——让 pyright/ruff/pytest 从第一天可跑。这是相对 spec §6 清单的一处刻意补充。

- [ ] **Step 1: 创建目录树与占位文件**

```bash
mkdir -p docs/spec/modules docs/guide .claude/skills .claude/commands
touch docs/spec/modules/.gitkeep docs/guide/.gitkeep .claude/skills/.gitkeep .claude/commands/.gitkeep
```

- [ ] **Step 2: 写 `pyproject.toml`（工具配置骨架，非系统代码）**

```toml
[project]
name = "deep-research"
version = "0.0.0"
description = "多智能体深度研究系统（由本框架引导实现）"
requires-python = ">=3.14"
dependencies = [
  "httpx>=0.27",
  "pydantic>=2.7",
  "mcp>=1.0",
]

[dependency-groups]
dev = ["pytest>=8", "pytest-asyncio>=0.23", "ruff>=0.5", "pyright>=1.1"]

[tool.pyright]
typeCheckingMode = "strict"
pythonVersion = "3.14"
reportMissingTypeStubs = false

[tool.ruff]
target-version = "py314"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "ASYNC"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 3: 写 `.gitignore`**

```gitignore
__pycache__/
*.py[cod]
.venv/
.pytest_cache/
.ruff_cache/
*.sqlite
.env
```

- [ ] **Step 4: 验证 pyproject 可解析**

Run: `python -c "import tomllib; tomllib.load(open('pyproject.toml','rb')); print('ok')"`
Expected: 输出 `ok`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .gitignore docs .claude
git commit -m "chore: 仓库脚手架与工具基线（pyright strict / ruff / pytest）"
```

---

### Task 2: `docs/spec/00-vision-prd.md`（愿景与 PRD）

**Files:** Create `docs/spec/00-vision-prd.md`

- [ ] **Step 1: 写文件，含以下章节与内容点**

必需 `##` 章节及内容：
1. **项目身份** —— 对标 OpenAI Deep Research 的开源实现；给定开放性问题，Plan→Search→Verify→Write 四阶段多 Agent 协同产出带引用研究报告。
2. **三大特点** —— 控制流确定 / 故障可恢复 / 成本可治理，各一句展开。
3. **目标 (Goals)** —— 确定性编排内核；多 Provider 号池抗限流；Journal 断点续跑；引用溯源核验；评测驱动。
4. **非目标 (Non-Goals)** —— 不做交互式多轮对话产品；不做图像/多模态子集；不追 no-GIL 构建；本仓库聚焦文本研究任务。
5. **成功指标（target，实测见质量门）** —— 表格：GAIA validation 文本子集准确率目标 51.2%（对照 HuggingFace open-deep-research 55.15%）；单题平均成本 ≤ \$0.18；引用错误率 < 3%（基线 17%）；并发扇出 16 路零中断；并行 vs 串行端到端时延降 ~60%；WebWalkerQA 持续回归。**标注：数字是目标值，质量门跑出实测值如实报告，绝不伪造。**
6. **技术栈与硬约束** —— Python 3.14 下限；asyncio / httpx / pydantic / SQLite / MCP。

- [ ] **Step 2: 验证无占位符且章节齐全**

Run: `grep -nE "TODO|TBD|FIXME|待补|XXX" docs/spec/00-vision-prd.md; echo "---"; grep -c "^## " docs/spec/00-vision-prd.md`
Expected: 第一段无输出（无占位符）；第二段计数 ≥ 6

- [ ] **Step 3: Commit**

```bash
git add docs/spec/00-vision-prd.md
git commit -m "docs(spec): 愿景与 PRD"
```

---

### Task 3: `docs/spec/01-glossary.md`（术语表/领域语言）

**Files:** Create `docs/spec/01-glossary.md`

- [ ] **Step 1: 写文件，每个术语一个 `###` 条目 + 一句定义**

必需术语：**Workflow 编排内核**、**agent 原语**、**pipeline 原语（无屏障）**、**parallel 原语（屏障扇出）**、**子 Agent (subagent)**、**多 Provider 号池**、**滑动窗口限流**、**熔断换道**、**Journal（断点续跑）**、**前缀命中缓存**、**四阶段（Plan/Search/Verify/Write）**、**引用溯源核验**、**多视角扇出**、**MCP 工具**、**token 预算池**、**弹性接缝 (resilience seam)**、**tracer-bullet**、**质量门 (quality gate)**。

- [ ] **Step 2: 验证无占位符 + 术语数**

Run: `grep -nE "TODO|TBD|FIXME" docs/spec/01-glossary.md; echo "---"; grep -c "^### " docs/spec/01-glossary.md`
Expected: 无占位符；条目数 ≥ 18

- [ ] **Step 3: Commit**

```bash
git add docs/spec/01-glossary.md && git commit -m "docs(spec): 术语表"
```

---

### Task 4: `docs/spec/02-architecture.md`（架构与数据流）

**Files:** Create `docs/spec/02-architecture.md`

- [ ] **Step 1: 写文件，含以下章节**

1. **组件图** —— ascii 框图：8 模块分层（地基 cross-cutting；单调用 provider-pool/journal/mcp-tools；执行单元 subagent/kernel；研究语义 verifier/pipeline；评测 eval），用 `[[module]]` 链向各规约。
2. **四阶段数据流** —— ascii：question → Plan(子问题) → Search(多路并行检索) → Verify(逐条引用溯源) → Write(带引用报告)。
3. **控制流确定性** —— 编排由脚本驱动、模型只做单步推理；pipeline 无屏障/parallel 屏障的取舍。
4. **三大特点如何落到组件** —— 确定性→kernel；可恢复→journal；可治理→provider-pool + token 预算池 + verifier。

- [ ] **Step 2: 验证无占位符 + 双链存在**

Run: `grep -nE "TODO|TBD|FIXME" docs/spec/02-architecture.md; echo "---"; grep -oE "\[\[[a-z-]+\]\]" docs/spec/02-architecture.md | sort -u`
Expected: 无占位符；列出 8 个模块双链

- [ ] **Step 3: Commit**

```bash
git add docs/spec/02-architecture.md && git commit -m "docs(spec): 架构与数据流"
```

---

### Task 5: `docs/spec/03-cross-cutting.md`（横切关注）

**Files:** Create `docs/spec/03-cross-cutting.md`

- [ ] **Step 1: 写文件，含以下章节**

1. **配置** —— provider/key 配置来源、env 加载、pydantic Settings 模型（字段意图，不写完整签名）。
2. **可观测** —— 结构化日志约定（每 agent 调用、每 provider 调用、阶段边界打点）。
3. **错误分类 (error taxonomy)** —— 可重试（429/超时/校验失败）vs 致命（配置缺失/全 key 不可用）；与异常处理纪律呼应。
4. **token 计费** —— 计费类型（每调用 token/成本累计）、共享预算池语义（超限熔断）。

- [ ] **Step 2: 验证无占位符 + 章节齐全**

Run: `grep -nE "TODO|TBD|FIXME" docs/spec/03-cross-cutting.md; echo "---"; grep -c "^## " docs/spec/03-cross-cutting.md`
Expected: 无占位符；计数 ≥ 4

- [ ] **Step 3: Commit**

```bash
git add docs/spec/03-cross-cutting.md && git commit -m "docs(spec): 横切关注"
```

---

### Task 6: 模块规约模板 + `docs/spec/modules/kernel.md`

**Files:** Create `docs/spec/modules/_TEMPLATE.md`、`docs/spec/modules/kernel.md`

- [ ] **Step 1: 写九段式模板 `_TEMPLATE.md`**

含 9 个 `##` 段标题与一行说明：`## 1 职责` / `## 2 边界与非目标` / `## 3 关键接口/契约` / `## 4 数据模型` / `## 5 不变式` / `## 6 依赖` / `## 7 失败语义` / `## 8 验收标准` / `## 9 开放决策`。每段附"约束强度（强/中/——）"标注与一句填写指引。

- [ ] **Step 2: 写 `kernel.md`（按九段式）**

- §1 职责：提供 agent/pipeline/parallel 三原语，确定性编排子 Agent；控制流由脚本驱动，模型只做单步推理。
- §2 边界：不做 LLM 调用本身（→ [[subagent]]）、不做持久化（→ [[journal]]）、不解析研究语义（→ [[pipeline]]）。
- §3 接口：`agent(prompt,*,schema?,model?)->结果`（给 schema 则强制结构化输出经 pydantic 校验返回校验对象，否则返回文本）；`pipeline(items,*stages)->结果[]`（条目独立穿过各阶段，阶段间无屏障）；`parallel(thunks)->结果[]`（屏障扇出聚合，单项抛错降级 None，调用本身不抛）。
- §4 数据模型：`AgentResult`、`Stage` 类型别名、编排上下文（并发槽、phase 标签）—— 字段意图，精确定义交 agent。
- §5 不变式：① pipeline 中条目 A 可处于 stage 3 而 B 仍在 stage 1；② 任一 agent 调用先查 Journal（[[journal]]），命中即返回缓存；③ 并发上限 `min(16, cpu-2)`，超额排队；④ parallel 单项抛错→None，调用不抛。
- §6 依赖：[[subagent]]、[[journal]]、cross-cutting；asyncio。
- §7 失败语义：parallel 单项失败→None；pipeline 某 stage 抛错→该 item 后续 stage 跳过降 None；agent 失败语义委托 [[subagent]]。
- §8 验收：构造多条目验证可异步穿越（不同 item 处于不同 stage）；parallel 屏障聚合；并发上限生效；journal 命中跳过执行。
- §9 开放决策：调度器实现（asyncio.Queue/信号量）、`Stage` 泛型签名、结果聚合数据结构。

- [ ] **Step 3: 验证九段齐全 + 双链 + 无占位符**

Run: `for s in 1 2 3 4 5 6 7 8 9; do grep -q "^## $s " docs/spec/modules/kernel.md || echo "缺第 $s 段"; done; grep -nE "TODO|TBD|FIXME" docs/spec/modules/kernel.md`
Expected: 无"缺第 N 段"、无占位符

- [ ] **Step 4: Commit**

```bash
git add docs/spec/modules/_TEMPLATE.md docs/spec/modules/kernel.md
git commit -m "docs(spec): 九段式模板 + kernel 规约"
```

---

### Task 7: `docs/spec/modules/provider-pool.md`

**Files:** Create `docs/spec/modules/provider-pool.md`（九段式）

- [ ] **Step 1: 写文件**

- §1 职责：多 provider + 多 key 池化，发起 LLM 调用，规避上游 RPM/并发限制，支撑 16 路扇出零中断。
- §2 边界：不做 prompt 组装/schema 校验（→ [[subagent]]）；不做编排（→ [[kernel]]）。
- §3 接口：`acquire()->选中 key`（最少并发优先 + 加权轮询）；`call(request)->response`；按 key 维度滑动窗口限流。
- §4 数据模型：`ProviderConfig`、`KeyState`（并发计数/窗口计数/熔断状态）、`LLMRequest`/`LLMResponse`。
- §5 不变式：最少并发优先调度；熔断中的 key 不被选中；滑窗限流不超配置 RPM。
- §6 依赖：cross-cutting（config、token 计费）；httpx。
- §7 失败语义（弹性接缝）：429/超时→熔断换道 + 指数退避重试；全 key 不可用→上抛致命错误。
- §8 验收：注入 429→换道继续；并发计数正确增减；滑窗限流到阈值阻塞；加权轮询分布符合权重。
- §9 开放决策：退避参数、熔断阈值/半开恢复策略、轮询权重算法、是否每 provider 独立 httpx client。

- [ ] **Step 2: 验证（同 Task 6 Step 3，替换文件名）**

Run: `for s in 1 2 3 4 5 6 7 8 9; do grep -q "^## $s " docs/spec/modules/provider-pool.md || echo "缺第 $s 段"; done; grep -nE "TODO|TBD|FIXME" docs/spec/modules/provider-pool.md`
Expected: 无"缺第 N 段"、无占位符

- [ ] **Step 3: Commit**

```bash
git add docs/spec/modules/provider-pool.md && git commit -m "docs(spec): provider-pool 规约"
```

---

### Task 8: `docs/spec/modules/journal.md`

**Files:** Create `docs/spec/modules/journal.md`（九段式）

- [ ] **Step 1: 写文件**

- §1 职责：每次 agent 调用以 (prompt, 参数) 哈希为键 append 写入 SQLite journal；resume 时未变更前缀命中缓存、仅重跑修改步骤。
- §2 边界：只管持久化与命中查询，不做业务编排（→ [[kernel]]）。
- §3 接口：`lookup(hash)->命中结果|空`；`append(hash, result)`；前缀命中语义说明。
- §4 数据模型：`JournalEntry`（hash、prompt 指纹、参数、结果、时间戳）。
- §5 不变式：写入幂等（同 hash 重复 append 不破坏命中）；append-only 不就地改写。
- §6 依赖：cross-cutting；sqlite3 / aiosqlite。
- §7 失败语义（弹性接缝）：SQLite IO 错误在此处理；其余调用方不包防御性 try。
- §8 验收：杀进程后 resume 命中未变更前缀、不重跑已完成步骤；变更某步参数后该步及其后失配重跑。
- §9 开放决策：哈希算法、表 schema、aiosqlite vs 线程池执行同步 sqlite。

- [ ] **Step 2: 验证**

Run: `for s in 1 2 3 4 5 6 7 8 9; do grep -q "^## $s " docs/spec/modules/journal.md || echo "缺第 $s 段"; done; grep -nE "TODO|TBD|FIXME" docs/spec/modules/journal.md`
Expected: 无"缺第 N 段"、无占位符

- [ ] **Step 3: Commit**

```bash
git add docs/spec/modules/journal.md && git commit -m "docs(spec): journal 规约"
```

---

### Task 9: `docs/spec/modules/subagent.md`

**Files:** Create `docs/spec/modules/subagent.md`（九段式）

- [ ] **Step 1: 写文件**

- §1 职责：子 Agent 执行单元 —— prompt 组装 → provider 调用 → pydantic 校验 → 失败带错误上下文重试 → token 预算扣减。
- §2 边界：不做编排（→ [[kernel]]）、不做缓存（→ [[journal]]）、不直接管 key（→ [[provider-pool]]）。
- §3 接口：`run(prompt,*,schema?,model?)->校验对象|文本`；schema 校验失败→重试时携带上一次错误上下文。
- §4 数据模型：`SubagentSpec`、校验错误上下文、`BudgetTicket`。
- §5 不变式：给定 schema 则输出必过 pydantic 校验才返回；超预算→熔断；重试有上限。
- §6 依赖：[[provider-pool]]、cross-cutting（token 预算池）。
- §7 失败语义（弹性接缝）：校验失败→带错误上下文重试至上限→上抛；预算超限→熔断。
- §8 验收：非法输出触发重试并最终通过或失败；预算耗尽触发熔断；合法 schema 对象正确返回。
- §9 开放决策：重试上限值、错误上下文注入 prompt 的格式、预算扣减时机（调用前预扣 vs 调用后结算）。

- [ ] **Step 2: 验证**

Run: `for s in 1 2 3 4 5 6 7 8 9; do grep -q "^## $s " docs/spec/modules/subagent.md || echo "缺第 $s 段"; done; grep -nE "TODO|TBD|FIXME" docs/spec/modules/subagent.md`
Expected: 无"缺第 N 段"、无占位符

- [ ] **Step 3: Commit**

```bash
git add docs/spec/modules/subagent.md && git commit -m "docs(spec): subagent 规约"
```

---

### Task 10: `docs/spec/modules/mcp-tools.md`

**Files:** Create `docs/spec/modules/mcp-tools.md`（九段式）

- [ ] **Step 1: 写文件**

- §1 职责：通过 MCP 集成检索/抓取工具（search/fetch），供 Search 阶段使用。
- §2 边界：不做编排、不做研究语义（→ [[pipeline]]）。
- §3 接口：`search(query)->结果[]`；`fetch(url)->内容`；MCP 客户端封装。
- §4 数据模型：`SearchHit`、`FetchedDoc`。
- §5 不变式：工具调用经 MCP 协议；超时受控。
- §6 依赖：cross-cutting；MCP Python SDK、httpx。
- §7 失败语义（弹性接缝）：网络/工具错误在此处理（超时/有限重试）。
- §8 验收：search 返回结构化结果；fetch 取回内容；超时配置生效。
- §9 开放决策：选用哪些 MCP server、结果规范化结构、是否做抓取去重。

- [ ] **Step 2: 验证**

Run: `for s in 1 2 3 4 5 6 7 8 9; do grep -q "^## $s " docs/spec/modules/mcp-tools.md || echo "缺第 $s 段"; done; grep -nE "TODO|TBD|FIXME" docs/spec/modules/mcp-tools.md`
Expected: 无"缺第 N 段"、无占位符

- [ ] **Step 3: Commit**

```bash
git add docs/spec/modules/mcp-tools.md && git commit -m "docs(spec): mcp-tools 规约"
```

---

### Task 11: `docs/spec/modules/verifier.md`

**Files:** Create `docs/spec/modules/verifier.md`（九段式）

- [ ] **Step 1: 写文件**

- §1 职责：对报告每条引用多视角扇出溯源核验，把引用错误率由 17% 降至 3% 以下。
- §2 边界：不做检索本身（→ [[mcp-tools]]）、不写报告（→ [[pipeline]] 的 Write）。
- §3 接口：`verify(claim, citation)->裁决`；多视角扇出借 [[kernel]] 的 parallel。
- §4 数据模型：`Citation`、`Verdict`（是否支持/置信度/视角）。
- §5 不变式：每条引用独立核验；多数视角判不支持→标记为引用错误。
- §6 依赖：[[kernel]]、[[mcp-tools]]。
- §7 失败语义：单视角失败降级（不阻断其他视角）。
- §8 验收：注入伪造引用→被标错；真实引用→通过；引用错误率指标可统计输出。
- §9 开放决策：视角数量与类型（原文比对/语义一致/来源可达）、裁决聚合阈值。

- [ ] **Step 2: 验证**

Run: `for s in 1 2 3 4 5 6 7 8 9; do grep -q "^## $s " docs/spec/modules/verifier.md || echo "缺第 $s 段"; done; grep -nE "TODO|TBD|FIXME" docs/spec/modules/verifier.md`
Expected: 无"缺第 N 段"、无占位符

- [ ] **Step 3: Commit**

```bash
git add docs/spec/modules/verifier.md && git commit -m "docs(spec): verifier 规约"
```

---

### Task 12: `docs/spec/modules/pipeline.md`

**Files:** Create `docs/spec/modules/pipeline.md`（九段式）

- [ ] **Step 1: 写文件**

- §1 职责：研究主流程脚本 —— Plan→Search→Verify→Write 四阶段确定性编排，产出带引用报告。
- §2 边界：不实现原语（→ [[kernel]]）、不实现检索/校验内部（→ [[mcp-tools]]/[[verifier]]）。
- §3 接口：`research(question)->带引用报告`；各阶段用 pipeline/parallel 表达；Search 多路并行检索。
- §4 数据模型：`Plan`（子问题列表）、`SearchResult`、`VerifiedClaim`、`Report`。
- §5 不变式：控制流确定；Search 多路并行；每条引用过 Verify 才进 Write。
- §6 依赖：[[kernel]]、[[subagent]]、[[mcp-tools]]、[[verifier]]。
- §7 失败语义：阶段失败委托各模块语义；顶层 runner（弹性接缝）兜底。
- §8 验收：给定问题端到端产出带引用报告；并行检索端到端时延 < 串行基线。
- §9 开放决策：阶段细分粒度、子问题分解策略、报告模板与引用标注格式。

- [ ] **Step 2: 验证**

Run: `for s in 1 2 3 4 5 6 7 8 9; do grep -q "^## $s " docs/spec/modules/pipeline.md || echo "缺第 $s 段"; done; grep -nE "TODO|TBD|FIXME" docs/spec/modules/pipeline.md`
Expected: 无"缺第 N 段"、无占位符

- [ ] **Step 3: Commit**

```bash
git add docs/spec/modules/pipeline.md && git commit -m "docs(spec): pipeline 规约"
```

---

### Task 13: `docs/spec/modules/eval.md`

**Files:** Create `docs/spec/modules/eval.md`（九段式）

- [ ] **Step 1: 写文件**

- §1 职责：基于 GAIA validation 文本子集自动评测（LLM-as-judge + 人工抽检）+ 单题成本核算 + WebWalkerQA 持续回归。
- §2 边界：不改系统行为，只评测（→ [[pipeline]] 是被测对象）。
- §3 接口：`run_eval(dataset)->{准确率, 单题平均成本}`；`judge(answer, gold)->对/错`。
- §4 数据模型：`EvalCase`、`EvalResult`（准确率/成本/逐题明细）。
- §5 不变式：judge 确定可复现；成本按 token 计费累计（[[provider-pool]] 计费）。
- §6 依赖：[[pipeline]]、[[provider-pool]]。
- §7 失败语义：单题失败记为错并继续，不中断整批。
- §8 验收：跑子集产出准确率 + 单题成本；judge 与人工抽检一致性可核对。
- §9 开放决策：judge prompt、人工抽检比例、GAIA 子集选取规则。

- [ ] **Step 2: 验证**

Run: `for s in 1 2 3 4 5 6 7 8 9; do grep -q "^## $s " docs/spec/modules/eval.md || echo "缺第 $s 段"; done; grep -nE "TODO|TBD|FIXME" docs/spec/modules/eval.md`
Expected: 无"缺第 N 段"、无占位符

- [ ] **Step 3: Commit**

```bash
git add docs/spec/modules/eval.md && git commit -m "docs(spec): eval 规约"
```

---

### Task 14: `docs/guide/00-operating-model.md`（确定性开发循环）

**Files:** Create `docs/guide/00-operating-model.md`

- [ ] **Step 1: 写文件，含以下章节**

1. **确定性开发循环** —— 代码块展示闭环：按 build-order DAG 取下一模块 → 读规约 → 写验收测试(TDD red) → 实现到通过(green) → 自验证+质量门 → 提交+更新状态表。
2. **开发即可续跑** —— 模块间无共享状态、按 DAG 解锁，中断后从下一个未完成模块接着跑，与 [[journal]] 同理。
3. **复用 superpowers，不重造** —— 表格映射：出规约→brainstorming（模块九段式模板）；出计划→writing-plans（喂 build-order DAG）；实现→test-driven-development（模块验收测试）；收尾→verification-before-completion（质量门）；合并前→requesting/receiving-code-review。

- [ ] **Step 2: 验证**

Run: `grep -nE "TODO|TBD|FIXME" docs/guide/00-operating-model.md; echo "---"; grep -c "^## " docs/guide/00-operating-model.md`
Expected: 无占位符；计数 ≥ 3

- [ ] **Step 3: Commit**

```bash
git add docs/guide/00-operating-model.md && git commit -m "docs(guide): 确定性开发循环"
```

---

### Task 15: `docs/guide/01-build-order.md`（构建顺序 DAG）

**Files:** Create `docs/guide/01-build-order.md`

- [ ] **Step 1: 写文件，含以下章节**

1. **依赖分波** —— 直接复刻设计文档 §4 的分波 ascii 图（Wave 0 cross-cutting；Wave 1 provider-pool/journal/mcp-tools 可并行；Wave 2 subagent/kernel；Wave 3 verifier/pipeline；Wave 4 eval），每行标依赖箭头与一句职责。
2. **Tracer-bullet 纵切** —— 复刻"配置→单 key provider→最小 subagent→最小 kernel→单 search→Plan/Search/Write（Verify stub）→粗糙带引用报告"路径，并说明"先打穿再加厚"。
3. **加厚顺序** —— 号池→Journal 续跑→Verifier 全量扇出→pipeline 无屏障优化→eval。
4. **构建状态表** —— 9 行（cross-cutting + 8 模块）× 列（依赖就绪/规约✓/测试✓/实现✓/质量门✓），全 `☐`。

- [ ] **Step 2: 验证状态表行数 + 无占位符**

Run: `grep -nE "TODO|TBD|FIXME" docs/guide/01-build-order.md; echo "---"; grep -c "☐" docs/guide/01-build-order.md`
Expected: 无占位符（注意 ☐ 是表格内容不算占位符）；`☐` 计数 = 45（9 行 × 5 列；首行 cross-cutting 依赖列若为 `—` 则 44，二者皆可）

- [ ] **Step 3: Commit**

```bash
git add docs/guide/01-build-order.md && git commit -m "docs(guide): 构建顺序 DAG + tracer-bullet + 状态表"
```

---

### Task 16: `docs/guide/02-coding-conventions.md`（编码约定）

**Files:** Create `docs/guide/02-coding-conventions.md`

- [ ] **Step 1: 写文件，含以下章节（异常处理纪律置于首位）**

1. **异常处理纪律（1 号规则）** ——
   - 错误处理只允许出现在"弹性接缝 (resilience seam)"：provider 调用（429/超时→熔断退避）、agent 输出校验（pydantic 失败→带错误上下文重试）、Journal IO、顶层 workflow runner；列明这四处。
   - 其余所有地方 fail-loud、零防御性 try；不 catch-log-swallow，不为类型/不变式已排除的情况加守卫，不给纯逻辑包 try。
   - 宁可响亮崩溃不静默降级（Journal 续跑让崩溃恢复成本近乎为零）。
   - 信任 pydantic 校验后的数据，校验过的边界内侧不重复检查。
2. **Python 版本** —— 硬下限 3.14；PEP 695 泛型贯穿内核、PEP 649 注解惰性求值利好 pydantic；不追 no-GIL 构建（纯 IO 密集、asyncio 单线程足够）。
3. **类型** —— `pyright --strict` 硬门、禁 `Any`、PEP 695 泛型、全边界 pydantic。
4. **并发** —— `asyncio.TaskGroup` 结构化并发，禁裸 `create_task`；httpx 连接池 + 显式超时/取消语义。
5. **布局/命名** —— src layout，模块边界对齐 [[kernel]] 等 `docs/spec/modules/`，统一命名约定。

- [ ] **Step 2: 验证含"弹性接缝"且无占位符**

Run: `grep -nE "TODO|TBD|FIXME" docs/guide/02-coding-conventions.md; echo "---"; grep -c "弹性接缝\|fail-loud\|TaskGroup" docs/guide/02-coding-conventions.md`
Expected: 无占位符；计数 ≥ 3

- [ ] **Step 3: Commit**

```bash
git add docs/guide/02-coding-conventions.md && git commit -m "docs(guide): 编码约定（异常处理纪律为首）"
```

---

### Task 17: `docs/guide/03-quality-gates.md`（三层质量门）

**Files:** Create `docs/guide/03-quality-gates.md`

- [ ] **Step 1: 写文件，含以下章节**

1. **T1 模块门** —— `pyright --strict` 零报错 · 验收测试(§8)全绿 · 不变式(§5)有测试覆盖 · ruff/format clean · 防御性 try 审查。
2. **T2 集成门** —— tracer-bullet 端到端产出带引用报告 · Journal 续跑（杀进程→命中缓存不重跑）· 号池韧性（注入 429/超时→熔断换道+退避+零中断扇出）。
3. **T3 系统门** —— 引用门 <3%（基线 17%）· 评测门 GAIA 准确率 ≥ 目标 51.2%（对照 55.15%）· 成本门 单题 ≤ \$0.18 · 时延门 并行 vs 串行降 ~60% · WebWalkerQA 回归。
4. **诚实原则** —— 数字是 target，门跑出 actual 如实报告；打不到是迭代项不是既成事实；绝不伪造指标。
5. **DoD（完成定义）** —— 所有模块状态表五列全勾 + T3 系统门实测值已记录。

- [ ] **Step 2: 验证**

Run: `grep -nE "TODO|TBD|FIXME" docs/guide/03-quality-gates.md; echo "---"; grep -c "^## " docs/guide/03-quality-gates.md`
Expected: 无占位符；计数 ≥ 5

- [ ] **Step 3: Commit**

```bash
git add docs/guide/03-quality-gates.md && git commit -m "docs(guide): 三层质量门 + DoD"
```

---

### Task 18: `CLAUDE.md`（项目宪法 / 适配层入口）

**Files:** Create `CLAUDE.md`

- [ ] **Step 1: 写文件，含以下章节**

1. **项目身份** —— 一句话 + 指向 `docs/spec/`、`docs/guide/`、构建状态表 `docs/guide/01-build-order.md` 的导航。
2. **置顶硬规则（编号列表）** ——
   1. 异常处理只在弹性接缝；其余 fail-loud、零防御性 try。
   2. `pyright --strict` / 禁 `Any` / 全边界 pydantic。
   3. `asyncio.TaskGroup` 结构化并发，禁裸 `create_task`。
   4. 改任何模块前先读其规约 §1–§9；不得违反 §5 不变式；不得在 §9 之外擅自收紧约束。
   5. 复用现成 superpowers 技能（TDD / writing-plans / verification），不重造。
3. **开发循环速记** —— 指向 `docs/guide/00-operating-model.md`，列出闭环五步。
4. **常用命令** —— 指向 `/build-next`、`/spec-check`、`/eval`、`/gate`。

- [ ] **Step 2: 验证含 5 条硬规则 + 导航链接**

Run: `grep -nE "TODO|TBD|FIXME" CLAUDE.md; echo "---"; grep -c "docs/spec\|docs/guide" CLAUDE.md`
Expected: 无占位符；导航引用计数 ≥ 2

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md && git commit -m "docs: CLAUDE.md 项目宪法（置顶硬规则）"
```

---

### Task 19: `.claude/commands/`（4 个 slash 命令）

**Files:** Create `.claude/commands/{build-next,spec-check,eval,gate}.md`

- [ ] **Step 1: 写四个命令文件（每个含 frontmatter `description` + 正文指引）**

- `build-next.md`：读 `docs/guide/01-build-order.md` 状态表，取下一个"依赖就绪但未完成"的模块，触发 `build-module` 技能走完确定性开发循环。
- `spec-check.md`：参数为模块名，对照 `docs/spec/modules/<name>.md` 的 §3 接口契约与 §5 不变式，检查当前实现是否符合并报告偏差。
- `eval.md`：跑 GAIA 子集评测门（[[eval]] 模块实现就绪后），报准确率与单题成本。
- `gate.md`：参数为层级（T1/T2/T3），跑对应质量门（见 `docs/guide/03-quality-gates.md`）。

- [ ] **Step 2: 验证四文件均有 frontmatter description**

Run: `for f in build-next spec-check eval gate; do head -3 .claude/commands/$f.md | grep -q "description" || echo "$f 缺 description"; done`
Expected: 无"缺 description"输出

- [ ] **Step 3: Commit**

```bash
git add .claude/commands/ && git commit -m "feat(cc): 4 个 slash 命令"
```

---

### Task 20: `.claude/skills/`（build-module / verify-citations）

**Files:** Create `.claude/skills/build-module/SKILL.md`、`.claude/skills/verify-citations/SKILL.md`

- [ ] **Step 1: 写两个技能（每个含 frontmatter `name` + `description` + 正文）**

- `build-module/SKILL.md`：取 DAG 下一模块 → 读其九段式规约 → 调用 `superpowers:writing-plans` 出实现计划 → 调用 `superpowers:test-driven-development` 实现 → 跑 T1 质量门 → 更新 `docs/guide/01-build-order.md` 状态表。强调"复用既有 superpowers 技能，不重造 TDD/计划/验证"。
- `verify-citations/SKILL.md`：独立运行引用溯源门 —— 对报告每条引用按 [[verifier]] 多视角扇出核验，统计并报告引用错误率，对照 <3% 目标门。

- [ ] **Step 2: 验证两技能 frontmatter 齐全**

Run: `for s in build-module verify-citations; do grep -q "^name:" .claude/skills/$s/SKILL.md && grep -q "^description:" .claude/skills/$s/SKILL.md || echo "$s frontmatter 不全"; done`
Expected: 无"frontmatter 不全"输出

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/ && git commit -m "feat(cc): build-module / verify-citations 技能"
```

---

### Task 21: 全局一致性验证 + 收尾

**Files:** 只读校验，无新文件

- [ ] **Step 1: 校验所有 `[[module]]` 双链可解析（指向存在的 modules/*.md）**

Run:
```bash
grep -rhoE "\[\[[a-z-]+\]\]" docs CLAUDE.md .claude 2>/dev/null | sort -u | sed -E 's/\[\[|\]\]//g' | while read m; do
  [ -f "docs/spec/modules/$m.md" ] || echo "悬空双链: [[$m]]"
done; echo "校验完成"
```
Expected: 仅输出"校验完成"（无"悬空双链"；注意 [[journal]]/[[kernel]] 等须对应真实文件）

- [ ] **Step 2: 全仓占位符扫描**

Run: `grep -rnE "TODO|TBD|FIXME|待补|占位符" docs CLAUDE.md .claude 2>/dev/null; echo "扫描完成"`
Expected: 仅输出"扫描完成"

- [ ] **Step 3: 模块清单一致性（8 个模块文件齐全）**

Run: `ls docs/spec/modules/*.md | grep -vE "_TEMPLATE" | wc -l`
Expected: 输出 `8`

- [ ] **Step 4: 产出清单核对**

Run: `ls CLAUDE.md docs/spec/*.md docs/spec/modules/*.md docs/guide/*.md .claude/commands/*.md .claude/skills/*/SKILL.md`
Expected: 列出全部交付文件（4 spec 前缀 + 8 模块 + 1 模板 + 4 guide + CLAUDE.md + 4 命令 + 2 技能）

- [ ] **Step 5: Commit（若前述校验触发了任何修正）**

```bash
git add -A && git commit -m "docs: 全局一致性校验通过（双链/占位符/清单）" --allow-empty
```

---

## 自检（Self-Review）

**Spec 覆盖：** 设计 §1 结构树 → Task 1/6/19/20 脚手架与目录；§2 九段式模板 → Task 6 `_TEMPLATE.md` + 各模块 Task 7-13；§3 HOW 层 → Task 14/16；§4 构建 DAG → Task 15；§5 质量门 → Task 17、`.claude` → Task 18-20；§6 产出清单 → Task 21 Step 4 核对；§7 非目标 → 体现在 PRD Task 2 与本计划范围。8 模块逐一有任务（Task 6-13）。无遗漏。

**占位符：** 各任务用枚举内容点而非"写合适内容"；验证步骤均给真实 grep 命令与期望。

**类型/命名一致性：** 模块文件名（kernel/provider-pool/journal/subagent/verifier/pipeline/mcp-tools/eval）在结构树、DAG、双链校验、产出核对四处一致；九段式段标题 `## N ...` 在模板与各模块及验证命令中一致。
