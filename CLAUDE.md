# CLAUDE.md —— DeepResearch 项目宪法

DeepResearch 是对标 OpenAI Deep Research 的多智能体深度研究系统：给定开放性问题，经 Plan→Search→Verify→Write 四阶段产出带引用报告。**控制流确定、故障可恢复、成本可治理。**

本仓库按"开发引导文档框架"组织。动手前先读：

- **造什么**：`docs/spec/`（PRD、术语表、架构、横切；`docs/spec/modules/` 下 8 份九段式模块规约）。
- **怎么造**：`docs/guide/`（开发循环、构建顺序、编码约定、质量门）。
- **当前进度**：`docs/guide/01-build-order.md` 的构建状态表。

## 置顶硬规则（不可违反）

1. **异常处理只在弹性接缝**（provider 调用 / agent 输出校验 / Journal IO / 顶层 runner），其余一律 **fail-loud、零防御性 try**；宁可响亮崩溃不静默降级。详见 `docs/guide/02-coding-conventions.md`。
2. **`pyright --strict` / 禁 `Any` / 全边界 pydantic。**
3. **`asyncio.TaskGroup` 结构化并发，禁裸 `asyncio.create_task`。**
4. **改任何模块前先读其规约 §1–§9**；不得违反 §5 不变式；不得在 §9"开放决策"之外擅自收紧约束。
5. **复用现成 superpowers 技能**（test-driven-development / writing-plans / verification-before-completion），**不重造** TDD/计划/验证。

## 开发循环（速记）

详见 `docs/guide/00-operating-model.md`：

```
取 DAG 下一模块 → 读规约写验收测试(red) → 实现到通过(green)
→ 自验证 + T1 质量门 → 提交 + 勾状态表
```

## 常用命令

- `/build-next` —— 取构建状态表里下一个依赖就绪的模块，走完开发循环。
- `/spec-check <module>` —— 校验实现是否符合该模块 §3 接口契约 / §5 不变式。
- `/eval` —— 在数据集上端到端评测，报告逐题对错与结果。
- `/gate <T1|T2|T3>` —— 跑对应层质量门（见 `docs/guide/03-quality-gates.md`）。
