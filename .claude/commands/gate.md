---
description: 跑指定层级（T1/T2/T3）的质量门并报告结果
---

# /gate <T1|T2|T3>

参数为层级，对应 `docs/guide/03-quality-gates.md`：

- **T1 模块门**：`pyright --strict` + 验收测试 + 不变式覆盖 + ruff + 防御性 try 审查。
- **T2 集成门**：tracer-bullet 端到端 + Journal 续跑 + 号池韧性。
- **T3 系统门**：引用门 / 评测门 / 成本门 / 时延门 / WebWalkerQA 回归。

跑完输出每项功能性检查的 pass/fail。
