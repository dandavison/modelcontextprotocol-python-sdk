from __future__ import annotations as _annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.fastmcp.tools.async_tool import AsyncTool, AsyncToolModel
from mcp.server.fastmcp.tools.base import Tool
from mcp.server.fastmcp.utilities.logging import get_logger
from mcp.shared.context import LifespanContextT, RequestT
from mcp.types import AsyncOperationToken, ToolAnnotations

if TYPE_CHECKING:
    from mcp.server.fastmcp.server import Context
    from mcp.server.session import ServerSessionT

logger = get_logger(__name__)


class ToolManager:
    """Manages FastMCP tools."""

    def __init__(
        self,
        warn_on_duplicate_tools: bool = True,
        *,
        tools: list[Tool] | None = None,
        # TODO: support populating async_tools via constructor?
    ):
        self._tools: dict[str, Tool] = {}
        if tools is not None:
            for tool in tools:
                if warn_on_duplicate_tools and tool.name in self._tools:
                    logger.warning(f"Tool already exists: {tool.name}")
                self._tools[tool.name] = tool

        self.warn_on_duplicate_tools = warn_on_duplicate_tools

    def get_tool(self, name: str) -> Tool | None:
        """Get tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[Tool]:
        """List all registered tools."""
        return list(self._tools.values())

    def add_tool(
        self,
        fn: Callable[..., Any],
        name: str | None = None,
        description: str | None = None,
        annotations: ToolAnnotations | None = None,
    ) -> Tool:
        """Add a tool to the server."""
        tool = Tool.from_function(
            fn, name=name, description=description, annotations=annotations
        )
        existing = self._tools.get(tool.name)
        if existing:
            if self.warn_on_duplicate_tools:
                logger.warning(f"Tool already exists: {tool.name}")
            return existing
        self._tools[tool.name] = tool
        return tool

    def add_async_tool(
        self,
        async_tool: AsyncTool,
        name: str | None = None,
        description: str | None = None,
        annotations: ToolAnnotations | None = None,
    ) -> Tool:
        """Add an async tool to the server."""
        tool = AsyncToolModel.from_instance(
            async_tool,
            name=name or async_tool.__class__.__name__,
            description=description,
            annotations=annotations,
        )
        existing = self._tools.get(tool.name)
        if existing:
            if self.warn_on_duplicate_tools:
                logger.warning(f"Tool already exists: {tool.name}")
            return existing
        self._tools[tool.name] = tool
        return tool

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        context: Context[ServerSessionT, LifespanContextT, RequestT] | None = None,
    ) -> Any:
        """Call a tool by name with arguments."""
        tool = self.get_tool(name)
        if not tool:
            raise ToolError(f"Unknown tool: {name}")

        return await tool.run(arguments, context=context)

    async def get_async_tool_result(
        self,
        name: str,
        token: AsyncOperationToken,
        wait: int | None,
        context: Context[ServerSessionT, LifespanContextT, RequestT] | None = None,
    ) -> Any:
        """Get the result of an asynchronous tool operation."""
        tool = self.get_tool(name)
        if not tool:
            raise ToolError(f"Unknown tool: {name}")
        if not isinstance(tool, AsyncToolModel):
            raise ToolError(f"Tool is not an async tool: {name}")
        if not tool.get_result:
            raise ToolError(f"Async tool has no get_result method: {name}")
        return await tool.get_result.run(
            {"token": token, "wait": wait}, context=context
        )

    async def cancel_async_tool_call(
        self,
        name: str,
        token: AsyncOperationToken,
        context: Context[ServerSessionT, LifespanContextT, RequestT] | None = None,
    ) -> None:
        """Cancel an asynchronous tool call."""
        tool = self.get_tool(name)
        if not tool:
            raise ToolError(f"Unknown tool: {name}")
        if not isinstance(tool, AsyncToolModel):
            raise ToolError(f"Tool is not an async tool: {name}")
        if not tool.cancel:
            raise ToolError(f"Async tool has no cancel method: {name}")
        return await tool.cancel.run({"token": token}, context=context)
