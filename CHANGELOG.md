# Changelog

## Unreleased

### Official API migration (#15)

- `list_tags` and the `ticktick://tags` resource now use the official `GET /open/v1/tag` instead of v2 `GET /tags`, so they no longer need the v2 session token. Same tags, colors, and parents (verified live: 38 = 38). v1 omits `etag`, `rawName`, `sortOption`, and `timeline`, which nothing reads. (#16)
- `add_tags` uses `POST /open/v1/tag`, one call per name. It now returns the created tags instead of v2's `id2etag` map. (#17)
- `edit_tag` uses `PUT /open/v1/tag`. Only the fields you pass change; `clear_parent` still works. (#18)
- `rename_tag` uses `PUT /open/v1/tag/rename?scope=0`, renaming the tag on every task, as v2 did. (#19)
- `delete_tags` uses `DELETE /open/v1/tag/delete?scope=0`. Like v2, this removes the tag from every task; the old docstring wrongly said tasks were unaffected. (#20)
- `merge_tags` stays on v2: there is no official endpoint.
- New `TickTickClient.v1_put`; `v1_delete` accepts a JSON body.
- Add optional shared HTTP transport: `TICKTICK_MCP_TRANSPORT=http` (with `TICKTICK_MCP_HOST`/`TICKTICK_MCP_PORT`, default `127.0.0.1:8502`) runs one server for many clients. Loopback-only, with Host/Origin (DNS-rebinding) protection always on. stdio stays the default.
- Require FastMCP 4.1 (MCP SDK 2.3)

## 0.1.2 (2026-02-22)

- Add project URLs, author to PyPI sidebar metadata

## 0.1.1 (2026-02-22)

- Fix PyPI project description (add readme to package metadata)

## 0.1.0 (2026-02-22)

Initial release.

- 45 tools: tasks, projects, tags, folders, habits, filters, focus, calendar
- 4 resources: profile, settings, projects, tags
- v1 API (OAuth) for tasks and projects
- v2 API (session cookie) for tags, folders, filters, habits, focus, calendar
- Fuzzy name resolution with Levenshtein distance
- Date/time parsing with timezone support
