from __future__ import annotations

import json

import httpx
import pytest
import respx
from fastmcp.exceptions import ToolError

from tests.helpers import body, call_tool, result_data
from ticktick_mcp.client import V1_BASE, V2_BASE, TickTickClient


class TestListTasks:
    @pytest.mark.anyio
    async def test_list_by_project(self, client: TickTickClient, mock_api: respx.MockRouter):
        mock_api.get(f"{V1_BASE}/project").mock(
            return_value=httpx.Response(200, json=[{"id": "p1", "name": "Work"}])
        )
        mock_api.get(f"{V1_BASE}/project/p1/data").mock(
            return_value=httpx.Response(200, json={"tasks": [{"id": "t1", "title": "Task 1"}]})
        )
        data = await client.v1_get("/project/p1/data")
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["title"] == "Task 1"

    @pytest.mark.anyio
    async def test_list_completed(self, client: TickTickClient, mock_api: respx.MockRouter):
        mock_api.get(f"{V2_BASE}/project/all/completedInAll/?limit=50").mock(
            return_value=httpx.Response(200, json=[{"id": "t2", "title": "Done", "status": 2}])
        )
        result = await client.v2_get("/project/all/completedInAll/?limit=50")
        assert result[0]["status"] == 2


class TestAddTask:
    @pytest.mark.anyio
    async def test_create_simple(self, client: TickTickClient, mock_api: respx.MockRouter):
        mock_api.post(f"{V1_BASE}/task").mock(
            return_value=httpx.Response(
                200, json={"id": "t1", "title": "Buy milk", "projectId": "inbox123"}
            )
        )
        result = await client.v1_post("/task", {"title": "Buy milk"})
        assert result["id"] == "t1"
        assert result["title"] == "Buy milk"


class TestTaskReminders:
    @pytest.fixture
    def post_task(self, mock_api: respx.MockRouter):
        return mock_api.post(f"{V1_BASE}/task").mock(
            return_value=httpx.Response(200, json={"id": "t1", "title": "x"})
        )

    @pytest.mark.anyio
    async def test_timed_task_defaults_to_at_due_time(self, env_vars, post_task):
        await call_tool("add_task", {"title": "x", "due": "2027-03-01T10:00"})
        assert body(post_task)["reminders"] == ["TRIGGER:PT0S"]

    @pytest.mark.anyio
    async def test_all_day_task_defaults_to_9am(self, env_vars, post_task):
        await call_tool("add_task", {"title": "x", "due": "2027-03-01"})
        assert body(post_task)["reminders"] == ["TRIGGER:P0DT9H0M0S"]

    @pytest.mark.anyio
    async def test_start_only_task_gets_default(self, env_vars, post_task):
        await call_tool("add_task", {"title": "x", "start": "2027-03-01T10:00"})
        assert body(post_task)["reminders"] == ["TRIGGER:PT0S"]

    @pytest.mark.anyio
    async def test_all_day_flag_overrides_default(self, env_vars, post_task):
        await call_tool("add_task", {"title": "x", "due": "2027-03-01", "all_day": False})
        assert body(post_task)["reminders"] == ["TRIGGER:PT0S"]

    @pytest.mark.anyio
    async def test_no_date_means_no_default(self, env_vars, post_task):
        await call_tool("add_task", {"title": "x"})
        assert "reminders" not in body(post_task)

    @pytest.mark.anyio
    async def test_explicit_reminders_win(self, env_vars, post_task):
        await call_tool(
            "add_task", {"title": "x", "due": "2027-03-01T10:00", "reminders": ["TRIGGER:-PT15M"]}
        )
        assert body(post_task)["reminders"] == ["TRIGGER:-PT15M"]

    @pytest.mark.anyio
    async def test_empty_list_means_no_reminder(self, env_vars, post_task):
        await call_tool("add_task", {"title": "x", "due": "2027-03-01T10:00", "reminders": []})
        assert body(post_task)["reminders"] == []

    @pytest.mark.anyio
    async def test_edit_sends_reminders_only_when_passed(self, env_vars, mock_api):
        mock_api.get(f"{V1_BASE}/project").mock(
            return_value=httpx.Response(200, json=[{"id": "p1", "name": "Work"}])
        )
        route = mock_api.post(f"{V1_BASE}/task/t1").mock(
            return_value=httpx.Response(200, json={"id": "t1"})
        )
        await call_tool("edit_task", {"task_id": "t1", "project": "Work", "title": "y"})
        await call_tool("edit_task", {"task_id": "t1", "project": "Work", "reminders": []})
        await call_tool(
            "edit_task", {"task_id": "t1", "project": "Work", "reminders": ["TRIGGER:PT0S"]}
        )
        assert "reminders" not in body(route, 0)
        assert body(route, 1)["reminders"] == []
        assert body(route, 2)["reminders"] == ["TRIGGER:PT0S"]

    @pytest.mark.anyio
    async def test_edit_with_date_does_not_add_default(self, env_vars, mock_api):
        mock_api.get(f"{V1_BASE}/project").mock(
            return_value=httpx.Response(200, json=[{"id": "p1", "name": "Work"}])
        )
        route = mock_api.post(f"{V1_BASE}/task/t1").mock(
            return_value=httpx.Response(200, json={"id": "t1"})
        )
        await call_tool(
            "edit_task", {"task_id": "t1", "project": "Work", "due": "2027-03-01T10:00"}
        )
        assert "reminders" not in body(route)


