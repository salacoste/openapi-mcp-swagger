"""Daemon management for background MCP server execution."""

import os
import sys
import signal
import subprocess
import asyncio
from typing import Dict, Any, Optional
from pathlib import Path
import structlog

logger = structlog.get_logger(__name__)


class DaemonManager:
    """Manages daemon/background execution of MCP servers."""

    def __init__(self):
        self.daemon_processes: Dict[str, subprocess.Popen] = {}

    async def start_daemon_server(self, server_config: Dict[str, Any]) -> Dict[str, Any]:
        """Start MCP server in daemon/background mode.

        Args:
            server_config: Server configuration

        Returns:
            Dict[str, Any]: Process information
        """
        # Prepare daemon environment
        daemon_env = self._prepare_daemon_environment(server_config)

        # Create server script path
        server_script = self._create_daemon_script(server_config)

        try:
            # Start daemon process
            process = await self._start_daemon_process(server_script, daemon_env)

            # Store process reference
            server_id = server_config.get("server_id", f"daemon-{process.pid}")
            self.daemon_processes[server_id] = process

            logger.info("Daemon server started",
                       server_id=server_id,
                       pid=process.pid,
                       port=server_config.get("port"))

            return {
                "server_id": server_id,
                "pid": process.pid,
                "host": server_config.get("host", "localhost"),
                "port": server_config.get("port", 8080),
                "daemon": True,
                "startup_time": 0  # Will be updated when server is ready
            }

        except Exception as e:
            logger.error("Failed to start daemon server", error=str(e))
            raise

    async def stop_daemon_server(self, server_id: str, timeout: int = 30) -> bool:
        """Stop daemon server gracefully.

        Args:
            server_id: Server identifier
            timeout: Shutdown timeout in seconds

        Returns:
            bool: True if stopped successfully
        """
        if server_id not in self.daemon_processes:
            logger.warning("Daemon server not found", server_id=server_id)
            return False

        process = self.daemon_processes[server_id]

        try:
            # Send SIGTERM for graceful shutdown
            process.terminate()

            # Wait for graceful shutdown
            try:
                process.wait(timeout=timeout)
                logger.info("Daemon server stopped gracefully", server_id=server_id)
            except subprocess.TimeoutExpired:
                # Force kill if timeout exceeded
                logger.warning("Forcing daemon server shutdown", server_id=server_id)
                process.kill()
                process.wait()

            # Remove from tracking
            del self.daemon_processes[server_id]
            return True

        except Exception as e:
            logger.error("Failed to stop daemon server", server_id=server_id, error=str(e))
            return False

    async def get_daemon_status(self, server_id: str) -> Optional[Dict[str, Any]]:
        """Get daemon server status.

        Args:
            server_id: Server identifier

        Returns:
            Optional[Dict[str, Any]]: Status information or None if not found
        """
        if server_id not in self.daemon_processes:
            return None

        process = self.daemon_processes[server_id]

        try:
            # Check if process is still running
            return_code = process.poll()

            if return_code is None:
                # Process is still running
                return {
                    "status": "running",
                    "pid": process.pid,
                    "return_code": None
                }
            else:
                # Process has exited
                return {
                    "status": "stopped",
                    "pid": process.pid,
                    "return_code": return_code
                }

        except Exception as e:
            logger.error("Failed to get daemon status", server_id=server_id, error=str(e))
            return {
                "status": "error",
                "error": str(e)
            }

    def _prepare_daemon_environment(self, server_config: Dict[str, Any]) -> Dict[str, str]:
        """Prepare environment variables for daemon process.

        Args:
            server_config: Server configuration

        Returns:
            Dict[str, str]: Environment variables
        """
        env = os.environ.copy()

        # Set daemon-specific environment variables
        env.update({
            "SWAGGER_MCP_DAEMON": "true",
            "SWAGGER_MCP_HOST": str(server_config.get("host", "localhost")),
            "SWAGGER_MCP_PORT": str(server_config.get("port", 8080)),
            "PYTHONUNBUFFERED": "1"  # Ensure output is not buffered
        })

        # Add config file if specified
        if server_config.get("config_file"):
            env["SWAGGER_MCP_CONFIG"] = str(server_config["config_file"])

        # Add working directory
        if server_config.get("working_directory"):
            env["SWAGGER_MCP_WORKDIR"] = str(server_config["working_directory"])

        return env

    def _create_daemon_script(self, server_config: Dict[str, Any]) -> Path:
        """Create daemon startup script.

        Args:
            server_config: Server configuration

        Returns:
            Path: Path to daemon script
        """
        # Use working directory or current directory
        work_dir = Path(server_config.get("working_directory", "."))

        # Look for server.py in working directory
        server_script = work_dir / "server.py"

        if not server_script.exists():
            # Create a simple server script if it doesn't exist
            server_script = self._generate_simple_server_script(work_dir, server_config)

        return server_script

    def _generate_simple_server_script(self, work_dir: Path, server_config: Dict[str, Any]) -> Path:
        """Generate a simple server script for daemon execution.

        Args:
            work_dir: Working directory
            server_config: Server configuration

        Returns:
            Path: Path to generated script
        """
        script_path = work_dir / "daemon_server.py"

        script_content = f'''#!/usr/bin/env python3
"""Auto-generated daemon server script."""

import asyncio
import os
import sys
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

async def main():
    \"\"\"Main daemon server function.\"\"\"
    try:
        # Import and start MCP server
        from swagger_mcp_server.server.mcp_server_simple import create_simple_server

        # Get configuration from environment
        host = os.getenv("SWAGGER_MCP_HOST", "{server_config.get('host', 'localhost')}")
        port = int(os.getenv("SWAGGER_MCP_PORT", "{server_config.get('port', 8080)}"))

        # Create and start server
        server = create_simple_server()
        print(f"🚀 MCP Server starting on {{host}}:{{port}}")
        print(f"📊 API: {server_config.get('api_title', 'Generated API')}")
        print("🤖 AI agents can now connect and query API documentation")

        # Start server (this will block)
        await server.start(host=host, port=port)

    except KeyboardInterrupt:
        print("\\n🛑 Server shutdown requested")
    except Exception as e:
        print(f"❌ Server error: {{e}}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
'''

        with open(script_path, 'w') as f:
            f.write(script_content)

        # Make executable
        script_path.chmod(0o755)

        return script_path

    async def _start_daemon_process(self, server_script: Path, env: Dict[str, str]) -> subprocess.Popen:
        """Start daemon process.

        Args:
            server_script: Path to server script
            env: Environment variables

        Returns:
            subprocess.Popen: Process handle
        """
        # Prepare command
        cmd = [sys.executable, str(server_script)]

        # Create log directory
        log_dir = Path.home() / ".swagger-mcp-server" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        # Create log files
        stdout_log = log_dir / f"daemon-{os.getpid()}.out"
        stderr_log = log_dir / f"daemon-{os.getpid()}.err"

        try:
            # Start process with redirected output
            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=open(stdout_log, 'w'),
                stderr=open(stderr_log, 'w'),
                stdin=subprocess.DEVNULL,
                cwd=server_script.parent,
                start_new_session=True  # Detach from parent session
            )

            # Wait a moment to check if process started successfully
            await asyncio.sleep(1)

            return_code = process.poll()
            if return_code is not None:
                # Process exited immediately - read error output
                try:
                    with open(stderr_log, 'r') as f:
                        error_output = f.read()
                    raise Exception(f"Daemon process exited with code {return_code}: {error_output}")
                except:
                    raise Exception(f"Daemon process exited with code {return_code}")

            logger.info("Daemon process started successfully",
                       pid=process.pid,
                       stdout_log=str(stdout_log),
                       stderr_log=str(stderr_log))

            return process

        except Exception as e:
            logger.error("Failed to start daemon process", error=str(e))
            raise

    async def cleanup_all_daemons(self):
        """Clean up all tracked daemon processes."""
        for server_id in list(self.daemon_processes.keys()):
            await self.stop_daemon_server(server_id)

    def __del__(self):
        """Cleanup on destruction."""
        # Note: This is not async, so we can't use await
        # In production, ensure cleanup_all_daemons() is called explicitly
        for process in self.daemon_processes.values():
            try:
                if process.poll() is None:
                    process.terminate()
            except:
                pass