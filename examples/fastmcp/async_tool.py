import asyncio
from collections.abc import Coroutine, Sequence
from dataclasses import dataclass, field
from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.tools.async_tool import AsyncTool
from mcp.types import (
    AsyncOperationToken,
    AsyncToolResponse,
    EmbeddedResource,
    ImageContent,
    ProgressNotification,
    ProgressNotificationParams,
    ServerNotification,
    TextContent,
)

mcp = FastMCP("AsyncToolExample")


# A user's AsyncTool class must conform to the AsyncTool interface (typing.Protocol),
# which defines start, get_result, and cancel methods. A Context parameter is optional, as
# in normal (non-async) tool functions. Inheriting from the protocol is optional, but
# brings static type information and docstrings.
class MyAsyncTool(AsyncTool):
    def __init__(self):
        self._executor = MyTaskExecutor()

    async def start(self, task_id: str, ctx: Context) -> AsyncToolResponse:
        # Pass context to task so that it can e.g. send progress notifications.
        await self._executor.add_task(task_id, my_task(task_id, ctx))
        return AsyncToolResponse(token=task_id)

    async def get_result(self, token: str, wait: int | None) -> Any:
        return await asyncio.wait_for(
            self._executor.get_task_result(token),
            timeout=(wait / 1000.0 if wait is not None else None),
        )

    async def cancel(self, token: str) -> None:
        await self._executor.cancel_task(token)


@dataclass
class MyTaskExecutor:
    """
    This class represents the task execution platform being used by the team operating the
    MCP server.
    """

    tasks: dict[str, asyncio.Task[Any]] = field(default_factory=dict)

    async def add_task(self, id: str, coro: Coroutine[Any, Any, Any]) -> None:
        """
        Add a task to the task execution platform.
        """
        if id in self.tasks:
            raise RuntimeError(f"Task with id {id} already exists")

        # This function is async def because in reality this step will often write to
        # durable storage.
        self.tasks[id] = asyncio.create_task(coro)

    async def get_task_result(self, id: str) -> Any:
        """
        Get the result of a task from the task execution platform.
        """
        task = self.tasks.get(id)
        if not task:
            raise RuntimeError(f"Task not found with id {id}")
        return await task

    async def cancel_task(self, id: str) -> None:
        """
        Request cancellation of a task on the task execution platform.
        """
        task = self.tasks.get(id)
        if not task:
            raise RuntimeError(f"Task not found with id {id}")
        task.cancel()
        # Not implemented: cancellation confirmation, deletion on cancellation


async def my_task(
    token: AsyncOperationToken, ctx: Context
) -> Sequence[TextContent | ImageContent | EmbeddedResource | AsyncToolResponse]:
    await asyncio.sleep(0.1)
    result = [
        TextContent(
            text="Hello from async tool!",
            type="text",
        )
    ]
    # Send a progress notification
    progress_params = ProgressNotificationParams(
        progressToken=token,
        progress=0.5,
        message="Work in progress...",
    )
    await ctx.session.send_notification(
        ServerNotification(
            root=ProgressNotification(
                method="notifications/progress", params=progress_params
            )
        )
    )
    return result


mcp.add_async_tool(MyAsyncTool())
