from __future__ import annotations

import httpx
import pytest
import respx

from tests.helpers import body, call_tool, result_data
from ticktick_mcp.client import V1_BASE

COMMENTS = [
    {"id": "c1", "userId": 1, "title": "first", "createdTime": 1, "modifiedTime": 1},
    {"id": "c2", "userId": 1, "title": "second", "createdTime": 2, "modifiedTime": 2},
]


@pytest.fixture
def projects(mock_api: respx.MockRouter) -> respx.Route:
    return mock_api.get(f"{V1_BASE}/project").mock(
        return_value=httpx.Response(200, json=[{"id": "p1", "name": "Work"}])
    )


class TestListComments:
    @pytest.mark.anyio
    async def test_list(self, env_vars, projects, mock_api: respx.MockRouter):
        route = mock_api.get(f"{V1_BASE}/project/p1/task/t1/comments").mock(
            return_value=httpx.Response(200, json=COMMENTS)
        )
        result = await call_tool("list_comments", {"task_id": "t1", "project": "work"})
        assert route.called
        assert [c["title"] for c in result_data(result)] == ["first", "second"]

    @pytest.mark.anyio
    async def test_list_empty_body(self, env_vars, projects, mock_api: respx.MockRouter):
        mock_api.get(f"{V1_BASE}/project/p1/task/t1/comments").mock(
            return_value=httpx.Response(200, json=[])
        )
        result = await call_tool("list_comments", {"task_id": "t1", "project": "Work"})
        assert result_data(result) == []


class TestAddComment:
    @pytest.mark.anyio
    async def test_add_sends_title(self, env_vars, projects, mock_api: respx.MockRouter):
        route = mock_api.post(f"{V1_BASE}/project/p1/task/t1/comment").mock(
            return_value=httpx.Response(200, json={"id": "c3", "title": "hello"})
        )
        result = await call_tool(
            "add_comment", {"task_id": "t1", "project": "Work", "text": "hello"}
        )
        assert body(route) == {"title": "hello"}
        assert result_data(result)["id"] == "c3"


class TestDeleteComment:
    @pytest.mark.anyio
    async def test_delete(self, env_vars, projects, mock_api: respx.MockRouter):
        route = mock_api.delete(f"{V1_BASE}/project/p1/task/t1/comment/c1").mock(
            return_value=httpx.Response(200)
        )
        result = await call_tool(
            "delete_comment", {"task_id": "t1", "project": "Work", "comment_id": "c1"}
        )
        assert route.called
        assert "c1" in result_data(result)
