---
description: 取构建状态表里下一个依赖就绪且未完成的模块，触发 build-module 技能走完确定性开发循环
---

# /build-next

1. 读 `docs/guide/01-build-order.md` 的构建状态表。
2. 找出第一个**依赖已就绪、但本行未全部勾选**的模块。
3. 调用 `build-module` 技能（`.claude/skills/build-module/`）对该模块走完开发循环：读九段式规约 → writing-plans → TDD → T1 质量门 → 更新状态表。
4. 若所有模块均已完成，报告"全部模块完成"，并提示按 `docs/guide/03-quality-gates.md` 跑 T2/T3 门。
