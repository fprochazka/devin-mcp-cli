"""MCP Client for connecting to the Devin MCP Server."""

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import CallToolResult, TextContent, Tool

from .cache import load_from_cache, save_to_cache
from .config import DEVIN_MCP_URL, McpServerConfig, OrgConfig


class DevinMcpClient:
    """Client for interacting with the Devin MCP Server."""

    def __init__(self, org: OrgConfig, server: McpServerConfig | None = None):
        self.org = org
        self.server = server or McpServerConfig()
        self._session: ClientSession | None = None

    def _get_headers(self) -> dict[str, str]:
        """Build authentication headers for the MCP server.

        The Bearer key is always sent. ``X-Org-Id`` is sent only when the account
        carries an ``org_id`` (Personal Access Tokens and enterprise-scoped keys
        need it, org-scoped service keys do not). An empty value is never sent.
        """
        headers = {"Authorization": f"Bearer {self.org.api_key}"}
        if self.org.org_id:
            headers["X-Org-Id"] = self.org.org_id
        return headers

    @asynccontextmanager
    async def connect(self):
        """Connect to the MCP server and yield a session."""
        headers = self._get_headers()

        async with (
            streamablehttp_client(
                url=DEVIN_MCP_URL,
                headers=headers,
                timeout=self.server.timeout,
                sse_read_timeout=self.server.sse_read_timeout,
            ) as (read, write, _),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            self._session = session
            try:
                yield session
            finally:
                self._session = None

    async def list_tools(self) -> list[Tool]:
        """List all available tools from the MCP server."""
        if self._session is None:
            raise RuntimeError("Not connected to MCP server. Use 'async with client.connect()' first.")

        result = await self._session.list_tools()
        return list(result.tools)

    async def call_tool(self, tool_name: str, arguments: dict[str, Any] | None = None) -> CallToolResult:
        """Call a tool on the MCP server."""
        if self._session is None:
            raise RuntimeError("Not connected to MCP server. Use 'async with client.connect()' first.")

        return await self._session.call_tool(tool_name, arguments=arguments or {})


def format_tool_result(result: CallToolResult) -> str:
    """Format a tool result for display."""
    output_parts = []

    for content in result.content:
        if isinstance(content, TextContent):
            # Try to parse as JSON for pretty printing
            try:
                data = json.loads(content.text)
                output_parts.append(json.dumps(data, indent=2))
            except json.JSONDecodeError:
                output_parts.append(content.text)
        else:
            output_parts.append(str(content))

    return "\n".join(output_parts)


class McpError(Exception):
    """Base exception for MCP client errors."""

    pass


class McpConnectionError(McpError):
    """Error connecting to the MCP server."""

    pass


class McpAuthenticationError(McpError):
    """Authentication failed with the MCP server."""

    pass


def get_tools(org: OrgConfig, server: McpServerConfig | None = None) -> list[dict[str, Any]]:
    """Get MCP tools, using cache if available.

    Args:
        org: The resolved account credentials.
        server: MCP server timeouts.

    Returns:
        List of tool dictionaries with name, description, and inputSchema.

    Raises:
        McpError: If fetching tools fails and no cache is available.
    """
    if not org.api_key:
        return []

    # Try cache first
    cached = load_from_cache()
    if cached is not None:
        return cached

    # Fetch from MCP server
    async def _fetch():
        client = DevinMcpClient(org, server)
        async with client.connect():
            return await client.list_tools()

    tools = asyncio.run(_fetch())
    tools_data = [
        {
            "name": t.name,
            "description": t.description,
            "inputSchema": t.inputSchema,
        }
        for t in tools
    ]
    save_to_cache(tools_data)
    return tools_data
