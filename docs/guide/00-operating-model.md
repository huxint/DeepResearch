# 确定性开发循环（Operating Model）

本框架不仅规约"造什么"，也规约"怎么造"。开发过程本身镜像产品哲学：**控制流确定、每模块即检查点、可断点续跑**。

## 确定性开发循环

每个模块都走同一个闭环：

```
1. 按构建顺序 DAG 取下一个"依赖已就绪且未完成"的模块   （见 01-build-order.md）
2. 读其九段式规约（§1–§9），写验收测试                  （TDD red）
3. 实现到验收测试通过                                   （TDD green）
4. 自验证 + 跑 T1 质量门（pyright --strict / 测试 / 不变式 / 防御性 try 审查）
5. 提交 + 在 01-build-order.md 状态表里勾掉对应格子
```

不在 §9"开放决策"之外擅自收紧约束；不违反 §5 不变式。

## 开发即可续跑

模块之间**无共享状态**、只按 DAG 的依赖关系解锁。任何时候中断，下次从"状态表里下一个依赖就绪但未完成的模块"接着开工即可——这与 [[journal]] 给运行时带来的断点续跑同构：开发流程也有自己的"journal"（状态表）。

## 复用 superpowers，不重造

HOW 层只定义 DeepResearch 专属的东西，通用开发纪律一律挂现成 superpowers 技能：

| 阶段 | 复用的现成技能 | 本框架只补充 |
|---|---|---|
| 出规约 | `superpowers:brainstorming` | 模块九段式模板（`../spec/modules/_TEMPLATE.md`） |
| 出计划 | `superpowers:writing-plans` | 把构建顺序 DAG 喂进去 |
| 实现 | `superpowers:test-driven-development` | 模块验收测试约定（来自各模块 §8） |
| 收尾 | `superpowers:verification-before-completion` | DeepResearch 三层质量门（`03-quality-gates.md`） |
| 合并前 | `superpowers:requesting-code-review` / `receiving-code-review` | —— |

落地驱动见 `.claude/skills/build-module/` 与 `.claude/commands/build-next.md`。
