from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastmcp import FastMCP


def register_tools(mcp: FastMCP) -> None:
    from ticktick_mcp.tools import (
        calendar,
        comments,
        countdowns,
        filters,
        focus,
        folders,
        habits,
        projects,
        search,
        tags,
        tasks,
    )

    tasks.register(mcp)
    comments.register(mcp)
    projects.register(mcp)
    search.register(mcp)
    tags.register(mcp)
    folders.register(mcp)
    habits.register(mcp)
    filters.register(mcp)
    focus.register(mcp)
    calendar.register(mcp)
    countdowns.register(mcp)
