from __future__ import annotations

import json

from fastmcp import Context, FastMCP

from ticktick_mcp.client import TickTickClient


def _get_client(ctx: Context) -> TickTickClient:
    return ctx.request_context.lifespan_context["client"]  # type: ignore[union-attr]


def register(mcp: FastMCP) -> None:
    @mcp.resource("ticktick://projects")
    async def projects(ctx: Context) -> str:
        """All projects (task lists) with their IDs, names, colors, and folder assignments."""
        client = _get_client(ctx)
        return json.dumps(await client.v1_get("/project"))

    @mcp.resource("ticktick://tags")
    async def tags(ctx: Context) -> str:
        """All tags with their names, colors, and hierarchical relationships."""
        client = _get_client(ctx)
        return json.dumps(await client.v1_get("/tag"))
