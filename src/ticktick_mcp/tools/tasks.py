from __future__ import annotations

import contextlib
from typing import Any

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

from ticktick_mcp.client import TickTickClient
from ticktick_mcp.dates import ParsedDateTime, parse_datetime, parse_duration
from ticktick_mcp.models import Project
from ticktick_mcp.resolve import resolve_name

PRIORITY_MAP = {"none": 0, "low": 1, "medium": 3, "high": 5}


def _get_client(ctx: Context) -> TickTickClient:
    return ctx.request_context.lifespan_context["client"]  # type: ignore[union-attr]


async def _resolve_project_id(client: TickTickClient, project: str) -> str:
    """Turn a user-supplied project reference into a project ID.

    The inbox needs its own path because it is not returned by ``/project`` and
    its ID is account-specific rather than a stable constant.
    """
    if project.lower() == "inbox":
        return await _get_inbox_id(client)

    # An already-resolved inbox ID has the form "inbox<digits>"; pass it through
    # rather than trying (and failing) to match it against the project list.
    if project.startswith("inbox") and project[5:].isdigit():
        return project

    projects = await client.v1_get("/project")
    parsed = [Project(**p) for p in projects]
    return resolve_name(project, parsed, lambda p: p.name, lambda p: p.id, "project")


async def _get_inbox_id(client: TickTickClient) -> str:
    """Discover this account's inbox project ID.

    The v1 API exposes no endpoint that returns the inbox ID, so we provoke it:
    a freshly created task lands in the inbox by default and reports its
    ``projectId``. The probe task is then deleted so it leaves no trace. The ID
    is stable per account, so cache it for the client's lifetime.
    """
    if client._inbox_project_id:
        return client._inbox_project_id

    probe_task = await client.v1_post("/task", {"title": "__inbox_probe__"})
    inbox_id = probe_task.get("projectId")
    if not inbox_id:
        raise ToolError("Could not discover inbox project ID")

    # Best-effort cleanup: a leftover probe task is harmless, so don't fail the
    # caller's request if the delete doesn't go through.
    with contextlib.suppress(Exception):
        await client.v1_delete(f"/project/{inbox_id}/task/{probe_task['id']}")

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
    async def list_tasks(
        ctx: Context,
        project: str | None = None,
        status: str = "active",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List tasks from TickTick.

        Retrieves tasks from a specific project or all projects. Use 'status' to
        filter by active/completed tasks. For completed tasks across all projects,
        omit the project parameter.

        Args:
            project: Project name or ID to list tasks from. Supports fuzzy matching.
                Use "inbox" for the default inbox. Omit to list from all projects.
            status: Filter by task status: "active" (default) or "completed".
            limit: Maximum number of completed tasks to return (only used with status="completed").
        """
        client = _get_client(ctx)

        if status == "completed":
            if project:
                project_id = await _resolve_project_id(client, project)
                return await client.v2_get(f"/project/{project_id}/completed")
            return await client.v2_get(f"/project/all/completedInAll/?limit={limit}")

        if project:
            project_id = await _resolve_project_id(client, project)
            data = await client.v1_get(f"/project/{project_id}/data")
            return data.get("tasks") or []

        # No project given: fan out across every project and gather their tasks.
        # One unreadable project (e.g. a permissions quirk) shouldn't sink the
        # whole listing, so failures per project are swallowed.
        projects = await client.v1_get("/project")
        all_tasks: list[dict[str, Any]] = []
        for p in projects:
            try:
                data = await client.v1_get(f"/project/{p['id']}/data")
                all_tasks.extend(data.get("tasks") or [])
            except Exception:
                continue

        # The inbox isn't part of /project, so pull it in separately.
        try:
            inbox_id = await _get_inbox_id(client)
            data = await client.v1_get(f"/project/{inbox_id}/data")
            all_tasks.extend(data.get("tasks") or [])
        except Exception:
            pass

        return all_tasks

    @mcp.tool(
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }
    )
    async def get_task(
        ctx: Context,
        task_id: str,
        project: str,
    ) -> dict[str, Any]:
        """Get a single task by its ID.

        Args:
            task_id: The task ID.
            project: The project name or ID containing the task.
        """
        client = _get_client(ctx)
        project_id = await _resolve_project_id(client, project)
        return await client.v1_get(f"/project/{project_id}/task/{task_id}")

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        }
    )
    async def add_task(
        ctx: Context,
        title: str,
        project: str | None = None,
        due: str | None = None,
        start: str | None = None,
        duration: str | None = None,
        priority: str = "none",
        tags: list[str] | None = None,
        content: str | None = None,
        desc: str | None = None,
        items: list[str] | None = None,
        all_day: bool | None = None,
        timezone: str | None = None,
    ) -> dict[str, Any]:
        """Create a new task in TickTick.

        Args:
            title: Task title (required).
            project: Project name or ID. Supports fuzzy matching. Omit for inbox.
            due: Due date. Accepts "today", "tomorrow", "YYYY-MM-DD", "YYYY-MM-DDTHH:MM".
            start: Start date. Same format as due. If duration is set, defaults to due.
            duration: Duration like "1h", "30m", "1h30m". Requires a start or due date with a time.
            priority: Priority level: "none" (default), "low", "medium", "high".
            tags: List of tag names to apply.
            content: Markdown content/notes for the task.
            desc: Plain text description.
            items: List of checklist item titles.
            all_day: Whether this is an all-day task. Auto-detected from date format.
            timezone: IANA timezone name (e.g. "America/Chicago"). Defaults to system timezone.
        """
        client = _get_client(ctx)
        body: dict[str, Any] = {"title": title}

        if project:
            body["projectId"] = await _resolve_project_id(client, project)

        priority_level = PRIORITY_MAP.get(priority.lower())
        if priority_level is None:
            raise ToolError(f"Invalid priority '{priority}'. Use: none, low, medium, high")
        # "none" is the API default; omit it to keep the payload minimal.
        if priority_level != 0:
            body["priority"] = priority_level

        if tags:
            body["tags"] = tags
        if content is not None:
            body["content"] = content
        if desc is not None:
            body["desc"] = desc
        if items:
            body["items"] = [{"title": t, "status": 0} for t in items]

        parsed_due: ParsedDateTime | None = None
        parsed_start: ParsedDateTime | None = None

        if due:
            parsed_due = parse_datetime(due)
            body["dueDate"] = parsed_due.to_api_string(timezone)
            # Honor an explicit all_day override; otherwise infer it from whether
            # the caller supplied a time component.
            if all_day is None:
                body["isAllDay"] = parsed_due.is_all_day
            else:
                body["isAllDay"] = all_day

        if start:
            parsed_start = parse_datetime(start)
            body["startDate"] = parsed_start.to_api_string(timezone)
            if all_day is None and "isAllDay" not in body:
                body["isAllDay"] = parsed_start.is_all_day

        if duration:
            parsed_duration = parse_duration(duration)
            # A duration is only meaningful relative to an anchor instant, and
            # start takes precedence over due when both are present.
            anchor = parsed_start or parsed_due
            if anchor is None:
                raise ToolError("Duration requires a start or due date with a time component")
            if anchor.is_all_day:
                raise ToolError(
                    "Duration requires a date with a time component (use YYYY-MM-DDTHH:MM)"
                )
            end = anchor.add_duration(parsed_duration)
            # Fill in whichever endpoint the caller left implicit: given a start,
            # duration defines the due date; given only a due, it becomes the
            # start and due shifts out by the duration.
            if parsed_start and not parsed_due:
                body["dueDate"] = end.to_api_string(timezone)
            elif parsed_due and not parsed_start:
                body["startDate"] = parsed_due.to_api_string(timezone)
                body["dueDate"] = end.to_api_string(timezone)

        if timezone:
            body["timeZone"] = timezone

        return await client.v1_post("/task", body)

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        }
    )
    async def edit_task(
        ctx: Context,
        task_id: str,
        project: str,
        title: str | None = None,
        due: str | None = None,
        start: str | None = None,
        priority: str | None = None,
        tags: list[str] | None = None,
        content: str | None = None,
        desc: str | None = None,
        clear_due: bool = False,
        clear_start: bool = False,
        timezone: str | None = None,
    ) -> dict[str, Any]:
        """Update an existing task.

        Only provided fields are changed. Use clear_due/clear_start to remove dates.

        Args:
            task_id: The task ID to edit.
            project: The project name or ID containing the task.
            title: New task title.
            due: New due date ("today", "tomorrow", "YYYY-MM-DD", "YYYY-MM-DDTHH:MM").
            start: New start date.
            priority: New priority: "none", "low", "medium", "high".
            tags: Replace all tags with this list.
            content: New markdown content.
            desc: New plain text description.
            clear_due: Set to true to remove the due date.
            clear_start: Set to true to remove the start date.
            timezone: IANA timezone for date interpretation.
        """
        client = _get_client(ctx)
        project_id = await _resolve_project_id(client, project)
        body: dict[str, Any] = {"taskId": task_id, "projectId": project_id}

        if title is not None:
            body["title"] = title
        if tags is not None:
            body["tags"] = tags
        if content is not None:
            body["content"] = content
        if desc is not None:
            body["desc"] = desc

        if priority is not None:
            priority_level = PRIORITY_MAP.get(priority.lower())
            if priority_level is None:
                raise ToolError(f"Invalid priority '{priority}'. Use: none, low, medium, high")
            body["priority"] = priority_level

        if clear_due:
            body["dueDate"] = None
        elif due:
            parsed = parse_datetime(due)
            body["dueDate"] = parsed.to_api_string(timezone)
            body["isAllDay"] = parsed.is_all_day

        if clear_start:
            body["startDate"] = None
        elif start:
            parsed = parse_datetime(start)
            body["startDate"] = parsed.to_api_string(timezone)

        if timezone:
            body["timeZone"] = timezone

        return await client.v1_post(f"/task/{task_id}", body)

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        }
    )
    async def complete_task(
        ctx: Context,
        task_id: str,
        project: str,
    ) -> str:
        """Mark a task as complete.

        Args:
            task_id: The task ID to complete.
            project: The project name or ID containing the task.
        """
        client = _get_client(ctx)
        project_id = await _resolve_project_id(client, project)
        await client.v1_post_empty(f"/project/{project_id}/task/{task_id}/complete")
        return f"Task {task_id} completed"

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": True,
        }
    )
    async def delete_task(
        ctx: Context,
        task_id: str,
        project: str,
    ) -> str:
        """Permanently delete a task.

        This action cannot be undone. The task is moved to trash first but
        this API call removes it entirely.

        Args:
            task_id: The task ID to delete.
            project: The project name or ID containing the task.
        """
        client = _get_client(ctx)
        project_id = await _resolve_project_id(client, project)
        await client.v1_delete(f"/project/{project_id}/task/{task_id}")
        return f"Task {task_id} deleted"

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        }
    )
    async def move_task(
        ctx: Context,
        task_id: str,
        from_project: str,
        to_project: str,
    ) -> str:
        """Move a task from one project to another.

        Args:
            task_id: The task ID to move.
            from_project: Source project name or ID.
            to_project: Destination project name or ID.
        """
        client = _get_client(ctx)
        from_project_id = await _resolve_project_id(client, from_project)
        to_project_id = await _resolve_project_id(client, to_project)
        await client.v2_post(
            "/batch/taskProject",
            [{"taskId": task_id, "fromProjectId": from_project_id, "toProjectId": to_project_id}],
        )
        return f"Task {task_id} moved to {to_project}"

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        }
    )
    async def set_subtask(
        ctx: Context,
        task_id: str,
        parent_id: str,
        project: str,
    ) -> str:
        """Make a task a subtask of another task.

        Both tasks must be in the same project.

        Args:
            task_id: The task ID to make a subtask.
            parent_id: The parent task ID.
            project: The project name or ID containing both tasks.
        """
        client = _get_client(ctx)
        project_id = await _resolve_project_id(client, project)
        await client.v2_post(
            "/batch/taskParent",
            [{"taskId": task_id, "parentId": parent_id, "projectId": project_id}],
        )
        return f"Task {task_id} is now a subtask of {parent_id}"

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        }
    )
    async def unparent_task(
        ctx: Context,
        task_id: str,
        project: str,
    ) -> dict[str, Any]:
        """Remove a task's parent, making it a top-level task.

        Args:
            task_id: The task ID to unparent.
            project: The project name or ID containing the task.
        """
        client = _get_client(ctx)
        project_id = await _resolve_project_id(client, project)
        return await client.v1_post(
            f"/task/{task_id}", {"taskId": task_id, "projectId": project_id, "parentId": ""}
        )

    @mcp.tool(
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }
    )
    async def list_trash(ctx: Context) -> list[dict[str, Any]]:
        """List tasks in the trash.

        Returns tasks that have been deleted but not yet permanently removed.
        Requires v2 session token.
        """
        client = _get_client(ctx)
        data = await client.v2_get("/project/all/trash/page")
        return data.get("tasks") or []
