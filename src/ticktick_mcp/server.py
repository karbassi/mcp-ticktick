from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from ticktick_mcp.client import TickTickClient


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[dict]:
    client = TickTickClient(
        access_token=os.environ["TICKTICK_ACCESS_TOKEN"],
        client_id=os.environ.get("TICKTICK_CLIENT_ID"),
        client_secret=os.environ.get("TICKTICK_CLIENT_SECRET"),
        session_token=os.environ.get("TICKTICK_V2_SESSION_TOKEN"),
        refresh_token=os.environ.get("TICKTICK_REFRESH_TOKEN"),
    )
    async with client:
        yield {"client": client}


mcp = FastMCP("TickTick", lifespan=lifespan)

# Register tool and resource modules
from ticktick_mcp.resources import register_resources  # noqa: E402
from ticktick_mcp.tools import register_tools  # noqa: E402

register_tools(mcp)
register_resources(mcp)


# The HTTP endpoint has no auth: any caller acts with the TickTick tokens, so it
# may only listen on loopback. Put an authenticating proxy in front for remote use.
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def main() -> None:
    # stdio by default; set TICKTICK_MCP_TRANSPORT=http to run one shared server.
    transport = os.environ.get("TICKTICK_MCP_TRANSPORT", "stdio")
    if transport == "stdio":
        mcp.run(transport="stdio")
        return
    if transport != "http":
        msg = f"TICKTICK_MCP_TRANSPORT must be 'stdio' or 'http', got {transport!r}"
        raise SystemExit(msg)
    host = os.environ.get("TICKTICK_MCP_HOST", "127.0.0.1")
    if host not in LOOPBACK_HOSTS:
        msg = f"TICKTICK_MCP_HOST must be a loopback address, got {host!r}"
        raise SystemExit(msg)
    mcp.run(
        transport="http",
        host=host,
        port=int(os.environ.get("TICKTICK_MCP_PORT", "8502")),
        show_banner=False,
        # FastMCP defaults this off, leaving the server open to DNS rebinding.
        # Extra trusted hosts/origins come from FASTMCP_HTTP_ALLOWED_HOSTS/_ORIGINS.
        host_origin_protection=True,
    )


if __name__ == "__main__":
    main()
