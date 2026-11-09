from __future__ import annotations

import json

import httpx
import pytest
import respx

from tests.helpers import body, call_tool, result_data
from ticktick_mcp.client import V1_BASE, V2_BASE, TickTickClient


class TestListTags:
    @pytest.mark.anyio
    async def test_list_uses_v1(self, env_vars, mock_api: respx.MockRouter):
        v1 = mock_api.get(f"{V1_BASE}/tag").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"name": "work", "label": "work", "color": "#FF0000"},
                    {"name": "personal", "label": "personal", "parent": "life"},
                ],
            )
        )
        v2 = mock_api.get(f"{V2_BASE}/tags")
        result = await call_tool("list_tags", {})
        assert v1.called
        assert not v2.called
        assert [t["name"] for t in result_data(result)] == ["work", "personal"]


class TestAddTags:
    @pytest.mark.anyio
    async def test_add_posts_each_name_to_v1(self, env_vars, mock_api: respx.MockRouter):
        route = mock_api.post(f"{V1_BASE}/tag").mock(
            side_effect=lambda req: httpx.Response(200, json=json.loads(req.content))
        )
        await call_tool("add_tags", {"names": ["errands", "home"]})
        assert route.call_count == 2
        assert body(route, 1) == {"label": "home", "name": "home"}


class TestDeleteTags:
    @pytest.mark.anyio
    async def test_delete_uses_v1_scope_all(self, env_vars, mock_api: respx.MockRouter):
        route = mock_api.delete(f"{V1_BASE}/tag/delete", params={"scope": "0"}).mock(
            return_value=httpx.Response(200)
        )
        await call_tool("delete_tags", {"names": ["work", "a b"]})
        assert route.call_count == 2
        assert body(route, 1) == {"name": "a b"}


class TestRenameTag:
    @pytest.mark.anyio
    async def test_rename_uses_v1_scope_all(self, env_vars, mock_api: respx.MockRouter):
        route = mock_api.put(f"{V1_BASE}/tag/rename", params={"scope": "0"}).mock(
            return_value=httpx.Response(200, json={"name": "new_tag"})
        )
        await call_tool("rename_tag", {"old_name": "old_tag", "new_name": "new_tag"})
        assert body(route) == {"name": "old_tag", "newName": "new_tag"}


class TestEditTag:
    @pytest.mark.anyio
    async def test_edit_sends_only_given_fields(self, env_vars, mock_api: respx.MockRouter):
        route = mock_api.put(f"{V1_BASE}/tag").mock(
            return_value=httpx.Response(200, json={"name": "work"})
        )
        await call_tool("edit_tag", {"name": "work", "color": "#00FF00", "clear_parent": True})
        assert body(route) == {"name": "work", "color": "#00FF00", "parent": ""}


class TestMergeTags:
    @pytest.mark.anyio
    async def test_merge(self, client: TickTickClient, mock_api: respx.MockRouter):
        mock_api.put(f"{V2_BASE}/tag/merge").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        result = await client.v2_put("/tag/merge", {"name": "source", "newName": "target"})
        assert result["ok"] is True
