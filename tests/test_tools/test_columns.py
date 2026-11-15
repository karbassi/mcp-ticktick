from __future__ import annotations

import httpx
import pytest
import respx

from tests.helpers import body, call_tool, result_data
from ticktick_mcp.client import V1_BASE

PID = "a" * 24
C1 = "b" * 24
C2 = "c" * 24
COLUMNS = [
    {"id": C1, "projectId": PID, "name": "To do", "color": None, "sortOrder": 0},
    {"id": C2, "projectId": PID, "name": "Doing", "color": None, "sortOrder": 1},
]


@pytest.fixture
def columns(mock_api: respx.MockRouter) -> respx.Route:
    return mock_api.get(f"{V1_BASE}/project/{PID}/column").mock(
        return_value=httpx.Response(200, json=COLUMNS)
    )


@pytest.fixture
def projects(mock_api: respx.MockRouter) -> respx.Route:
    return mock_api.get(f"{V1_BASE}/project").mock(
        return_value=httpx.Response(200, json=[{"id": PID, "name": "Board"}])
    )


class TestListColumns:
    @pytest.mark.anyio
    async def test_list(self, env_vars, projects, columns):
        result = await call_tool("list_columns", {"project": "Board"})
        assert [c["name"] for c in result_data(result)] == ["To do", "Doing"]


class TestAddColumn:
    @pytest.mark.anyio
    async def test_add_minimal(self, env_vars, projects, mock_api: respx.MockRouter):
        route = mock_api.post(f"{V1_BASE}/project/{PID}/column").mock(
            return_value=httpx.Response(200, json={"id": "x", "name": "Done"})
        )
        await call_tool("add_column", {"project": "Board", "name": "Done"})
        assert body(route) == {"name": "Done"}

    @pytest.mark.anyio
    async def test_add_all_fields(self, env_vars, projects, mock_api: respx.MockRouter):
        route = mock_api.post(f"{V1_BASE}/project/{PID}/column").mock(
            return_value=httpx.Response(200, json={"id": "x", "name": "Done"})
        )
        await call_tool(
            "add_column",
            {"project": "Board", "name": "Done", "sort_order": 3, "color": "#FF0000"},
        )
        assert body(route) == {"name": "Done", "sortOrder": 3, "color": "#FF0000"}


class TestEditColumn:
    @pytest.mark.anyio
    async def test_edit_resolves_name(self, env_vars, projects, columns, mock_api):
        route = mock_api.post(f"{V1_BASE}/project/{PID}/column/{C2}").mock(
            return_value=httpx.Response(200, json={"id": C2, "name": "In progress"})
        )
        await call_tool(
            "edit_column", {"project": "Board", "column": "doing", "name": "In progress"}
        )
        assert body(route) == {"name": "In progress"}

    @pytest.mark.anyio
    async def test_edit_needs_a_field(self, env_vars, projects, columns):
        with pytest.raises(Exception, match="at least one"):
            await call_tool("edit_column", {"project": "Board", "column": "doing"})

    @pytest.mark.anyio
    async def test_unknown_column(self, env_vars, projects, columns):
        with pytest.raises(Exception, match="No column found"):
            await call_tool("edit_column", {"project": "Board", "column": "zzz", "name": "x"})


class TestTaskColumn:
    @pytest.mark.anyio
    async def test_add_task_with_column(self, env_vars, projects, columns, mock_api):
        route = mock_api.post(f"{V1_BASE}/task").mock(
            return_value=httpx.Response(200, json={"id": "t1"})
        )
        await call_tool("add_task", {"title": "T", "project": "Board", "column": "Doing"})
        assert body(route)["columnId"] == C2
        assert body(route)["projectId"] == PID

    @pytest.mark.anyio
    async def test_add_task_column_needs_project(self, env_vars):
        with pytest.raises(Exception, match="column requires project"):
            await call_tool("add_task", {"title": "T", "column": "Doing"})

    @pytest.mark.anyio
    async def test_edit_task_column(self, env_vars, projects, columns, mock_api):
        route = mock_api.post(f"{V1_BASE}/task/t1").mock(
            return_value=httpx.Response(200, json={"id": "t1"})
        )
        await call_tool("edit_task", {"task_id": "t1", "project": "Board", "column": "To do"})
        assert body(route)["columnId"] == C1
