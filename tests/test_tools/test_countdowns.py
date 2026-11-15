from __future__ import annotations

import httpx
import pytest
import respx

from tests.helpers import call_tool, result_data
from ticktick_mcp.client import V1_BASE, V2_BASE


class TestListCountdowns:
    @pytest.mark.anyio
    async def test_list_uses_v1(self, env_vars, mock_api: respx.MockRouter):
        v1 = mock_api.get(f"{V1_BASE}/countdown").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"id": "c1", "name": "Birthday", "date": 19860506},
                    {"id": "c2", "name": "Anniversary", "date": 20180630},
                ],
            )
        )
        v2 = mock_api.get(f"{V2_BASE}/batch/check/0")
        result = await call_tool("list_countdowns", {})
        assert v1.called
        assert not v2.called
        data = result_data(result)
        assert [c["name"] for c in data] == ["Birthday", "Anniversary"]
        assert data[0]["date"] == 19860506

    @pytest.mark.anyio
    async def test_list_empty(self, env_vars, mock_api: respx.MockRouter):
        mock_api.get(f"{V1_BASE}/countdown").mock(return_value=httpx.Response(200, json=[]))
        assert result_data(await call_tool("list_countdowns", {})) == []
