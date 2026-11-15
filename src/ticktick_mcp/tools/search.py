from __future__ import annotations

from typing import Any

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

from ticktick_mcp.client import TickTickClient
from ticktick_mcp.dates import parse_datetime
from ticktick_mcp.tools.tasks import PRIORITY_MAP, _resolve_project_id

STATUS_MAP = {"active": 0, "completed": 2, "abandoned": -1}
# The filter endpoint calls plain text tasks "TASK" (verified live), though tasks report "TEXT".
KIND_MAP = {"text": "TASK", "task": "TASK", "note": "NOTE", "checklist": "CHECKLIST"}

_READ_ONLY = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}


def _get_client(ctx: Context) -> TickTickClient:
    return ctx.request_context.lifespan_context["client"]  # type: ignore[union-attr]


async def _project_ids(client: TickTickClient, projects: list[str] | None) -> list[str] | None:
    if not projects:
        return None
    return [await _resolve_project_id(client, p) for p in projects]


def _statuses(statuses: list[str] | None) -> list[int] | None:
    if not statuses:
        return None
    out: list[int] = []
    for s in statuses:
        val = STATUS_MAP.get(s.lower())
        if val is None:
            raise ToolError(f"Invalid status '{s}'. Use: {', '.join(STATUS_MAP)}")
        out.append(val)
    return out


def _priorities(priorities: list[str] | None) -> list[int] | None:
    if not priorities:
        return None
    out: list[int] = []
    for p in priorities:
        val = PRIORITY_MAP.get(p.lower())
        if val is None:
            raise ToolError(f"Invalid priority '{p}'. Use: {', '.join(PRIORITY_MAP)}")
        out.append(val)
    return out


def _kinds(kinds: list[str] | None) -> list[str] | None:
    if not kinds:
        return None
    out: list[str] = []
    for k in kinds:
        val = KIND_MAP.get(k.lower())
        if val is None:
            raise ToolError(f"Invalid kind '{k}'. Use: text, note, checklist")
        out.append(val)
    return out


def _date(value: str | None) -> str | None:
    return parse_datetime(value).to_api_string() if value else None


def _compact(body: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in body.items() if v is not None}


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=_READ_ONLY)
    async def search_tasks(
        ctx: Context,
        query: str,
        projects: list[str] | None = None,
        tags: list[str] | None = None,
        status: list[str] | None = None,
        due_from: str | None = None,
        due_to: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search tasks by keyword, server-side.

        Matches whole words in task titles and content, case-insensitively
        ("quokka" finds "Quokka plan", "quok" does not). Faster than listing every
        project and scanning. For criteria without a keyword (priority, date range,
        kind), use filter_tasks.

        Args:
            query: Keyword(s) to search for.
            projects: Only search these projects (names or IDs; "inbox" works).
            tags: Only tasks with these tags.
            status: Statuses to include: "active", "completed", "abandoned".
            due_from: Earliest due date: "today", "tomorrow", "YYYY-MM-DD", or "YYYY-MM-DDTHH:MM".
            due_to: Latest due date, same formats.
        """
        client = _get_client(ctx)
        body = _compact(
            {
                "keywords": query,
                "projectIds": await _project_ids(client, projects),
                "tags": tags or None,
                "status": _statuses(status),
                "dueFrom": _date(due_from),
                "dueTo": _date(due_to),
            }
        )
        return await client.v1_post("/task/search", body) or []

    @mcp.tool(annotations=_READ_ONLY)
    async def filter_tasks(
        ctx: Context,
        projects: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        priority: list[str] | None = None,
        tags: list[str] | None = None,
        status: list[str] | None = None,
        kind: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Filter tasks by project, date range, priority, tags, status, or kind, server-side.

        All criteria are optional and combine. No keyword matching; use search_tasks
        for that. Not related to the saved filters (list_filters and friends).

        Args:
            projects: Only these projects (names or IDs; "inbox" works).
            start_date: Earliest task start date: "today", "tomorrow", "YYYY-MM-DD",
                or "YYYY-MM-DDTHH:MM".
            end_date: Latest task start date, same formats.
            priority: Priorities to include: "none", "low", "medium", "high".
            tags: Only tasks with these tags.
            status: Statuses to include: "active", "completed", "abandoned".
            kind: Task kinds to include: "text", "note", "checklist".
        """
        client = _get_client(ctx)
        body = _compact(
            {
                "projectIds": await _project_ids(client, projects),
                "startDate": _date(start_date),
                "endDate": _date(end_date),
                "priority": _priorities(priority),
                "tag": tags or None,
                "status": _statuses(status),
                "kind": _kinds(kind),
            }
        )
        return await client.v1_post("/task/filter", body) or []
