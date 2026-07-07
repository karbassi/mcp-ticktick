from __future__ import annotations

import json

from fastmcp import Context, FastMCP

from ticktick_mcp.client import TickTickClient
from ticktick_mcp.text import clean_project


def _get_client(ctx: Context) -> TickTickClient:
    return ctx.request_context.lifespan_context["client"]  # type: ignore[union-attr]


def register(mcp: FastMCP) -> None:
    @mcp.resource("ticktick://projects")
    async def projects(ctx: Context) -> str:
        """All projects (task lists) with their IDs, names, colors, and folder assignments.

        Project names have their leading emoji icon stripped (e.g. the API's
        "\U0001f4d6Study" is returned as "Study").
        """
        client = _get_client(ctx)
        return json.dumps([clean_project(p) for p in await client.v1_get("/project")])

    @mcp.resource("ticktick://tags")
    async def tags(ctx: Context) -> str:
        """All tags with their names, colors, and hierarchical relationships."""
        client = _get_client(ctx)
        return json.dumps(await client.v2_get("/tags"))
