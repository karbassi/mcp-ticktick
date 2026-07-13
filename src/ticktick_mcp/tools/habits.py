from __future__ import annotations

from typing import Any

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

from ticktick_mcp.client import TickTickClient
from ticktick_mcp.dates import date_to_stamp
from ticktick_mcp.models import Habit, HabitSection
from ticktick_mcp.resolve import _looks_like_id, resolve_name_with_etag


def _get_client(ctx: Context) -> TickTickClient:
    return ctx.request_context.lifespan_context["client"]  # type: ignore[union-attr]


async def _resolve_habit(client: TickTickClient, name_or_id: str) -> tuple[str, str]:
    """Resolve a habit name/ID to (id, etag)."""
    habits = await client.v2_get("/habits")
    parsed = [Habit(**h) for h in habits]
    return resolve_name_with_etag(
        name_or_id,
        parsed,
        lambda h: h.name or "",
        lambda h: h.id,
        lambda h: h.etag or "",
        "habit",
    )


async def _resolve_section(client: TickTickClient, name_or_id: str) -> tuple[str, str]:
    """Resolve a habit section name/ID to (id, name)."""
    sections = await client.v2_get("/habitSections")
    parsed = [HabitSection(**s) for s in sections]

    # This mirrors resolve_name but returns the section's name (not an etag),
    # which the batch endpoints need — so it can't reuse resolve_name_with_etag.
    if _looks_like_id(name_or_id):
        for s in parsed:
            if s.id == name_or_id:
                return s.id, s.name
        return name_or_id, ""

    search = name_or_id.lower()
    for s in parsed:
        if s.name.lower() == search:
            return s.id, s.name

    matches = [s for s in parsed if search in s.name.lower()]
    if len(matches) == 1:
        return matches[0].id, matches[0].name
    if len(matches) > 1:
        names = [s.name for s in matches]
        raise ToolError(f"Multiple sections match '{name_or_id}': {', '.join(names)}")

    raise ToolError(f"No habit section found matching '{name_or_id}'")


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }
    )
    async def list_habits(ctx: Context) -> list[dict[str, Any]]:
        """List all habits.

        Returns all habits with their IDs, names, types, goals, streaks, and sections.
        Requires v2 session token.
        """
        client = _get_client(ctx)
        return await client.v2_get("/habits")

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        }
    )
    async def add_habit(
        ctx: Context,
        name: str,
        habit_type: str = "Boolean",
        goal: float | None = None,
        unit: str | None = None,
        section: str | None = None,
        repeat_rule: str | None = None,
        color: str | None = None,
    ) -> Any:
        """Create a new habit.

        Args:
            name: Habit name (required).
            habit_type: "Boolean" for yes/no, "Numeric" for tracked values. Default: "Boolean".
            goal: Daily goal value (e.g. 8 for "8 glasses of water"). Default: 1 for Boolean.
            unit: Unit label for numeric habits (e.g. "glasses", "km", "pages").
            section: Habit section name or ID to group this habit under.
            repeat_rule: Repeat rule string (e.g. for specific days of the week).
            color: Hex color code (e.g. "#FF0000").
        """
        client = _get_client(ctx)
        habit: dict[str, Any] = {"name": name, "type": habit_type}
        if goal is not None:
            habit["goal"] = goal
        if unit is not None:
            habit["unit"] = unit
        if section:
            section_id, _ = await _resolve_section(client, section)
            habit["sectionId"] = section_id
        if repeat_rule is not None:
            habit["repeatRule"] = repeat_rule
        if color is not None:
            habit["color"] = color
        return await client.v2_post("/habits/batch", {"add": [habit]})

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        }
    )
    async def edit_habit(
        ctx: Context,
        habit: str,
        name: str | None = None,
        goal: float | None = None,
        unit: str | None = None,
        section: str | None = None,
        repeat_rule: str | None = None,
        color: str | None = None,
    ) -> Any:
        """Update an existing habit's properties.

        Only provided fields are changed.

        Args:
            habit: Habit name or ID. Supports fuzzy matching.
            name: New habit name.
            goal: New daily goal value.
            unit: New unit label.
            section: Move to this section (name or ID).
            repeat_rule: New repeat rule string.
            color: New hex color code.
        """
        client = _get_client(ctx)
        habit_id, etag = await _resolve_habit(client, habit)
        update: dict[str, Any] = {"id": habit_id, "etag": etag}
        if name is not None:
            update["name"] = name
        if goal is not None:
            update["goal"] = goal
        if unit is not None:
            update["unit"] = unit
        if section:
            section_id, _ = await _resolve_section(client, section)
            update["sectionId"] = section_id
        if repeat_rule is not None:
            update["repeatRule"] = repeat_rule
        if color is not None:
            update["color"] = color
        return await client.v2_post("/habits/batch", {"update": [update]})

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": True,
        }
    )
    async def delete_habits(
        ctx: Context,
        habits: list[str],
    ) -> str:
        """Delete one or more habits.

        Args:
            habits: List of habit names or IDs to delete. Supports fuzzy matching.
        """
        client = _get_client(ctx)
        ids = []
        for name_or_id in habits:
            habit_id, _ = await _resolve_habit(client, name_or_id)
            ids.append(habit_id)
        await client.v2_post("/habits/batch", {"delete": ids})
        return f"Deleted {len(ids)} habit(s)"

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        }
    )
    async def checkin_habit(
        ctx: Context,
        habit: str,
        date: str = "today",
        value: float = 1.0,
    ) -> Any:
        """Record a habit check-in for a given date.

        For Boolean habits, value=1 means done. For Numeric habits, value is the
        tracked amount (e.g. 3 for "3 glasses of water").

        Args:
            habit: Habit name or ID. Supports fuzzy matching.
            date: Check-in date: "today" (default), "yesterday", or "YYYY-MM-DD".
            value: Check-in value. Default: 1.0 (done for Boolean habits).
        """
        client = _get_client(ctx)
        habit_id, _ = await _resolve_habit(client, habit)
        stamp = date_to_stamp(date)
        return await client.v2_post(
            "/habitCheckins/batch",
            {"add": [{"habitId": habit_id, "checkinStamp": stamp, "value": value, "status": 0}]},
        )

    @mcp.tool(
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }
    )
    async def habit_log(
        ctx: Context,
        habits: list[str],
        after: str = "today",
    ) -> Any:
        """Query check-in history for one or more habits.

        Args:
            habits: List of habit names or IDs to query. Supports fuzzy matching.
            after: Return check-ins after this date: "today", "yesterday", "YYYY-MM-DD".
        """
        client = _get_client(ctx)
        ids = []
        for name_or_id in habits:
            habit_id, _ = await _resolve_habit(client, name_or_id)
            ids.append(habit_id)
        stamp = date_to_stamp(after)
        return await client.v2_post(
            "/habitCheckins/query",
            {"habitIds": ids, "afterStamp": stamp},
        )

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        }
    )
    async def archive_habits(
        ctx: Context,
        habits: list[str],
    ) -> Any:
        """Archive one or more habits (set status to inactive).

        Archived habits are hidden from the main view but retain their data.

        Args:
            habits: List of habit names or IDs to archive. Supports fuzzy matching.
        """
        client = _get_client(ctx)
        updates = []
        for name_or_id in habits:
            habit_id, etag = await _resolve_habit(client, name_or_id)
            updates.append({"id": habit_id, "etag": etag, "status": 1})
        return await client.v2_post("/habits/batch", {"update": updates})

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        }
    )
    async def manage_habit_sections(
        ctx: Context,
        action: str,
        name: str | None = None,
        section: str | None = None,
        new_name: str | None = None,
        sections: list[str] | None = None,
    ) -> Any:
        """Manage habit sections (groups for organizing habits).

        Consolidates list/add/delete/rename operations into one tool.

        Args:
            action: Operation to perform: "list", "add", "delete", "rename".
            name: Section name (required for "add").
            section: Section name or ID (required for "rename").
            new_name: New name (required for "rename").
            sections: List of section names or IDs (required for "delete").
        """
        client = _get_client(ctx)

        if action == "list":
            return await client.v2_get("/habitSections")

        if action == "add":
            if not name:
                raise ToolError("'name' is required for action='add'")
            return await client.v2_post("/habitSections/batch", {"add": [{"name": name}]})

        if action == "delete":
            if not sections:
                raise ToolError("'sections' is required for action='delete'")
            ids = []
            for s in sections:
                section_id, _ = await _resolve_section(client, s)
                ids.append(section_id)
            await client.v2_post("/habitSections/batch", {"delete": ids})
            return f"Deleted {len(ids)} section(s)"

        if action == "rename":
            if not section:
                raise ToolError("'section' is required for action='rename'")
            if not new_name:
                raise ToolError("'new_name' is required for action='rename'")
            section_id, _ = await _resolve_section(client, section)
            return await client.v2_post(
                "/habitSections/batch",
                {"update": [{"id": section_id, "name": new_name}]},
            )

        raise ToolError(f"Invalid action '{action}'. Use: list, add, delete, rename")
