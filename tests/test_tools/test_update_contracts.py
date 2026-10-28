from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import httpx
import pytest
from fastmcp.exceptions import ToolError

from ticktick_mcp.client import V1_BASE, V2_BASE
from ticktick_mcp.tools import filters, projects


class Registry:
    """Capture actual tool functions without a transport or real account."""

    def __init__(self):
        self.tools = {}

    def tool(self, **kwargs):
        def register(fn):
            self.tools[fn.__name__] = fn
            return fn

        return register


def tool(module, name, client):
    registry = Registry()
    module.register(registry)
    ctx = SimpleNamespace(request_context=SimpleNamespace(lifespan_context={"client": client}))
    return registry.tools[name], ctx


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"rule": "new-rule"}, {"rule": "new-rule"}),
        ({"name": "Today + Tomorrow"}, {"name": "Today + Tomorrow"}),
        ({"sort_type": "priority"}, {"sortType": "priority"}),
    ],
)
async def test_filter_edit_preserves_other_fields(client, mock_api, changes, expected):
    original = {
        "id": "a" * 24,
        "name": "Today",
        "etag": "e1",
        "rule": "old-rule",
        "sortOrder": -42,
        "sortType": "dueDate",
        "viewMode": "list",
        "sortOption": {"groupBy": "project", "order": "asc"},
        "background": None,
        "futureField": {"keep": True},
    }
    state = deepcopy(original)
    mock_api.get(f"{V2_BASE}/batch/check/0").mock(
        side_effect=lambda request: httpx.Response(200, json={"filters": [state]})
    )

    def replace(request):
        import json

        payload = json.loads(request.content)["update"][0]
        # The server replaces fields rather than applying a JSON merge patch.
        state.clear()
        state.update(payload)
        return httpx.Response(200, json={"id2etag": {original["id"]: "e2"}})

    mock_api.post(f"{V2_BASE}/batch/filter").mock(side_effect=replace)
    edit, ctx = tool(filters, "edit_filter", client)
    await edit(ctx, filter_name="Today", **changes)
    assert state == original | expected


@pytest.mark.anyio
async def test_filter_with_null_name_can_be_repaired_by_id(client, mock_api):
    fid = "a" * 24
    original = {"id": fid, "name": None, "etag": "e1", "rule": "keep"}
    mock_api.get(f"{V2_BASE}/batch/check/0").mock(
        return_value=httpx.Response(200, json={"filters": [original]})
    )
    route = mock_api.post(f"{V2_BASE}/batch/filter").mock(
        return_value=httpx.Response(200, json={"id2etag": {fid: "e2"}})
    )
    edit, ctx = tool(filters, "edit_filter", client)
    await edit(ctx, filter_name=fid, name="Repaired")
    import json

    assert json.loads(route.calls.last.request.content)["update"][0] == original | {
        "name": "Repaired"
    }


@pytest.mark.anyio
async def test_unknown_filter_id_never_writes(client, mock_api):
    mock_api.get(f"{V2_BASE}/batch/check/0").mock(
        return_value=httpx.Response(200, json={"filters": []})
    )
    edit, ctx = tool(filters, "edit_filter", client)
    with pytest.raises(ValueError, match="filter"):
        await edit(ctx, filter_name="a" * 24, name="Unknown")


@pytest.mark.anyio
@pytest.mark.parametrize("stored_group", ["old-folder", None, "missing"])
async def test_remove_folder_checks_persisted_state(client, mock_api, stored_group):
    pid = "b" * 24
    mock_api.get(f"{V1_BASE}/project").mock(
        return_value=httpx.Response(200, json=[{"id": pid, "name": "Work"}])
    )
    mock_api.post(f"{V1_BASE}/project/{pid}").mock(
        return_value=httpx.Response(200, json={"id": pid, "name": "Work"})
    )
    stored = {"id": pid}
    if stored_group != "missing":
        stored["groupId"] = stored_group
    mock_api.get(f"{V1_BASE}/project/{pid}").mock(return_value=httpx.Response(200, json=stored))
    edit, ctx = tool(projects, "edit_project", client)
    if stored_group is None:
        result = await edit(ctx, project=pid, remove_folder=True)
        assert result["groupId"] is None
    else:
        with pytest.raises(ToolError, match="folder"):
            await edit(ctx, project=pid, remove_folder=True)
