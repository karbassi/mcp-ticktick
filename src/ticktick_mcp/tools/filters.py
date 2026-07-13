from __future__ import annotations

from typing import Any

from fastmcp import Context, FastMCP

from ticktick_mcp.client import TickTickClient
from ticktick_mcp.models import Filter
from ticktick_mcp.resolve import resolve_name_with_etag


def _get_client(ctx: Context) -> TickTickClient:
    return ctx.request_context.lifespan_context["client"]  # type: ignore[union-attr]


async def _resolve_filter(client: TickTickClient, name_or_id: str) -> tuple[str, str]:
    """Resolve a filter name/ID to (id, etag)."""
    data = await client.batch_check()
    filters = [Filter(**f) for f in data.get("filters") or []]
    return resolve_name_with_etag(
        name_or_id,
        filters,
        lambda f: f.name,
        lambda f: f.id,
        lambda f: f.etag or "",
        "filter",
    )


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }
    )
    async def list_filters(ctx: Context) -> list[dict[str, Any]]:
        """List all saved filters.

        Returns all custom filters with their IDs, names, rules, and sort settings.
        Requires v2 session token.
        """
        client = _get_client(ctx)
        data = await client.batch_check()
        return data.get("filters") or []

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        }
    )
    async def add_filter(
        ctx: Context,
        name: str,
        rule: str | None = None,
        sort_type: str | None = None,
    ) -> Any:
        """Create a new saved filter.

        Args:
            name: Filter name (required).
            rule: JSON rule definition string (e.g. '{"and":[],"type":0}').
            sort_type: Sort type for filter results (e.g. "dueDate", "priority").
        """
        client = _get_client(ctx)
        payload: dict[str, Any] = {"name": name}
        if rule is not None:
            payload["rule"] = rule
        if sort_type is not None:
            payload["sortType"] = sort_type
        return await client.v2_post("/batch/filter", {"add": [payload]})

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        }
    )
    async def edit_filter(
        ctx: Context,
        filter_name: str,
        name: str | None = None,
        rule: str | None = None,
        sort_type: str | None = None,
    ) -> Any:
        """Update an existing filter.

        Only provided fields are changed.

        Args:
            filter_name: Current filter name or ID. Supports fuzzy matching.
            name: New filter name.
            rule: New JSON rule definition string.
            sort_type: New sort type.
        """
        client = _get_client(ctx)
        filter_id, etag = await _resolve_filter(client, filter_name)
        update: dict[str, Any] = {"id": filter_id, "etag": etag}
        if name is not None:
            update["name"] = name
        if rule is not None:
            update["rule"] = rule
        if sort_type is not None:
            update["sortType"] = sort_type
        return await client.v2_post("/batch/filter", {"update": [update]})

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": True,
        }
    )
    async def delete_filters(
        ctx: Context,
        filters: list[str],
    ) -> str:
        """Delete one or more saved filters.

        Args:
            filters: List of filter names or IDs to delete. Supports fuzzy matching.
        """
        client = _get_client(ctx)
        ids = []
        for name_or_id in filters:
            filter_id, _ = await _resolve_filter(client, name_or_id)
            ids.append(filter_id)
        await client.v2_post("/batch/filter", {"delete": ids})
        return f"Deleted {len(ids)} filter(s)"
