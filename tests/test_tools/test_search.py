from __future__ import annotations

import httpx
import pytest
import respx

from tests.helpers import body, call_tool, result_data
from ticktick_mcp.client import V1_BASE


class TestSearchTasks:
    @pytest.mark.anyio
    async def test_keyword_only(self, env_vars, mock_api: respx.MockRouter):
        route = mock_api.post(f"{V1_BASE}/task/search").mock(
            return_value=httpx.Response(200, json=[{"id": "t1", "title": "Quokka"}])
        )
        result = await call_tool("search_tasks", {"query": "quokka"})
        assert body(route) == {"keywords": "quokka"}
        assert result_data(result)[0]["id"] == "t1"

    @pytest.mark.anyio
    async def test_all_options(self, env_vars, mock_api: respx.MockRouter):
        mock_api.get(f"{V1_BASE}/project").mock(
            return_value=httpx.Response(200, json=[{"id": "p1", "name": "Work"}])
        )
        route = mock_api.post(f"{V1_BASE}/task/search").mock(
            return_value=httpx.Response(200, json=[])
        )
        await call_tool(
            "search_tasks",
            {
                "query": "plan",
                "projects": ["Work"],
                "tags": ["a"],
                "status": ["active", "completed"],
                "due_from": "2030-01-01",
                "due_to": "2030-02-01T09:30",
            },
        )
        sent = body(route)
        assert sent["projectIds"] == ["p1"]
        assert sent["tags"] == ["a"]
        assert sent["status"] == [0, 2]
        assert sent["dueFrom"].startswith("2030-01-01T00:00:00.000")
        assert sent["dueTo"].startswith("2030-02-01T09:30:00.000")

    @pytest.mark.anyio
    async def test_empty_response_is_empty_list(self, env_vars, mock_api: respx.MockRouter):
        mock_api.post(f"{V1_BASE}/task/search").mock(return_value=httpx.Response(200))
        result = await call_tool("search_tasks", {"query": "nothing"})
        assert result_data(result) == []

    @pytest.mark.anyio
    async def test_bad_status_rejected(self, env_vars, mock_api: respx.MockRouter):
        route = mock_api.post(f"{V1_BASE}/task/search")
        with pytest.raises(Exception, match="Invalid status"):
            await call_tool("search_tasks", {"query": "x", "status": ["done"]})
        assert not route.called


class TestFilterTasks:
    @pytest.mark.anyio
    async def test_all_options(self, env_vars, mock_api: respx.MockRouter):
        mock_api.get(f"{V1_BASE}/project").mock(
            return_value=httpx.Response(200, json=[{"id": "p1", "name": "Work"}])
        )
        route = mock_api.post(f"{V1_BASE}/task/filter").mock(
            return_value=httpx.Response(200, json=[{"id": "t1"}])
        )
        result = await call_tool(
            "filter_tasks",
            {
                "projects": ["Work"],
                "start_date": "2030-01-01",
                "end_date": "2030-02-01",
                "priority": ["high", "medium"],
                "tags": ["a", "b"],
                "status": ["abandoned"],
                "kind": ["checklist", "text"],
            },
        )
        sent = body(route)
        assert sent["projectIds"] == ["p1"]
        assert sent["priority"] == [5, 3]
        assert sent["tag"] == ["a", "b"]
        assert sent["status"] == [-1]
        assert sent["kind"] == ["CHECKLIST", "TASK"]
        assert sent["startDate"].startswith("2030-01-01")
        assert sent["endDate"].startswith("2030-02-01")
        assert result_data(result) == [{"id": "t1"}]

    @pytest.mark.anyio
    async def test_no_criteria_sends_empty_body(self, env_vars, mock_api: respx.MockRouter):
        route = mock_api.post(f"{V1_BASE}/task/filter").mock(
            return_value=httpx.Response(200, json=[])
        )
        await call_tool("filter_tasks", {})
        assert body(route) == {}

    @pytest.mark.anyio
    async def test_bad_priority_and_kind_rejected(self, env_vars, mock_api: respx.MockRouter):
        route = mock_api.post(f"{V1_BASE}/task/filter")
        with pytest.raises(Exception, match="Invalid priority"):
            await call_tool("filter_tasks", {"priority": ["urgent"]})
        with pytest.raises(Exception, match="Invalid kind"):
            await call_tool("filter_tasks", {"kind": ["todo"]})
        assert not route.called
