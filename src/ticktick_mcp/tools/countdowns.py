from __future__ import annotations

from typing import Any

from fastmcp import Context, FastMCP

from ticktick_mcp.client import TickTickClient


def _get_client(ctx: Context) -> TickTickClient:
    return ctx.request_context.lifespan_context["client"]  # type: ignore[union-attr]


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }
    )
    async def list_countdowns(ctx: Context) -> list[dict[str, Any]]:
        """List all countdowns (birthdays, anniversaries, events).

        Read-only: the official API has no create, update, or delete for countdowns.
        Each countdown has an id, name, date (YYYYMMDD integer), repeatFlag, reminders,
        and display settings.
        """
        client = _get_client(ctx)
        return await client.v1_get("/countdown")
