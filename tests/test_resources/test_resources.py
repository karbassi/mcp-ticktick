from __future__ import annotations

import httpx
import pytest
import respx

from ticktick_mcp.client import V1_BASE, V2_BASE, TickTickClient


class TestProfileResource:
    @pytest.mark.anyio
    async def test_profile_merge(self, client: TickTickClient, mock_api: respx.MockRouter):
        mock_api.get(f"{V2_BASE}/user/profile").mock(
            return_value=httpx.Response(200, json={"username": "ali", "email": "ali@example.com"})
        )
        mock_api.get(f"{V2_BASE}/user/status").mock(
            return_value=httpx.Response(200, json={"pro": True, "plan": "premium"})
        )
        profile = await client.v2_get("/user/profile")
        status = await client.v2_get("/user/status")
        merged = {**profile, "status": status}
        assert merged["username"] == "ali"
        assert merged["status"]["pro"] is True


class TestSettingsResource:
    @pytest.mark.anyio
    async def test_settings(self, client: TickTickClient, mock_api: respx.MockRouter):
        mock_api.get(f"{V2_BASE}/user/preferences/settings?includeWeb=true").mock(
            return_value=httpx.Response(
                200, json={"theme": "dark", "startOfWeek": 1, "timeZone": "America/Chicago"}
            )
        )
        result = await client.v2_get("/user/preferences/settings?includeWeb=true")
        assert result["theme"] == "dark"
        assert result["timeZone"] == "America/Chicago"


class TestProjectsResource:
    @pytest.mark.anyio
    async def test_projects(self, client: TickTickClient, mock_api: respx.MockRouter):
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


class TestTagsResource:
    @pytest.mark.anyio
    async def test_tags(self, client: TickTickClient, mock_api: respx.MockRouter):
        mock_api.get(f"{V1_BASE}/tag").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"name": "work", "color": "#FF0000"},
                    {"name": "personal", "parent": "life"},
                ],
            )
        )
        result = await client.v1_get("/tag")
        assert len(result) == 2
        assert result[1]["parent"] == "life"
