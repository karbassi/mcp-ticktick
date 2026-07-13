from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Any

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

from ticktick_mcp.client import TickTickClient

_MS_PER_DAY = 86_400_000


def _get_client(ctx: Context) -> TickTickClient:
    return ctx.request_context.lifespan_context["client"]  # type: ignore[union-attr]


def _generate_focus_id() -> str:
    """Mint a client-side ID for a focus record.

    TickTick expects the client to supply the record's ID rather than assigning
    one server-side. It only needs to be unique per creation, so the current
    millisecond plus a derived tail is plenty — collisions would require two
    saves within the same millisecond.
    """
    ms = int(time.time() * 1000)
    tail = ms ^ 0xDEAD_BEEF_CAFE_BABE
    return f"{ms:x}{tail & 0xFFFFFFFF:08x}"


def _to_iso(dt: datetime) -> str:
    """Format a datetime as ISO with +0000 UTC offset (TickTick format)."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}+0000"


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }
    )
    async def focus_status(ctx: Context) -> Any:
        """Get the current focus/pomodoro timer status.

        Returns the active timer state including elapsed time, task association,
        and whether it's running or paused. Requires v2 session token.
        """
        client = _get_client(ctx)
        return await client.v2_get("/timer")

    @mcp.tool(
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }
    )
    async def focus_stats(ctx: Context) -> Any:
        """Get focus/pomodoro statistics.

        Returns daily and total focus time statistics including session counts
        and total minutes. Requires v2 session token.

        Note: "total" fields may exclude the current day (TickTick caches these).
        Use focus_log for accurate current-day data.
        """
        client = _get_client(ctx)
        return await client.v2_get("/pomodoros/statistics/generalForDesktop")

    @mcp.tool(
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }
    )
    async def focus_log(
        ctx: Context,
        from_date: str,
        to_date: str,
    ) -> Any:
        """Get focus session log for a date range.

        Args:
            from_date: Start date: "today", "yesterday", or "YYYY-MM-DD".
            to_date: End date: "today", "yesterday", or "YYYY-MM-DD".
        """
        client = _get_client(ctx)
        from ticktick_mcp.dates import date_to_epoch_ms

        from_ms = date_to_epoch_ms(from_date)
        # date_to_epoch_ms returns midnight; extend to the day's last millisecond
        # so the range covers all of to_date, not just its opening instant.
        to_ms = date_to_epoch_ms(to_date) + _MS_PER_DAY - 1
        return await client.v2_get(f"/pomodoros?from={from_ms}&to={to_ms}")

    @mcp.tool(
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }
    )
    async def focus_timeline(ctx: Context) -> Any:
        """Get the full focus session timeline.

        Returns all focus sessions in chronological order.
        Requires v2 session token.
        """
        client = _get_client(ctx)
        return await client.v2_get("/pomodoros/timeline")

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        }
    )
    async def focus_save(
        ctx: Context,
        duration_minutes: int,
        end: str = "now",
        note: str = "",
        task_id: str | None = None,
        project_id: str | None = None,
    ) -> Any:
        """Save a completed focus/pomodoro record.

        Records a focus session that has already happened. This does not start
        a live timer — it saves a historical record.

        Args:
            duration_minutes: Duration of the focus session in minutes. Must be >= 1.
            end: End time: "now" (default) or ISO datetime string (e.g. "2026-02-22T14:30:00").
            note: Optional note to attach to the session.
            task_id: Optional task ID to associate with the session.
            project_id: Optional project ID (required if task_id is provided).
        """
        if duration_minutes < 1:
            raise ToolError("duration_minutes must be >= 1")

        if end == "now":
            end_dt = datetime.now(UTC)
        else:
            try:
                end_dt = datetime.fromisoformat(end).astimezone(UTC)
            except ValueError:
                raise ToolError(
                    f"Invalid end time '{end}'. Use 'now' or ISO format like '2026-02-22T14:30:00'."
                ) from None

        start_dt = end_dt - timedelta(minutes=duration_minutes)

        start_iso = _to_iso(start_dt)
        end_iso = _to_iso(end_dt)

        task_entry: dict[str, Any] = {
            "startTime": start_iso,
            "endTime": end_iso,
            "title": "",
        }
        if task_id:
            task_entry["taskId"] = task_id
        if project_id:
            task_entry["projectId"] = project_id

        record: dict[str, Any] = {
            "id": _generate_focus_id(),
            "startTime": start_iso,
            "endTime": end_iso,
            "status": 1,
            "pauseDuration": 0,
            "tasks": [task_entry],
            "note": note,
        }

        client = _get_client(ctx)
        return await client.v2_post(
            "/batch/pomodoro",
            {"add": [record], "update": [], "delete": []},
        )
