from __future__ import annotations

from typing import Any

from fastmcp import Context, FastMCP

from ticktick_mcp.client import TickTickClient
from ticktick_mcp.models import ProjectGroup
from ticktick_mcp.resolve import resolve_name_with_etag


def _get_client(ctx: Context) -> TickTickClient:
    return ctx.request_context.lifespan_context["client"]  # type: ignore[union-attr]


async def _resolve_folder_id(client: TickTickClient, name_or_id: str) -> tuple[str, str]:
    """Resolve a folder name/ID to (id, etag)."""
    data = await client.batch_check()
    groups = [ProjectGroup(**g) for g in (data.get("projectGroups") or [])]
    return resolve_name_with_etag(
        name_or_id,
        groups,
        lambda g: g.name,
        lambda g: g.id,
        lambda g: g.etag or "",
        "folder",
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
    async def list_folders(ctx: Context) -> list[dict[str, Any]]:
        """List all project folders (groups).

        Folders organize projects into groups. Returns folder IDs, names,
        and sort settings. Requires v2 session token.
        """
        client = _get_client(ctx)
        data = await client.batch_check()
        return data.get("projectGroups") or []

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        }
    )
    async def add_folder(
        ctx: Context,
        name: str,
    ) -> Any:
        """Create a new project folder.

        Args:
            name: Folder name (required).
        """
        client = _get_client(ctx)
        return await client.v2_post(
            "/batch/projectGroup",
            {"add": [{"name": name, "listType": "group"}]},
        )

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": True,
        }
    )
    async def delete_folders(
        ctx: Context,
        folders: list[str],
    ) -> str:
        """Delete one or more folders.

        Projects inside deleted folders are not deleted — they become ungrouped.

        Args:
            folders: List of folder names or IDs to delete. Supports fuzzy matching.
        """
        client = _get_client(ctx)
        ids = []
        for name_or_id in folders:
            folder_id, _ = await _resolve_folder_id(client, name_or_id)
            ids.append(folder_id)
        await client.v2_post("/batch/projectGroup", {"delete": ids})
        return f"Deleted {len(ids)} folder(s)"

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        }
    )
    async def rename_folder(
        ctx: Context,
        folder: str,
        new_name: str,
    ) -> Any:
        """Rename a project folder.

        Args:
            folder: Current folder name or ID. Supports fuzzy matching.
            new_name: New folder name.
        """
        client = _get_client(ctx)
        folder_id, etag = await _resolve_folder_id(client, folder)
        return await client.v2_post(
            "/batch/projectGroup",
            {"update": [{"id": folder_id, "etag": etag, "name": new_name, "listType": "group"}]},
        )
