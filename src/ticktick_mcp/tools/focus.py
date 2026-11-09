from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

from ticktick_mcp.client import TickTickClient


def _get_client(ctx: Context) -> TickTickClient:
    return ctx.request_context.lifespan_context["client"]  # type: ignore[union-attr]


def _to_iso(dt: datetime) -> str:
    """Format a datetime as ISO with +0000 UTC offset (TickTick format)."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}+0000"


FOCUS_TYPES = (0, 1)  # 0 = pomodoro, 1 = stopwatch
V1_FOCUS_MAX_RANGE = timedelta(days=30)


async def _v1_focus_records(
    client: TickTickClient, start: datetime, end: datetime
) -> list[dict[str, Any]]:
    """All focus records (both types) in [start, end], paged to the v1 30-day cap."""
    records: list[dict[str, Any]] = []
    chunk_start = start
    while chunk_start < end:
        chunk_end = min(chunk_start + V1_FOCUS_MAX_RANGE, end)
        for focus_type in FOCUS_TYPES:
            q = urlencode(
                {"from": _to_iso(chunk_start), "to": _to_iso(chunk_end), "type": focus_type}
            )
            records.extend(await client.v1_get(f"/focus?{q}") or [])
        chunk_start = chunk_end
    # Records spanning a chunk boundary come back in both chunks.
    unique = {r["id"]: r for r in records}
    return sorted(unique.values(), key=lambda r: r.get("startTime", ""))


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

        start = datetime.fromtimestamp(date_to_epoch_ms(from_date) / 1000, UTC)
        end = datetime.fromtimestamp(date_to_epoch_ms(to_date) / 1000, UTC) + timedelta(
            days=1, milliseconds=-1
        )  # End of day
        return await _v1_focus_records(client, start, end)

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

        record: dict[str, Any] = {
            "type": 0,
            "startTime": start_iso,
            "endTime": end_iso,
            "status": 1,
            "pauseDuration": 0,
            "note": note,
        }
        if task_id:
            task_entry: dict[str, Any] = {
                "taskId": task_id,
                "startTime": start_iso,
                "endTime": end_iso,
            }
            if project_id:
                task_entry["projectId"] = project_id
            record["taskId"] = task_id
            record["tasks"] = [task_entry]

        client = _get_client(ctx)
        return await client.v1_post("/focus", record)
