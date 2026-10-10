# Changelog

## Unreleased

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
