"""Simple MCP server implementation for testing purposes.

This is a minimal implementation to verify the MCP SDK integration works correctly.
"""

import asyncio
from typing import Any, Dict

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from swagger_mcp_server.config.logging import get_logger
from swagger_mcp_server.config.settings import Settings

logger = get_logger(__name__)


def create_simple_server() -> Server:
    """Create a simple MCP server for testing."""
    server = Server("swagger-mcp-server")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        """List available tools."""
        return [
            types.Tool(
                name="test",
                description="Test tool for MCP server validation",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "Test message",
                        }
                    },
                    "required": ["message"],
                },
            )
        ]

    @server.call_tool()
    async def call_tool(
        name: str, arguments: Dict[str, Any]
    ) -> list[types.TextContent]:
        """Handle tool calls."""
        if name == "test":
            message = arguments.get("message", "No message provided")
            return [
                types.TextContent(
                    type="text", text=f"Test successful! Message: {message}"
                )
            ]
        else:
            raise ValueError(f"Unknown tool: {name}")

    return server


async def main():
    """Run the simple MCP server."""
    server = create_simple_server()

    # Run with stdio transport
    options = types.ServerCapabilities(tools=types.ToolsCapability())

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            types.InitializeResult(
                protocolVersion="1.0.0",
                capabilities=options,
                serverInfo=types.Implementation(
                    name="swagger-mcp-server", version="0.1.0"
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
