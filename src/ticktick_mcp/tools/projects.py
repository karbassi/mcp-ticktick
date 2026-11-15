from __future__ import annotations

import contextlib
from typing import Any

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

from ticktick_mcp.client import TickTickClient
from ticktick_mcp.models import Project
from ticktick_mcp.resolve import resolve_name
from ticktick_mcp.text import clean_project


def _get_client(ctx: Context) -> TickTickClient:
    return ctx.request_context.lifespan_context["client"]  # type: ignore[union-attr]


async def _resolve_project_id(client: TickTickClient, name_or_id: str) -> str:
    if name_or_id.lower() == "inbox":
        return await _get_inbox_id(client)
    if name_or_id.startswith("inbox") and name_or_id[5:].isdigit():
        return name_or_id
    projects = await client.v1_get("/project")
    parsed = [Project(**p) for p in projects]
    return resolve_name(name_or_id, parsed, lambda p: p.name, lambda p: p.id, "project")


async def _get_inbox_id(client: TickTickClient) -> str:
    if client._inbox_project_id:
        return client._inbox_project_id
    task = await client.v1_post("/task", {"title": "__inbox_probe__"})
    inbox_id = task.get("projectId")
    if not inbox_id:
        raise ToolError("Could not discover inbox project ID")
    with contextlib.suppress(Exception):
        await client.v1_delete(f"/project/{inbox_id}/task/{task['id']}")
    client._inbox_project_id = inbox_id
    return inbox_id


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }
    )
    async def list_projects(ctx: Context, include_icons: bool = False) -> list[dict[str, Any]]:
        """List all projects (task lists) in TickTick.

        Returns all projects including their IDs, names, colors, and folder assignments.
        Does not include the Inbox — use "inbox" as the project name in task tools to
        interact with the default inbox.

        Args:
            include_icons: Keep the leading emoji icon in each project name.
                By default the icon is stripped (e.g. "📖Study" -> "Study").
        """
        client = _get_client(ctx)
        projects = await client.v1_get("/project")
        if include_icons:
            return projects
        return [clean_project(p) for p in projects]

    @mcp.tool(
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }
    )
    async def get_project(
        ctx: Context,
        project: str,
        include_icons: bool = False,
    ) -> dict[str, Any]:
        """Get a single project by name or ID.

        Supports fuzzy name matching. Use "inbox" to get the inbox project.

        Args:
            project: Project name or ID. Supports fuzzy matching.
            include_icons: Keep the leading emoji icon in the project name.
                By default the icon is stripped (e.g. "📖Study" -> "Study").
        """
        client = _get_client(ctx)
        pid = await _resolve_project_id(client, project)
        result = await client.v1_get(f"/project/{pid}")
        return result if include_icons else clean_project(result)

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        }
    )
    async def add_project(
        ctx: Context,
        name: str,
        color: str | None = None,
        view_mode: str | None = None,
        kind: str | None = None,
        folder: str | None = None,
    ) -> dict[str, Any]:
        """Create a new project (task list).

        Args:
            name: Project name (required).
            color: Hex color code (e.g. "#FF0000").
            view_mode: View mode: "list", "kanban", "timeline".
            kind: Project kind (e.g. "TASK", "NOTE").
            folder: Folder name or ID to place the project in.
        """
        client = _get_client(ctx)
        body: dict[str, Any] = {"name": name}
        if color:
            body["color"] = color
        if view_mode:
            body["viewMode"] = view_mode
        if kind:
            body["kind"] = kind
        if folder:
            from ticktick_mcp.tools.folders import _resolve_folder_id

            folder_id, _ = await _resolve_folder_id(client, folder)
            body["groupId"] = folder_id

        return await client.v1_post("/project", body)

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        }
    )
    async def edit_project(
        ctx: Context,
        project: str,
        name: str | None = None,
        color: str | None = None,
        view_mode: str | None = None,
        folder: str | None = None,
        remove_folder: bool = False,
    ) -> dict[str, Any]:
        """Update an existing project's properties.

        Only provided fields are changed.

        Args:
            project: Project name or ID to edit.
            name: New project name.
            color: New hex color code.
            view_mode: New view mode: "list", "kanban", "timeline".
            folder: Move project to this folder (name or ID).
            remove_folder: Set to true to remove the project from its folder.
        """
        client = _get_client(ctx)
        pid = await _resolve_project_id(client, project)
        body: dict[str, Any] = {"id": pid}

        if name is not None:
            body["name"] = name
        if color is not None:
            body["color"] = color
        if view_mode is not None:
            body["viewMode"] = view_mode
        if remove_folder:
            body["groupId"] = "NONE"
        elif folder:
            from ticktick_mcp.tools.folders import _resolve_folder_id

            folder_id, _ = await _resolve_folder_id(client, folder)
            body["groupId"] = folder_id

        return await client.v1_post(f"/project/{pid}", body)

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": True,
        }
    )
    async def delete_project(
        ctx: Context,
        project: str,
    ) -> str:
        """Permanently delete a project and all its tasks.

        This action cannot be undone.

        Args:
            project: Project name or ID to delete.
        """
        client = _get_client(ctx)
        pid = await _resolve_project_id(client, project)
        await client.v1_delete(f"/project/{pid}")
        return f"Project {project} deleted"
