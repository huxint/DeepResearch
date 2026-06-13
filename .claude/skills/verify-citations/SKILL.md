---
name: verify-citations
description: 独立运行引用溯源门，对报告每条引用多视角扇出核验，找出不被来源支持的引用
---

# verify-citations

独立运行引用溯源门（不必整批评测）。实现机制见 `docs/spec/modules/verifier.md`（[[verifier]]）。

## 步骤

1. 取目标报告及其引用列表。
2. 对**每一条**引用，按 [[verifier]] 的多视角扇出（借 [[kernel]] 的 parallel）回到来源核验是否真正支持论断。
3. 聚合各视角分裁决为单条裁决（多数判不支持 → 标记为不被来源支持）。
4. 输出逐条不被来源支持的引用清单，确认引用核验确实生效。
