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
    groups = [ProjectGroup(**g) for g in (await client.v1_get("/project/group") or [])]
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
        and sort settings.
        """
        client = _get_client(ctx)
        return await client.v1_get("/project/group") or []

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
        return await client.v1_post("/project/group", {"name": name})

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
        for f in folders:
            fid, _ = await _resolve_folder_id(client, f)
            ids.append(fid)
        for fid in ids:
            await client.v1_delete(f"/project/group/{fid}")
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
        fid, _ = await _resolve_folder_id(client, folder)
        return await client.v1_post(f"/project/group/{fid}", {"name": new_name})
