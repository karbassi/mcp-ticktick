from __future__ import annotations

import httpx
import pytest
import respx

from tests.helpers import call_tool, result_data
from ticktick_mcp.client import V1_BASE, TickTickClient


class TestListProjects:
    @pytest.mark.anyio
    async def test_list(self, client: TickTickClient, mock_api: respx.MockRouter):
        mock_api.get(f"{V1_BASE}/project").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"id": "p1", "name": "Work", "color": "#FF0000"},
                    {"id": "p2", "name": "Personal"},
                ],
            )
        )
        result = await client.v1_get("/project")
        assert len(result) == 2
        assert result[0]["name"] == "Work"


class TestGetProject:
    @pytest.mark.anyio
    async def test_get_by_id(self, client: TickTickClient, mock_api: respx.MockRouter):
        mock_api.get(f"{V1_BASE}/project/p1").mock(
            return_value=httpx.Response(200, json={"id": "p1", "name": "Work", "color": "#FF0000"})
        )
        result = await client.v1_get("/project/p1")
        assert result["id"] == "p1"
        assert result["name"] == "Work"


class TestCreateProject:
    @pytest.mark.anyio
    async def test_create(self, client: TickTickClient, mock_api: respx.MockRouter):
        mock_api.post(f"{V1_BASE}/project").mock(
            return_value=httpx.Response(200, json={"id": "p_new", "name": "New Project"})
        )
        result = await client.v1_post("/project", {"name": "New Project"})
        assert result["id"] == "p_new"


class TestDeleteProject:
    @pytest.mark.anyio
    async def test_delete(self, client: TickTickClient, mock_api: respx.MockRouter):
        mock_api.delete(f"{V1_BASE}/project/p1").mock(return_value=httpx.Response(200))
        resp = await client.v1_delete("/project/p1")
        assert resp.status_code == 200


class TestInboxDiscovery:
    @pytest.mark.anyio
    async def test_inbox_probe(self, client: TickTickClient, mock_api: respx.MockRouter):
        # Create temp task returns inbox project ID
        mock_api.post(f"{V1_BASE}/task").mock(
            return_value=httpx.Response(
                200, json={"id": "tmp1", "projectId": "inbox123", "title": "__inbox_probe__"}
            )
        )
        # Delete temp task
        mock_api.delete(f"{V1_BASE}/project/inbox123/task/tmp1").mock(
            return_value=httpx.Response(200)
        )

        # Simulate the inbox discovery flow
        task = await client.v1_post("/task", {"title": "__inbox_probe__"})
        inbox_id = task["projectId"]
        assert inbox_id == "inbox123"
        await client.v1_delete(f"/project/{inbox_id}/task/{task['id']}")


class TestListProjectMembers:
    @pytest.mark.anyio
    async def test_members(self, env_vars, mock_api: respx.MockRouter):
        mock_api.get(f"{V1_BASE}/project/inbox123/members").mock(
            return_value=httpx.Response(
                200, json=[{"username": "a@b.c", "displayName": "A", "self": True}]
            )
        )
        result = await call_tool("list_project_members", {"project": "inbox123"})
        assert result_data(result)[0]["username"] == "a@b.c"
