from __future__ import annotations

import httpx
import pytest
import respx

from tests.helpers import body, call_tool
from ticktick_mcp.client import V1_BASE, V2_BASE

GROUPS = [
    {"id": "g1", "name": "Home", "sortOrder": 0, "showAll": True},
    {"id": "g2", "name": "Work", "sortOrder": 1, "showAll": True},
]


@pytest.fixture
def groups(mock_api: respx.MockRouter) -> respx.Route:
    return mock_api.get(f"{V1_BASE}/project/group").mock(
        return_value=httpx.Response(200, json=GROUPS)
    )


class TestListFolders:
    @pytest.mark.anyio
    async def test_list_uses_v1(self, env_vars, groups, mock_api: respx.MockRouter):
        v2 = mock_api.get(f"{V2_BASE}/batch/check/0")
        result = await call_tool("list_folders", {})
        assert groups.called
        assert not v2.called
        assert [g["name"] for g in result.structured_content["result"]] == ["Home", "Work"]


class TestAddFolder:
    @pytest.mark.anyio
    async def test_add(self, env_vars, mock_api: respx.MockRouter):
        route = mock_api.post(f"{V1_BASE}/project/group").mock(
            return_value=httpx.Response(200, json={"id": "g3", "name": "Errands"})
        )
        await call_tool("add_folder", {"name": "Errands"})
        assert body(route) == {"name": "Errands"}


class TestDeleteFolders:
    @pytest.mark.anyio
    async def test_delete_resolves_names(self, env_vars, groups, mock_api: respx.MockRouter):
        g1 = mock_api.delete(f"{V1_BASE}/project/group/g1").mock(return_value=httpx.Response(200))
        g2 = mock_api.delete(f"{V1_BASE}/project/group/g2").mock(return_value=httpx.Response(200))
        await call_tool("delete_folders", {"folders": ["home", "Work"]})
        assert g1.called
        assert g2.called


class TestRenameFolder:
    @pytest.mark.anyio
    async def test_rename(self, env_vars, groups, mock_api: respx.MockRouter):
        route = mock_api.post(f"{V1_BASE}/project/group/g2").mock(
            return_value=httpx.Response(200, json={"id": "g2", "name": "Job"})
        )
        await call_tool("rename_folder", {"folder": "Work", "new_name": "Job"})
        assert body(route) == {"name": "Job"}
