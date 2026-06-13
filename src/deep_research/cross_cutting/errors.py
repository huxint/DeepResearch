"""错误分类 (error taxonomy)。

两支：
- ``Retryable`` —— 可重试错误（429/超时/校验失败），由弹性接缝带退避重试。
- ``Fatal`` —— 致命错误（配置缺失/无可用 Key/预算耗尽），fail-loud 上抛、不静默降级。

弹性接缝据 ``Retryable``/``Fatal`` 做模式匹配决定重试还是终止。
详见 docs/spec/03-cross-cutting.md 与 docs/guide/02-coding-conventions.md。
"""


class DeepResearchError(Exception):
    """本系统所有错误的根基类。"""


class Retryable(DeepResearchError):
    """可重试错误：弹性接缝应带指数退避重试。"""


class Fatal(DeepResearchError):
    """致命错误：fail-loud 上抛并终止当前任务（恢复靠 Journal 续跑）。"""


# —— 可重试 ——
class RateLimited(Retryable):
    """上游返回 429 / 触发 RPM 限制。"""


class Timeout(Retryable):
    """请求超时。"""


class ValidationFailed(Retryable):
    """子 Agent 输出未通过 pydantic / JSON Schema 校验。"""


# —— 致命 ——
class ConfigMissing(Fatal):
    """必填配置缺失。"""


class NoKeysAvailable(Fatal):
    """号池中已无任何可用 Key。"""


class BudgetExhausted(Fatal):
    """共享 token 预算池已超限。"""
