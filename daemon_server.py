#!/usr/bin/env python3
"""Auto-generated daemon server script."""

import asyncio
import os
import sys
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))


async def main():
    """Main daemon server function."""
    try:
        # Import and start MCP server
        from swagger_mcp_server.server.mcp_server_simple import create_simple_server

        # Get configuration from environment
        host = os.getenv("SWAGGER_MCP_HOST", "0.0.0.0")
        port = int(os.getenv("SWAGGER_MCP_PORT", "9000"))

        # Create and start server
        server = create_simple_server()
        print(f"🚀 MCP Server starting on {host}:{port}")
        print(f"📊 API: MCP Server")
        print("🤖 AI agents can now connect and query API documentation")

        # Start server (this will block)
        await server.start(host=host, port=port)

    except KeyboardInterrupt:
        print("\n🛑 Server shutdown requested")
    except Exception as e:
        print(f"❌ Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
