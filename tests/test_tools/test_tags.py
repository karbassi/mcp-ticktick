from __future__ import annotations

import httpx
import pytest
import respx
from fastmcp import Client

from ticktick_mcp.client import V1_BASE, V2_BASE, TickTickClient


class TestListTags:
    @pytest.mark.anyio
    async def test_list_uses_v1(self, env_vars, mock_api: respx.MockRouter):
        from ticktick_mcp.server import mcp

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
        async with Client(mcp) as c:
            result = await c.call_tool("list_tags", {})
        assert v1.called
        assert not v2.called
        assert [t["name"] for t in result.structured_content["result"]] == ["work", "personal"]


class TestAddTags:
    @pytest.mark.anyio
    async def test_add(self, client: TickTickClient, mock_api: respx.MockRouter):
        mock_api.post(f"{V2_BASE}/batch/tag").mock(
            return_value=httpx.Response(200, json={"id2etag": {"tag1": "etag1"}})
        )
        result = await client.v2_post(
            "/batch/tag", {"add": [{"label": "errands", "name": "errands"}]}
        )
        assert "id2etag" in result


class TestDeleteTags:
    @pytest.mark.anyio
    async def test_delete(self, client: TickTickClient, mock_api: respx.MockRouter):
        mock_api.delete(f"{V2_BASE}/tag?name=work").mock(return_value=httpx.Response(200))
        resp = await client.v2_delete("/tag?name=work")
        assert resp.status_code == 200


class TestRenameTag:
    @pytest.mark.anyio
    async def test_rename(self, client: TickTickClient, mock_api: respx.MockRouter):
        mock_api.put(f"{V2_BASE}/tag/rename").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        result = await client.v2_put("/tag/rename", {"name": "old_tag", "newName": "new_tag"})
        assert result["ok"] is True


class TestEditTag:
    @pytest.mark.anyio
    async def test_edit(self, client: TickTickClient, mock_api: respx.MockRouter):
        mock_api.post(f"{V2_BASE}/batch/tag").mock(
            return_value=httpx.Response(200, json={"id2etag": {"work": "etag2"}})
        )
        result = await client.v2_post(
            "/batch/tag",
            {"update": [{"name": "work", "color": "#00FF00", "sortOrder": 1}]},
        )
        assert "id2etag" in result


class TestMergeTags:
    @pytest.mark.anyio
    async def test_merge(self, client: TickTickClient, mock_api: respx.MockRouter):
        mock_api.put(f"{V2_BASE}/tag/merge").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        result = await client.v2_put("/tag/merge", {"name": "source", "newName": "target"})
        assert result["ok"] is True
