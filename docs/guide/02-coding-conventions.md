# 编码约定

被引导实现的系统是 Python 3.14 / asyncio。本约定是质量门 T1 的依据，也是对抗"模型过度谨慎写出冗余代码"的硬规则。

## 1. 异常处理纪律（1 号规则）

**核心原则：错误处理只允许出现在"弹性接缝 (resilience seam)"，其余一律 fail-loud、零防御性 try。**

允许做错误处理的弹性接缝只有四处：

1. **provider 调用** —— 429/超时 → 熔断换道 + 指数退避（[[provider-pool]]）。
2. **agent 输出校验** —— pydantic 校验失败 → 带错误上下文重试（[[subagent]]）。
3. **Journal IO** —— SQLite 读写错误（[[journal]]）。
4. **顶层 workflow runner** —— 捕获致命错误、记录、终止任务（[[pipeline]]）。

除此之外：

- **不给纯逻辑包 try**；不为"类型/不变式已经排除的情况"加防御性守卫。
- **不 catch-log-swallow**，不 catch-and-reraise，不 catch-and-return-降级默认值。
- **宁可响亮崩溃，不静默降级** —— [[journal]] 续跑让崩溃恢复成本近乎为零，防御性 fallback 只会掩盖 bug。
- **信任 pydantic 校验后的数据**：校验过的边界内侧不再重复检查字段是否存在/类型是否正确。

> 评审清单项：若一处 try/except 不在上述四个接缝内，默认它是多余的，删掉或上抛。

## 2. Python 版本

- 硬下限 **Python 3.14**。
- 用 **PEP 695** 泛型语法写编排内核（`def agent[T](...) -> T`、`type Stage[I, O] = ...`），让类型流可被 pyright 全程追踪。
- **PEP 649** 注解惰性求值默认开启：pydantic 模型与前向引用开箱即用，无需 `from __future__ import annotations` 或字符串引号。
- **不追自由线程（no-GIL）构建**：系统纯 IO 密集、asyncio 单线程足够，走标准构建避免生态兼容风险。

## 3. 类型

- `pyright --strict` 为硬门，零报错才算通过 T1。
- **禁 `Any`**（确需逃逸时用 `object` + 显式 narrow，并写明理由）。
- 全边界用 pydantic：Agent 输入输出、配置、Journal 记录、工具结果。

## 4. 并发

- 统一用 `asyncio.TaskGroup`（结构化并发）。**禁裸 `asyncio.create_task`** 导致的任务泄漏。
- `httpx` 用连接池复用，所有外呼显式设置超时；取消语义随 TaskGroup 传播。

## 5. 布局与命名

- src layout（`src/deep_research/...`）。
- 代码模块边界对齐 `../spec/modules/`：[[kernel]]、[[provider-pool]]、[[journal]]、[[subagent]]、[[mcp-tools]]、[[verifier]]、[[pipeline]]、[[eval]] 各成一个包/模块。
- 统一命名：snake_case 函数/变量、PascalCase 类与 pydantic 模型、模块名与规约文件名一致。
