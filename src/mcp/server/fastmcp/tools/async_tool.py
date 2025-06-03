from __future__ import annotations as _annotations

from typing import Any, Protocol

from mcp.server.fastmcp.tools.base import Tool
from mcp.types import AsyncOperationToken, AsyncToolResponse, ToolAnnotations


class AsyncTool(Protocol):
    """A tool that can perform asynchronous operations."""

    # Note that Tool.is_async currently refers to whether or not the function returns an
    # Awaitable. This is orthogonal to whether or not the tool responds asynchronously:
    # to "respond asynchronously" means to respond with a token and support subsequent
    # requests to fetch/cancel the result, as well as supporting a callback in the
    # initial request to which the eventual result will be delivered as notification.

    async def start(self, *args: Any, **kwargs: Any) -> AsyncToolResponse:
        """Start the operation.

        The method can optionally request a Context object by adding a parameter with the
        Context type annotation. The context provides access to MCP capabilities like
        logging, progress reporting, and resource access.
        """
        ...

    async def cancel(
        self, token: AsyncOperationToken, *args: Any, **kwargs: Any
    ) -> None:
        """Cancel the operation.

        The method can optionally request a Context object by adding a parameter with the
        Context type annotation. The context provides access to MCP capabilities like
        logging, progress reporting, and resource access.

        Args:
            token: The token identifying the operation.
        """
        ...

    async def get_result(
        self, token: AsyncOperationToken, wait: int | None, *args: Any, **kwargs: Any
    ) -> Any:
        """Get the result of the operation.

        The method can optionally request a Context object by adding a parameter with the
        Context type annotation. The context provides access to MCP capabilities like
        logging, progress reporting, and resource access.

        Args:
            token: The token identifying the operation.
            wait: Optional number of milliseconds to wait for the result. If specified,
                  turns this request into a long poll.
        """
        ...


class AsyncToolModel(Tool):
    # TODO: these should not be nullable, but this would require duplicating or
    # refactoring Tool.from_function, since it runs Pydantic validation.
    get_result: Tool | None = None
    cancel: Tool | None = None

    @classmethod
    def from_instance(
        cls,
        async_tool: AsyncTool,
        name: str | None = None,
        description: str | None = None,
        annotations: ToolAnnotations | None = None,
    ) -> AsyncToolModel:
        start = super().from_function(
            async_tool.start,
            name=name,
            description=description,
            annotations=annotations,
        )
        start.get_result = Tool.from_function(async_tool.get_result)
        start.cancel = Tool.from_function(async_tool.cancel)
        return start
