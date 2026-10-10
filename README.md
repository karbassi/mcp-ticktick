<div align="center">

# mcp-ticktick

**Your entire TickTick — available to any AI.**

[![PyPI](https://img.shields.io/pypi/v/mcp-ticktick?style=flat-square)](https://pypi.org/project/mcp-ticktick/)
[![Python](https://img.shields.io/pypi/pyversions/mcp-ticktick?style=flat-square)](https://pypi.org/project/mcp-ticktick/)
[![License](https://img.shields.io/github/license/karbassi/mcp-ticktick?style=flat-square)](LICENSE)
[![CI](https://img.shields.io/github/actions/workflow/status/karbassi/mcp-ticktick/ci.yml?style=flat-square&label=tests)](https://github.com/karbassi/mcp-ticktick/actions)

A [Model Context Protocol](https://modelcontextprotocol.io/) server that gives LLMs full access to [TickTick](https://ticktick.com).<br>
Tasks, projects, habits, focus timers, tags, filters, calendar — all of it.

**45 tools** · **4 resources** · **Every TickTick feature**

</div>

---

## Quick Start

```bash
pip install mcp-ticktick
```

Then add it to your AI client of choice:

<details>
<summary><strong>Claude Desktop</strong></summary>

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ticktick": {
      "command": "mcp-ticktick",
      "env": {
        "TICKTICK_ACCESS_TOKEN": "your-access-token",
        "TICKTICK_V2_SESSION_TOKEN": "your-session-cookie"
      }
    }
  }
}
```

</details>

<details>
<summary><strong>Claude Code</strong></summary>

```bash
claude mcp add mcp-ticktick -- mcp-ticktick
```

Then set the environment variables in your shell.

</details>

<details>
<summary><strong>Cursor</strong></summary>

Add to `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "ticktick": {
      "command": "mcp-ticktick",
      "env": {
        "TICKTICK_ACCESS_TOKEN": "your-access-token",
        "TICKTICK_V2_SESSION_TOKEN": "your-session-cookie"
      }
    }
  }
}
```

</details>

<details>
<summary><strong>Windsurf</strong></summary>

Add to `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "ticktick": {
      "command": "mcp-ticktick",
      "env": {
        "TICKTICK_ACCESS_TOKEN": "your-access-token",
        "TICKTICK_V2_SESSION_TOKEN": "your-session-cookie"
      }
    }
  }
}
```

</details>

<details>
<summary><strong>VS Code / GitHub Copilot</strong></summary>

Add to your VS Code `settings.json`:

```json
{
  "mcp": {
    "servers": {
      "ticktick": {
        "command": "mcp-ticktick",
        "env": {
          "TICKTICK_ACCESS_TOKEN": "your-access-token",
          "TICKTICK_V2_SESSION_TOKEN": "your-session-cookie"
        }
      }
    }
  }
}
```

</details>

## What Can It Do?

> *"Add a task to my Shopping list due tomorrow"*  
> *"Check in my meditation habit for today"*  
> *"Show me what I focused on this week"*  
> *"Move all tasks tagged #backlog to the Archive project"*

| Domain | Tools | Highlights |
|---|---|---|
| **Tasks** | 10 | Create, edit, complete, delete, move, subtasks, trash |
| **Projects** | 5 | CRUD with fuzzy name matching |
| **Tags** | 6 | Create, rename, merge, hierarchies |
| **Folders** | 4 | Group projects into folders |
| **Habits** | 8 | Track, check in, streaks, sections |
| **Filters** | 4 | Saved custom filters |
| **Focus** | 5 | Pomodoro records, stats, session history |
| **Calendar** | 3 | Connected calendars and events |

Plus 4 read-only **resources**: `ticktick://profile` · `ticktick://settings` · `ticktick://projects` · `ticktick://tags`

<details>
<summary><strong>Full tool reference</strong></summary>

### Tasks

| Tool | Description |
|---|---|
| `list_tasks` | List tasks from a project or all projects |
| `get_task` | Get a single task by ID |
| `add_task` | Create a task with due date, priority, tags, checklist |
| `edit_task` | Update task fields |
| `complete_task` | Mark a task complete |
| `delete_task` | Delete a task |
| `move_task` | Move a task between projects |
| `set_subtask` | Make a task a subtask of another |
| `unparent_task` | Remove a task from its parent |
| `list_trash` | List deleted tasks |

### Projects

| Tool | Description |
|---|---|
| `list_projects` | List all projects |
| `get_project` | Get a project by name or ID (fuzzy match) |
| `add_project` | Create a new project |
| `edit_project` | Update project properties |
| `delete_project` | Delete a project and its tasks |

### Tags

| Tool | Description |
|---|---|
| `list_tags` | List all tags |
| `add_tags` | Create one or more tags |
| `delete_tags` | Delete tags |
| `rename_tag` | Rename a tag (updates all tasks) |
| `edit_tag` | Update tag color, parent, sort |
| `merge_tags` | Merge one tag into another |

### Folders

| Tool | Description |
|---|---|
| `list_folders` | List all project folders |
| `add_folder` | Create a folder |
| `delete_folders` | Delete folders |
| `rename_folder` | Rename a folder |

### Habits

| Tool | Description |
|---|---|
| `list_habits` | List all habits |
| `add_habit` | Create a boolean or numeric habit |
| `edit_habit` | Update habit properties |
| `delete_habits` | Delete habits |
| `checkin_habit` | Record a habit check-in |
| `habit_log` | Query check-in history |
| `archive_habits` | Archive habits (hide, keep data) |
| `manage_habit_sections` | List, add, delete, rename sections |

### Filters

| Tool | Description |
|---|---|
| `list_filters` | List saved filters |
| `add_filter` | Create a filter |
| `edit_filter` | Update a filter |
| `delete_filters` | Delete filters |

### Focus

| Tool | Description |
|---|---|
| `focus_status` | Current timer status |
| `focus_stats` | Daily and total focus statistics |
| `focus_log` | Focus sessions for a date range |
| `focus_timeline` | Full session history |
| `focus_save` | Save a completed pomodoro record |

### Calendar

| Tool | Description |
|---|---|
| `list_calendars` | List connected calendar accounts |
| `list_events` | Query events for a date range |
| `sync_account` | Full account sync |

</details>

## Shared HTTP server

By default every client starts its own stdio process. To run one long-lived server that many clients share:

```bash
TICKTICK_MCP_TRANSPORT=http TICKTICK_MCP_PORT=8502 mcp-ticktick
```

```json
{
  "mcpServers": {
    "ticktick": { "type": "http", "url": "http://127.0.0.1:8502/mcp" }
  }
}
```

The endpoint has **no authentication**: anything that can connect to it can use every tool with your TickTick credentials, including deleting projects. So:

- The server only binds to loopback (`TICKTICK_MCP_HOST` must be `127.0.0.1`, `localhost`, or `::1`). Any local process can still connect, so only use HTTP mode on a machine where every local user and process is trusted with your TickTick account.
- It always turns on FastMCP's Host/Origin protection, which FastMCP leaves off by default. That check **only** stops DNS-rebinding attacks from web pages. It does not authenticate anyone.
- To reach it from another machine, put it behind a reverse proxy that **controls who can connect**: a bearer token, mTLS, an IP allowlist on a private network, or similar. Then add the proxy's hostname to `FASTMCP_HTTP_ALLOWED_HOSTS`, e.g. `FASTMCP_HTTP_ALLOWED_HOSTS='["mcp.example.com"]'`. If a browser-based client will call it, also add that client's origin to `FASTMCP_HTTP_ALLOWED_ORIGINS`, e.g. `'["https://mcp.example.com"]'`. Never expose the port or the proxy publicly without access control.

## Authentication

You need a TickTick [OAuth app](https://developer.ticktick.com/manage) (free to create).

| Variable | Required | Description |
|---|---|---|
| `TICKTICK_ACCESS_TOKEN` | **Yes** | OAuth access token |
| `TICKTICK_CLIENT_ID` | No | OAuth client ID (for token refresh) |
| `TICKTICK_CLIENT_SECRET` | No | OAuth client secret (for token refresh) |
| `TICKTICK_REFRESH_TOKEN` | No | OAuth refresh token |
| `TICKTICK_V2_SESSION_TOKEN` | No | Browser `t` cookie for v2 features |

> **v1 vs v2:** The access token covers tasks and projects. For tags, folders, filters, habits, focus, and calendar you also need a v2 session token — grab the `t` cookie from your browser while logged into ticktick.com.

## Development

```bash
git clone https://github.com/karbassi/mcp-ticktick.git
cd ticktick-mcp
uv sync --all-extras
uv run ruff check src/ tests/
uv run pytest
```

## License

[MIT](LICENSE)
