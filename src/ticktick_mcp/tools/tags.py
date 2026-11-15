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
    async def list_tags(ctx: Context) -> list[dict[str, Any]]:
        """List all tags.

        Returns all tags with their names, colors, parent relationships, and sort settings.
        """
        client = _get_client(ctx)
        return await client.v1_get("/tag")

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        }
    )
    async def add_tags(
        ctx: Context,
        names: list[str],
    ) -> Any:
        """Create one or more new tags.

        Args:
            names: List of tag names to create.
        """
        client = _get_client(ctx)
        return [await client.v1_post("/tag", {"label": n, "name": n}) for n in names]

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": True,
        }
    )
    async def delete_tags(
        ctx: Context,
        names: list[str],
    ) -> str:
        """Delete one or more tags by name.

        Tasks keep existing, but the tag is removed from every task that had it.

        Args:
            names: List of tag names to delete.
        """
        client = _get_client(ctx)
        for name in names:
            await client.v1_delete("/tag/delete?scope=0", {"name": name})
        return f"Deleted {len(names)} tag(s)"

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        }
    )
    async def rename_tag(
        ctx: Context,
        old_name: str,
        new_name: str,
    ) -> str:
        """Rename a tag.

        All tasks with the old tag name will be updated to use the new name.

        Args:
            old_name: Current tag name.
            new_name: New tag name.
        """
        client = _get_client(ctx)
        await client.v1_put("/tag/rename?scope=0", {"name": old_name, "newName": new_name})
        return f"Tag '{old_name}' renamed to '{new_name}'"

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        }
    )
    async def edit_tag(
        ctx: Context,
        name: str,
        color: str | None = None,
        parent: str | None = None,
        clear_parent: bool = False,
        sort_order: int | None = None,
        sort_type: str | None = None,
    ) -> Any:
        """Update a tag's properties.

        Only provided fields are changed.

        Args:
            name: The tag name to edit.
            color: New hex color code (e.g. "#FF0000").
            parent: Set a parent tag name (for hierarchical tags).
            clear_parent: Set to true to remove the parent tag.
            sort_order: New sort order integer.
            sort_type: Sort type (e.g. "project", "dueDate").
        """
        client = _get_client(ctx)
        tag: dict[str, Any] = {"name": name}
        if color is not None:
            tag["color"] = color
        if clear_parent:
            tag["parent"] = ""
        elif parent is not None:
            tag["parent"] = parent
        if sort_order is not None:
            tag["sortOrder"] = sort_order
        if sort_type is not None:
            tag["sortType"] = sort_type
        return await client.v1_put("/tag", tag)

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": True,
        }
    )
    async def merge_tags(
        ctx: Context,
        source: str,
        target: str,
    ) -> str:
        """Merge a source tag into a target tag.

        All tasks tagged with the source tag will be re-tagged with the target tag.
        The source tag is deleted.

        Args:
            source: Tag name to merge from (will be deleted).
            target: Tag name to merge into (will be kept).
        """
        client = _get_client(ctx)
        await client.v2_put("/tag/merge", {"name": source, "newName": target})
        return f"Tag '{source}' merged into '{target}'"
