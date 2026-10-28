from __future__ import annotations

from typing import Any

from fastmcp import Context, FastMCP

from ticktick_mcp.client import TickTickClient
from ticktick_mcp.resolve import resolve_name_with_etag


def _get_client(ctx: Context) -> TickTickClient:
    return ctx.request_context.lifespan_context["client"]  # type: ignore[union-attr]


async def _get_filter(client: TickTickClient, name_or_id: str) -> dict[str, Any]:
    """Keep the full server representation, including unknown and nullable fields."""
    data = await client.batch_check()
    filters = data.get("filters") or []
    fid, _ = resolve_name_with_etag(
        name_or_id,
        filters,
        lambda f: f.get("name") or "",
        lambda f: f["id"],
        lambda f: f.get("etag") or "",
        "filter",
    )
    for f in filters:
        if f["id"] == fid:
            return f
    raise ValueError(f"No filter found matching '{name_or_id}'")


async def _resolve_filter(client: TickTickClient, name_or_id: str) -> tuple[str, str]:
    """Resolve a stored filter name/ID to (id, etag)."""
    f = await _get_filter(client, name_or_id)
    return f["id"], f.get("etag") or ""


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
        f: dict[str, Any] = {"name": name}
        if rule is not None:
            f["rule"] = rule
        if sort_type is not None:
            f["sortType"] = sort_type
        return await client.v2_post("/batch/filter", {"add": [f]})

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
        # /batch/filter replaces omitted fields; it is not a merge-patch API.
        update = (await _get_filter(client, filter_name)).copy()
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
        for f in filters:
            fid, _ = await _resolve_filter(client, f)
            ids.append(fid)
        await client.v2_post("/batch/filter", {"delete": ids})
        return f"Deleted {len(ids)} filter(s)"
