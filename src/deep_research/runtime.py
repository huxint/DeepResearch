"""Runtime bootstrap for the full DeepResearch pipeline."""

from collections.abc import AsyncGenerator
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

import httpx
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from pydantic import BaseModel

from deep_research.cross_cutting.budget import BudgetPool
from deep_research.cross_cutting.config import Settings, load_settings
from deep_research.cross_cutting.errors import ConfigMissing
from deep_research.cross_cutting.logging import configure_logging
from deep_research.journal import Journal
from deep_research.kernel import Kernel
from deep_research.mcp_tools import MCPClientSessionTransport, MCPTools
from deep_research.pipeline import Report, ResearchPipeline, SearchTools
from deep_research.provider_pool import ProviderPool
from deep_research.subagent import Subagent
from deep_research.verifier import Verifier


@asynccontextmanager
async def build_research_pipeline(
    settings: Settings | None = None,
    *,
    tools: SearchTools | None = None,
    provider_transport: httpx.AsyncBaseTransport | None = None,
) -> AsyncGenerator[ResearchPipeline]:
    """Construct a managed ResearchPipeline from validated settings."""

    runtime_settings = load_settings() if settings is None else settings
    configure_logging(runtime_settings.log_level)
    journal_path = Path(runtime_settings.journal_path)
    journal_path.parent.mkdir(parents=True, exist_ok=True)

    async with AsyncExitStack() as stack:
        provider_pool = await stack.enter_async_context(
            ProviderPool(
                runtime_settings.providers,
                request_timeout_s=runtime_settings.request_timeout_s,
                transport=provider_transport,
            )
        )
        journal = Journal(journal_path)
        stack.callback(journal.close)

        budget = BudgetPool(limit_usd=runtime_settings.budget_usd)
        subagent = Subagent(
            provider=provider_pool,
            budget=budget,
            default_model=runtime_settings.default_model,
        )
        kernel = Kernel(subagent=_SubagentAdapter(subagent), journal=journal)
        runtime_tools = (
            await _build_mcp_tools(runtime_settings=runtime_settings, stack=stack)
            if tools is None
            else tools
        )
        verifier = Verifier(kernel=kernel, tools=runtime_tools)
        yield ResearchPipeline(kernel=kernel, tools=runtime_tools, verifier=verifier)


async def run_research(
    question: str,
    *,
    settings: Settings | None = None,
    tools: SearchTools | None = None,
    provider_transport: httpx.AsyncBaseTransport | None = None,
) -> Report:
    """Run one full research task and return the verified report."""

    async with build_research_pipeline(
        settings,
        tools=tools,
        provider_transport=provider_transport,
    ) as pipeline:
        return await pipeline.research(question)


async def _build_mcp_tools(
    *,
    runtime_settings: Settings,
    stack: AsyncExitStack,
) -> MCPTools:
    server = runtime_settings.mcp_server
    if server is None:
        raise ConfigMissing("缺少 DR_MCP_SERVER，无法启动真实 search/fetch 工具")

    read_stream, write_stream = await stack.enter_async_context(
        stdio_client(
            StdioServerParameters(
                command=server.command,
                args=server.args,
                env=server.env,
                cwd=server.cwd,
            )
        )
    )
    session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
    await session.initialize()
    return MCPTools(
        transport=MCPClientSessionTransport(session),
        timeout_s=runtime_settings.request_timeout_s,
    )


class _SubagentAdapter:
    """Expose Subagent through Kernel's non-overloaded protocol surface."""

    def __init__(self, subagent: Subagent) -> None:
        self._subagent = subagent

    async def run(
        self,
        prompt: str,
        *,
        schema: type[BaseModel] | None = None,
        model: str | None = None,
        max_retries: int | None = None,
    ) -> BaseModel | str:
        if schema is None:
            return await self._subagent.run(
                prompt,
                schema=None,
                model=model,
                max_retries=max_retries,
            )
        return await self._subagent.run(
            prompt,
            schema=schema,
            model=model,
            max_retries=max_retries,
        )
