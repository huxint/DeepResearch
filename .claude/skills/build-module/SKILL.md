---
name: build-module
description: 取构建 DAG 下一模块，读其九段式规约，复用 superpowers 技能走完确定性开发循环并更新状态表
---

# build-module

对单个模块走完确定性开发循环（见 `docs/guide/00-operating-model.md`）。**复用现成 superpowers 技能，不重造 TDD / 计划 / 验证。**

## 步骤

1. **选模块**：读 `docs/guide/01-build-order.md` 状态表，取第一个依赖就绪且未完成的模块（或用户指定的模块）。
2. **读规约**：读 `docs/spec/modules/<module>.md` 全部 §1–§9，记牢 §5 不变式与 §8 验收标准、§9 开放决策边界。
3. **出计划**：调用 `superpowers:writing-plans`，把 §8 验收标准转成 bite-sized 实现计划。
4. **实现**：调用 `superpowers:test-driven-development`，按 §8 写验收测试（red）→ 实现到通过（green）。遵守 `docs/guide/02-coding-conventions.md`，尤其异常处理只在弹性接缝。
5. **T1 质量门**：调用 `superpowers:verification-before-completion`，跑 `pyright --strict` + 测试 + ruff + 防御性 try 审查（见 `docs/guide/03-quality-gates.md`）。
6. **收尾**：勾掉 `docs/guide/01-build-order.md` 状态表对应行的格子并提交。

## 约束

- 不违反规约 §5 不变式。
- 不在 §9 开放决策之外擅自收紧约束。
