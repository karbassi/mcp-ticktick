from __future__ import annotations

from typing import Any

from fastmcp import Context, FastMCP

from ticktick_mcp.client import TickTickClient
from ticktick_mcp.tools.tasks import _resolve_project_id


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
    async def list_comments(
        ctx: Context,
        task_id: str,
        project: str,
    ) -> list[dict[str, Any]]:
        """List the comments on a task.

        Args:
            task_id: The task ID.
            project: The project name or ID containing the task.
        """
        client = _get_client(ctx)
        pid = await _resolve_project_id(client, project)
        return await client.v1_get(f"/project/{pid}/task/{task_id}/comments") or []

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        }
    )
    async def add_comment(
        ctx: Context,
        task_id: str,
        project: str,
        text: str,
    ) -> Any:
        """Add a comment to a task.

        Comments cannot be edited through the official API. To change one,
        delete it and add a new one.

        Args:
            task_id: The task ID.
            project: The project name or ID containing the task.
            text: The comment text.
        """
        client = _get_client(ctx)
        pid = await _resolve_project_id(client, project)
        return await client.v1_post(f"/project/{pid}/task/{task_id}/comment", {"title": text})

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": True,
        }
    )
    async def delete_comment(
        ctx: Context,
        task_id: str,
        project: str,
        comment_id: str,
    ) -> str:
        """Delete a comment from a task.

        Args:
            task_id: The task ID.
            project: The project name or ID containing the task.
            comment_id: The comment ID (from list_comments).
        """
        client = _get_client(ctx)
        pid = await _resolve_project_id(client, project)
        await client.v1_delete(f"/project/{pid}/task/{task_id}/comment/{comment_id}")
        return f"Comment {comment_id} deleted"