class TestCompleteTask:
    @pytest.mark.anyio
    async def test_complete(self, client: TickTickClient, mock_api: respx.MockRouter):
        mock_api.post(f"{V1_BASE}/project/p1/task/t1/complete").mock(
            return_value=httpx.Response(200)
        )
        resp = await client.v1_post_empty("/project/p1/task/t1/complete")
        assert resp.status_code == 200


class TestCompleteTasksBatch:
    @pytest.mark.anyio
    async def test_single_uses_single_endpoint(self, env_vars, mock_api: respx.MockRouter):
        single = mock_api.post(f"{V1_BASE}/project/aaaaaaaaaaaaaaaaaaaaaaaa/task/t1/complete").mock(
            return_value=httpx.Response(200)
        )
        mock_api.get(f"{V1_BASE}/project").mock(return_value=httpx.Response(200, json=[]))
        batch = mock_api.post(f"{V1_BASE}/task/completeTasks")
        res = await call_tool(
            "complete_task", {"task_id": "t1", "project": "aaaaaaaaaaaaaaaaaaaaaaaa"}
        )
        assert single.called and not batch.called
        assert result_data(res) == "Task t1 completed"

    @pytest.mark.anyio
    async def test_several_use_batch_endpoint(self, env_vars, mock_api: respx.MockRouter):
        mock_api.get(f"{V1_BASE}/project").mock(return_value=httpx.Response(200, json=[]))
        route = mock_api.post(f"{V1_BASE}/task/completeTasks").mock(
            return_value=httpx.Response(200, json=["t1", "t2"])
        )
        res = await call_tool(
            "complete_task",
            {"task_ids": ["t1", "t2", "t1"], "project": "aaaaaaaaaaaaaaaaaaaaaaaa"},
        )
        assert body(route) == {"projectId": "aaaaaaaaaaaaaaaaaaaaaaaa", "taskIds": ["t1", "t2"]}
        assert result_data(res) == "Completed 2 of 2 tasks"

    @pytest.mark.anyio
    async def test_chunks_of_50_and_reports_failures(self, env_vars, mock_api: respx.MockRouter):
        mock_api.get(f"{V1_BASE}/project").mock(return_value=httpx.Response(200, json=[]))
        ids = [f"t{i}" for i in range(120)]
        route = mock_api.post(f"{V1_BASE}/task/completeTasks").mock(
            side_effect=lambda req: httpx.Response(
                200, json=[t for t in json.loads(req.content)["taskIds"] if t != "t7"]
            )
        )
        res = await call_tool(
            "complete_task", {"task_ids": ids, "project": "aaaaaaaaaaaaaaaaaaaaaaaa"}
        )
        assert [len(body(route, i)["taskIds"]) for i in range(route.call_count)] == [50, 50, 20]
        assert result_data(res) == "Completed 119 of 120 tasks; not completed: t7"

    @pytest.mark.anyio
    async def test_requires_an_id(self, env_vars, mock_api: respx.MockRouter):
        with pytest.raises(ToolError):
            await call_tool("complete_task", {"project": "aaaaaaaaaaaaaaaaaaaaaaaa"})


