# journal 规约 —— SQLite 断点续跑

## 1 职责　（强）
把每次 agent 调用以 (prompt, 参数) 的哈希为键、append-only 写入 SQLite journal。resume 时，未变更的调用前缀直接命中缓存返回，仅从第一个变更步骤起重跑，使长任务失败后的恢复成本近乎为零。

## 2 边界与非目标　（强）
- 只管持久化与命中查询，不做任何业务编排 —— 交给 [[kernel]]。
- 不决定"什么时候查缓存" —— 由 [[kernel]] 的 `agent` 原语在调用前调用本模块。

## 3 关键接口/契约　（中）
- `lookup(hash) -> 命中结果 | 空`：按键查缓存，命中返回此前记录的结果。
- `append(hash, result)`：把一次调用结果追加写入。
- 前缀命中语义：脚本前缀未变更 → 其每一步的 hash 不变 → 逐步命中；某步参数变更后 hash 失配 → 该步及其后重跑。

## 4 数据模型　（中）
- `JournalEntry`：`hash`、prompt 指纹、调用参数、结果载荷、时间戳。

## 5 不变式　（强）
1. 写入幂等：同一 `hash` 重复 `append` 不破坏后续 `lookup` 的命中正确性。
2. append-only：不就地改写历史记录。

## 6 依赖　（强）
- 模块：cross-cutting（config）。
- 库：`sqlite3` / `aiosqlite`（见 §9）。

## 7 失败语义（弹性接缝）　（中）
- SQLite 的 IO 错误在本模块内处理（本模块是允许做错误处理的接缝之一）。
- 调用方（[[kernel]]）不为缓存读写包防御性 try。

## 8 验收标准　（强）
- **given** 一个完整跑过的任务，**when** 杀掉进程后 resume，**then** 未变更前缀逐步命中缓存、不重复实际调用。
- **given** 某中间步骤的参数被修改，**when** resume，**then** 该步 hash 失配、该步及其后续步骤重跑，之前步骤仍命中。
- **given** 同一 hash 被 append 两次，**when** lookup，**then** 仍能正确命中。

## 9 开放决策　（——）
- 哈希算法（如 sha256）与 prompt/参数的规范化方式。
- 表结构 schema 与索引设计。
- 用 `aiosqlite` 异步，还是在线程池里跑同步 `sqlite3`。
