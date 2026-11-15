from __future__ import annotations

from typing import Any

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

from ticktick_mcp.client import TickTickClient
from ticktick_mcp.resolve import resolve_name
from ticktick_mcp.tools.projects import _resolve_project_id


def _get_client(ctx: Context) -> TickTickClient:
    return ctx.request_context.lifespan_context["client"]  # type: ignore[union-attr]


async def resolve_column_id(client: TickTickClient, project_id: str, column: str) -> str:
    """Resolve a column name/ID within a project to its ID."""
    columns = await client.v1_get(f"/project/{project_id}/column") or []
    return resolve_name(
        column,
        columns,
        lambda c: c.get("name", ""),
        lambda c: c["id"],
        "column",
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
    async def list_columns(ctx: Context, project: str) -> list[dict[str, Any]]:
        """List the kanban columns of a project.

        Returns column IDs, names, colors, and sort orders. A project only has
        columns when it uses the kanban view.

        Args:
            project: Project name or ID. Supports fuzzy matching.
        """
        client = _get_client(ctx)
        pid = await _resolve_project_id(client, project)
        return await client.v1_get(f"/project/{pid}/column") or []

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        }
    )
    async def add_column(
        ctx: Context,
        project: str,
        name: str,
        sort_order: int | None = None,
        color: str | None = None,
    ) -> Any:
        """Create a kanban column in a project.

        Args:
            project: Project name or ID. Supports fuzzy matching.
            name: Column name (required).
            sort_order: Position among the columns; lower comes first.
            color: Column color as a hex string, e.g. "#FF0000".
        """
        client = _get_client(ctx)
        pid = await _resolve_project_id(client, project)
        body: dict[str, Any] = {"name": name}
        if sort_order is not None:
            body["sortOrder"] = sort_order
        if color is not None:
            body["color"] = color
        return await client.v1_post(f"/project/{pid}/column", body)

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        }
    )
    async def edit_column(
        ctx: Context,
        project: str,
        column: str,
        name: str | None = None,
        sort_order: int | None = None,
        color: str | None = None,
    ) -> Any:
        """Rename, reorder, or recolor a kanban column.

        Only provided fields are changed. The official API has no endpoint to
        delete a column, so there is no delete_column tool.

        Args:
            project: Project name or ID. Supports fuzzy matching.
            column: Column name or ID. Supports fuzzy matching.
            name: New column name.
            sort_order: New position among the columns; lower comes first.
            color: New color as a hex string, e.g. "#FF0000".
        """
        client = _get_client(ctx)
        pid = await _resolve_project_id(client, project)
        cid = await resolve_column_id(client, pid, column)
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if sort_order is not None:
            body["sortOrder"] = sort_order
        if color is not None:
            body["color"] = color
        if not body:
            raise ToolError("Provide at least one of name, sort_order, color")
        return await client.v1_post(f"/project/{pid}/column/{cid}", body)