class TestDeleteTask:
    @pytest.mark.anyio
    async def test_delete(self, client: TickTickClient, mock_api: respx.MockRouter):
        mock_api.delete(f"{V1_BASE}/project/p1/task/t1").mock(return_value=httpx.Response(200))
        resp = await client.v1_delete("/project/p1/task/t1")
        assert resp.status_code == 200


class TestMoveTask:
    @pytest.mark.anyio
    async def test_move_uses_v1(self, env_vars, mock_api: respx.MockRouter):
        route = mock_api.post(f"{V1_BASE}/task/move").mock(
            return_value=httpx.Response(200, json=[{"id": "t1"}])
        )
        mock_api.get(f"{V1_BASE}/project").mock(return_value=httpx.Response(200, json=[]))
        v2 = mock_api.post(f"{V2_BASE}/batch/taskProject")
        await call_tool(
            "move_task",
            {
                "task_id": "t1",
                "from_project": "inbox123",
                "to_project": "aaaaaaaaaaaaaaaaaaaaaaaa",
            },
        )
        assert not v2.called
        assert body(route) == [
            {
                "taskId": "t1",
                "fromProjectId": "inbox123",
                "toProjectId": "aaaaaaaaaaaaaaaaaaaaaaaa",
            }
        ]


class TestSetSubtask:
    @pytest.mark.anyio
    async def test_set_parent(self, client: TickTickClient, mock_api: respx.MockRouter):
        mock_api.post(f"{V2_BASE}/batch/taskParent").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        result = await client.v2_post(
            "/batch/taskParent",
            [{"taskId": "t2", "parentId": "t1", "projectId": "p1"}],
        )
        assert result["ok"] is True


class TestListTrash:
    @pytest.mark.anyio
    async def test_trash(self, client: TickTickClient, mock_api: respx.MockRouter):
        mock_api.get(f"{V2_BASE}/project/all/trash/page").mock(
            return_value=httpx.Response(200, json={"tasks": [{"id": "t1", "title": "Trashed"}]})
        )
        data = await client.v2_get("/project/all/trash/page")
        assert len(data["tasks"]) == 1


class TestAssignTask:
    @pytest.mark.anyio
    async def test_assign(self, env_vars, mock_api: respx.MockRouter):
        route = mock_api.post(f"{V1_BASE}/task/assign").mock(
            return_value=httpx.Response(200, json={"id": "t1", "assigneeUsername": "bob"})
        )
        result = await call_tool(
            "assign_task", {"task_id": "t1", "project": "inbox123", "assignee": "bob"}
        )
        assert body(route) == {"projectId": "inbox123", "taskId": "t1", "assigneeUsername": "bob"}
        assert result_data(result)["id"] == "t1"

    @pytest.mark.anyio
    async def test_assign_error_is_tool_error(self, env_vars, mock_api: respx.MockRouter):
        mock_api.post(f"{V1_BASE}/task/assign").mock(return_value=httpx.Response(500, json={}))
        with pytest.raises(ToolError, match="shared project"):
            await call_tool(
                "assign_task", {"task_id": "t1", "project": "inbox123", "assignee": "x"}
            )

    @pytest.mark.anyio
    async def test_unassign(self, env_vars, mock_api: respx.MockRouter):
        route = mock_api.post(f"{V1_BASE}/task/unassign").mock(
            return_value=httpx.Response(200, json={"id": "t1"})
        )
        await call_tool("unassign_task", {"task_id": "t1", "project": "inbox123"})
        assert body(route) == {"projectId": "inbox123", "taskId": "t1"}
