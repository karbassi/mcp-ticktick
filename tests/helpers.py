from __future__ import annotations

import json
from typing import Any

import respx
from fastmcp import Client


async def call_tool(tool: str, args: dict[str, Any]) -> Any:
    """Call a tool through the real MCP server (needs the env_vars fixture)."""
    from ticktick_mcp.server import mcp

    async with Client(mcp) as c:
        return await c.call_tool(tool, args)


def body(route: respx.Route, i: int = 0) -> Any:
    """JSON body of the i-th request a respx route received."""
    return json.loads(route.calls[i].request.content)


def result_data(result: Any) -> Any:
    """Tool return value, whether FastMCP sent it structured or as JSON text."""
    if result.structured_content is not None:
        return result.structured_content.get("result", result.structured_content)
    return json.loads(result.content[0].text)
