"""Tests for example servers"""

import sys
import uuid

import anyio
import pytest
from pytest_examples import CodeExample, EvalExample, find_examples

from mcp import types
from mcp.shared.memory import (
    create_connected_server_and_client_session as client_session,
)
from mcp.shared.session import RequestResponder
from mcp.types import (
    AsyncToolResponse,
    TextContent,
    TextResourceContents,
)


@pytest.mark.anyio
async def test_simple_echo():
    """Test the simple echo server"""
    from examples.fastmcp.simple_echo import mcp

    async with client_session(mcp._mcp_server) as client:
        result = await client.call_tool("echo", {"text": "hello"})
        assert len(result.content) == 1
        content = result.content[0]
        assert isinstance(content, TextContent)
        assert content.text == "hello"


@pytest.mark.anyio
async def test_complex_inputs():
    """Test the complex inputs server"""
    from examples.fastmcp.complex_inputs import mcp

    async with client_session(mcp._mcp_server) as client:
        tank = {"shrimp": [{"name": "bob"}, {"name": "alice"}]}
        result = await client.call_tool(
            "name_shrimp", {"tank": tank, "extra_names": ["charlie"]}
        )
        assert len(result.content) == 3
        assert isinstance(result.content[0], TextContent)
        assert isinstance(result.content[1], TextContent)
        assert isinstance(result.content[2], TextContent)
        assert result.content[0].text == "bob"
        assert result.content[1].text == "alice"
        assert result.content[2].text == "charlie"


@pytest.mark.anyio
async def test_desktop(monkeypatch):
    """Test the desktop server"""
    from pathlib import Path

    from pydantic import AnyUrl

    from examples.fastmcp.desktop import mcp

    # Mock desktop directory listing
    mock_files = [Path("/fake/path/file1.txt"), Path("/fake/path/file2.txt")]
    monkeypatch.setattr(Path, "iterdir", lambda self: mock_files)
    monkeypatch.setattr(Path, "home", lambda: Path("/fake/home"))

    async with client_session(mcp._mcp_server) as client:
        # Test the add function
        result = await client.call_tool("add", {"a": 1, "b": 2})
        assert len(result.content) == 1
        content = result.content[0]
        assert isinstance(content, TextContent)
        assert content.text == "3"

        # Test the desktop resource
        result = await client.read_resource(AnyUrl("dir://desktop"))
        assert len(result.contents) == 1
        content = result.contents[0]
        assert isinstance(content, TextResourceContents)
        assert isinstance(content.text, str)
        if sys.platform == "win32":
            file_1 = "/fake/path/file1.txt".replace("/", "\\\\")  # might be a bug
            file_2 = "/fake/path/file2.txt".replace("/", "\\\\")  # might be a bug
            assert file_1 in content.text
            assert file_2 in content.text
            # might be a bug, but the test is passing
        else:
            assert "/fake/path/file1.txt" in content.text
            assert "/fake/path/file2.txt" in content.text


@pytest.mark.parametrize("example", find_examples("README.md"), ids=str)
def test_docs_examples(example: CodeExample, eval_example: EvalExample):
    ruff_ignore: list[str] = ["F841", "I001"]

    eval_example.set_config(
        ruff_ignore=ruff_ignore, target_version="py310", line_length=88
    )

    if eval_example.update_examples:  # pragma: no cover
        eval_example.format(example)
    else:
        eval_example.lint(example)


@pytest.mark.anyio
async def test_async_tool():
    """Test that MyAsyncTool returns an async token."""
    from examples.fastmcp.async_tool import mcp

    async with client_session(mcp._mcp_server) as client:
        task_id = str(uuid.uuid4())
        # Start the operation
        start_result = await client.call_tool("MyAsyncTool", {"task_id": task_id})
        assert len(start_result.content) == 1
        [async_response] = start_result.content
        assert isinstance(async_response, AsyncToolResponse)
        assert async_response.token == task_id, "Incorrect token"
        assert start_result.isError is False, "isError should be false"

        # Get the result
        get_result_result = await client.get_async_tool_result(
            "MyAsyncTool",
            task_id,
        )
        assert get_result_result.state == "successful"
        assert len(get_result_result.content) == 1
        [content] = get_result_result.content
        assert isinstance(content, TextContent)
        assert content.text == "Hello from async tool!"


@pytest.mark.anyio
async def test_cancel_async_tool_call():
    """Test that an async tool call can be cancelled."""
    from examples.fastmcp.async_tool import mcp

    async with client_session(mcp._mcp_server) as client:
        task_id = str(uuid.uuid4())
        tool_result = await client.call_tool("MyAsyncTool", {"task_id": task_id})
        assert len(tool_result.content) == 1
        [async_response] = tool_result.content
        assert isinstance(async_response, AsyncToolResponse)
        assert async_response.token == task_id
        _cancel_result = await client.cancel_async_tool_call("MyAsyncTool", task_id)

        # Try to get the result and confirm it was canceled
        get_result_result = await client.get_async_tool_result(
            "MyAsyncTool",
            task_id,
            wait=1,
        )
        assert get_result_result.state == "cancelled"


# Based on tests/shared/test_streamable_http.py::test_streamablehttp_client_get_stream
@pytest.mark.anyio
async def test_async_tool_progress_notification():
    from examples.fastmcp.async_tool import mcp

    notifications_received = []

    async def notification_handler(
        message: RequestResponder[types.ServerRequest, types.ClientResult]
        | types.ServerNotification
        | Exception,
    ) -> None:
        if isinstance(message, types.ServerNotification):
            notifications_received.append(message)

    async with client_session(
        mcp._mcp_server,
        message_handler=notification_handler,
    ) as client:
        task_id = str(uuid.uuid4())
        tool_result = await client.call_tool("MyAsyncTool", {"task_id": task_id})
        assert len(tool_result.content) == 1
        [async_response] = tool_result.content
        assert isinstance(async_response, types.AsyncToolResponse)
        assert async_response.token == task_id

        try:
            with anyio.fail_after(2):
                while not notifications_received:
                    await anyio.sleep(0.01)
        except TimeoutError:
            pytest.fail("Timeout waiting for ProgressNotification")

        assert len(notifications_received) == 1
        [server_notification_wrapper] = notifications_received

        assert isinstance(server_notification_wrapper.root, types.ProgressNotification)

        resolve_notification_params = server_notification_wrapper.root.params

        assert resolve_notification_params.progressToken == task_id
        assert resolve_notification_params.progress == 0.5
        assert resolve_notification_params.message == "Work in progress..."
