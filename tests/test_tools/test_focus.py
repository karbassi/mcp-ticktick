from __future__ import annotations

import httpx
import pytest
import respx

from tests.helpers import body, call_tool, result_data
from ticktick_mcp.client import V1_BASE, V2_BASE, TickTickClient


class TestFocusStatus:
    @pytest.mark.anyio
    async def test_status(self, client: TickTickClient, mock_api: respx.MockRouter):
        mock_api.get(f"{V2_BASE}/timer").mock(
            return_value=httpx.Response(
                200, json={"id": "fs1", "status": "running", "elapsed": 600000}
            )
        )
        result = await client.v2_get("/timer")
        assert result["id"] == "fs1"
        assert result["status"] == "running"


class TestFocusStats:
    @pytest.mark.anyio
    async def test_stats(self, client: TickTickClient, mock_api: respx.MockRouter):
        mock_api.get(f"{V2_BASE}/pomodoros/statistics/generalForDesktop").mock(
            return_value=httpx.Response(200, json={"todayFocus": 3600000, "totalSessions": 42})
        )
        result = await client.v2_get("/pomodoros/statistics/generalForDesktop")
        assert result["totalSessions"] == 42


class TestFocusLog:
    @pytest.mark.anyio
    async def test_log_queries_both_types_in_30_day_chunks(
        self, env_vars, mock_api: respx.MockRouter
    ):
        route = mock_api.get(f"{V1_BASE}/focus").mock(
            side_effect=lambda req: httpx.Response(
                200,
                json=[
                    {
                        "id": f"f{req.url.params['type']}",
                        "startTime": f"2026-0{int(req.url.params['type']) + 1}-01",
                    }
                ],
            )
        )
        v2 = mock_api.get(url__regex=r".*/pomodoros\?.*")
        result = await call_tool("focus_log", {"from_date": "2026-01-01", "to_date": "2026-02-14"})
        assert not v2.called
        # 45 days -> 2 chunks x 2 types
        assert route.call_count == 4
        assert {c.request.url.params["type"] for c in route.calls} == {"0", "1"}
        assert route.calls[0].request.url.params["from"] == "2026-01-01T00:00:00.000+0000"
        assert route.calls[-1].request.url.params["to"] == "2026-02-14T23:59:59.999+0000"
        # Duplicates across chunks collapse; sorted by start
        assert [r["id"] for r in result_data(result)] == ["f0", "f1"]


class TestFocusTimeline:
    @pytest.mark.anyio
    async def test_timeline(self, client: TickTickClient, mock_api: respx.MockRouter):
        mock_api.get(f"{V2_BASE}/pomodoros/timeline").mock(
            return_value=httpx.Response(
                200, json={"sessions": [{"id": "p1", "start": "2026-02-22"}]}
            )
        )
        result = await client.v2_get("/pomodoros/timeline")
        assert "sessions" in result


class TestFocusSave:
    @pytest.mark.anyio
    async def test_save_basic(self, env_vars, mock_api: respx.MockRouter):
        route = mock_api.post(f"{V1_BASE}/focus").mock(
            return_value=httpx.Response(200, json={"id": "f1"})
        )
        await call_tool("focus_save", {"duration_minutes": 25, "end": "2026-02-22T14:25:00+00:00"})
        assert body(route) == {
            "type": 0,
            "startTime": "2026-02-22T14:00:00.000+0000",
            "endTime": "2026-02-22T14:25:00.000+0000",
            "status": 1,
            "pauseDuration": 0,
            "note": "",
        }

    @pytest.mark.anyio
    async def test_save_with_task(self, env_vars, mock_api: respx.MockRouter):
        route = mock_api.post(f"{V1_BASE}/focus").mock(
            return_value=httpx.Response(200, json={"id": "f1"})
        )
        await call_tool(
            "focus_save",
            {
                "duration_minutes": 25,
                "end": "2026-02-22T14:25:00+00:00",
                "note": "Deep work session",
                "task_id": "task1",
                "project_id": "proj1",
            },
        )
        record = body(route)
        assert record["taskId"] == "task1"
        assert record["tasks"] == [
            {
                "taskId": "task1",
                "startTime": "2026-02-22T14:00:00.000+0000",
                "endTime": "2026-02-22T14:25:00.000+0000",
                "projectId": "proj1",
            }
        ]
        assert record["note"] == "Deep work session"
