"""Main MCP server manager coordinating all server lifecycle operations."""

import asyncio
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from .daemon_manager import DaemonManager
from .process_monitor import HealthStatus, ProcessMonitor, ServerMetrics
from .server_registry import ServerInstance, ServerRegistry

logger = structlog.get_logger(__name__)


class ServerError(Exception):
    """Server management error with user-friendly messages."""

    def __init__(
        self,
        message: str,
        suggestion: Optional[str] = None,
        details: Optional[Dict] = None,
    ):
        self.message = message
        self.suggestion = suggestion
        self.details = details or {}
        super().__init__(message)


class MCPServerManager:
    """Main server manager coordinating all MCP server operations."""

    def __init__(self, registry_dir: Optional[Path] = None):
        """Initialize server manager.

        Args:
            registry_dir: Directory for server registry (default: ~/.swagger-mcp-server)
        """
        self.registry = ServerRegistry(registry_dir)
        self.daemon_manager = DaemonManager()
        self.process_monitor = ProcessMonitor()

        # Track active interactive servers
        self.interactive_servers: Dict[str, subprocess.Popen] = {}

    async def start_server(
        self, server_config: Dict[str, Any], daemon: bool = False
    ) -> Dict[str, Any]:
        """Start MCP server with specified configuration.

        Args:
            server_config: Complete server configuration
            daemon: Whether to run in daemon mode

        Returns:
            Dict[str, Any]: Server startup result with process information
        """
        try:
            # Validate configuration
            await self._validate_server_config(server_config)

            # Check port availability
            port = server_config.get("port", 8080)
            if not await self.registry.is_port_available(port):
                raise ServerError(
                    f"Port {port} is already in use",
                    f"Choose a different port with --port option or stop the conflicting server",
                )

            # Clean up any dead servers
            await self.registry.cleanup_dead_servers()

            if daemon:
                return await self._start_daemon_server(server_config)
            else:
                return await self._start_interactive_server(server_config)

        except Exception as e:
            logger.error("Failed to start server", error=str(e), config=server_config)
            if isinstance(e, ServerError):
                raise
            else:
                raise ServerError(f"Failed to start server: {str(e)}")

    async def stop_server(
        self, server_id: str, force: bool = False, timeout: int = 30
    ) -> Dict[str, Any]:
        """Stop running MCP server.

        Args:
            server_id: Server identifier
            force: Force immediate shutdown
            timeout: Graceful shutdown timeout

        Returns:
            Dict[str, Any]: Shutdown result
        """
        try:
            # Get server instance
            server = await self.registry.get_server(server_id)
            if not server:
                raise ServerError(f"Server '{server_id}' not found")

            logger.info("Stopping server", server_id=server_id, force=force)

            # Update status to stopping
            await self.registry.update_server_status(server_id, "stopping")

            start_time = time.time()

            # Stop based on server type
            if server_id in self.interactive_servers:
                success = await self._stop_interactive_server(server_id, force, timeout)
            else:
                success = await self._stop_daemon_server(server_id, force, timeout)

            if success:
                # Remove from registry
                await self.registry.unregister_server(server_id)

                result = {
                    "status": "stopped",
                    "server_id": server_id,
                    "shutdown_time": time.time() - start_time,
                    "method": "forced" if force else "graceful",
                }

                logger.info("Server stopped successfully", **result)
                return result
            else:
                raise ServerError(f"Failed to stop server '{server_id}'")

        except Exception as e:
            if isinstance(e, ServerError):
                raise
            else:
                raise ServerError(f"Failed to stop server: {str(e)}")

    async def get_server_status(self, server_id: str) -> Dict[str, Any]:
        """Get detailed status for specific server.

        Args:
            server_id: Server identifier

        Returns:
            Dict[str, Any]: Complete server status
        """
        try:
            # Get server instance
            server = await self.registry.get_server(server_id)
            if not server:
                raise ServerError(f"Server '{server_id}' not found")

            # Get process metrics
            async with self.process_monitor:
                process_metrics = await self.process_monitor.get_process_metrics(
                    server.pid
                )
                if not process_metrics:
                    await self.registry.update_server_status(server_id, "stopped")
                    return {
                        "server": server.to_dict(),
                        "status": "stopped",
                        "message": "Process not found",
                    }

                # Get health status
                health_status = await self.process_monitor.check_server_health(
                    server.host, server.port, server_id
                )

                # Get server metrics
                server_metrics = await self.process_monitor.get_server_metrics(
                    server.pid, server.host, server.port
                )

            # Update server status based on health
            if health_status.is_healthy:
                await self.registry.update_server_status(server_id, "running")
            else:
                await self.registry.update_server_status(server_id, "unhealthy")

            return {
                "server": server.to_dict(),
                "health": health_status.to_dict(),
                "metrics": {
                    "process": {
                        "cpu_percent": process_metrics.cpu_percent,
                        "memory_mb": process_metrics.memory_mb,
                        "memory_percent": process_metrics.memory_percent,
                        "threads": process_metrics.threads,
                        "connections": process_metrics.connections,
                        "uptime_seconds": process_metrics.uptime_seconds,
                        "status": process_metrics.status,
                    },
                    "server": {
                        "requests_total": server_metrics.requests_total
                        if server_metrics
                        else 0,
                        "requests_per_minute": server_metrics.requests_per_minute
                        if server_metrics
                        else 0,
                        "response_time_avg_ms": server_metrics.response_time_avg_ms
                        if server_metrics
                        else 0,
                        "response_time_p95_ms": server_metrics.response_time_p95_ms
                        if server_metrics
                        else 0,
                        "active_connections": server_metrics.active_connections
                        if server_metrics
                        else 0,
                        "error_rate": server_metrics.error_rate
                        if server_metrics
                        else 0,
                    },
                },
                "uptime": server.uptime,
                "url": server.url,
            }

        except Exception as e:
            if isinstance(e, ServerError):
                raise
            else:
                raise ServerError(f"Failed to get server status: {str(e)}")

    async def get_all_servers_status(self) -> List[Dict[str, Any]]:
        """Get status for all registered servers.

        Returns:
            List[Dict[str, Any]]: Status information for all servers
        """
        try:
            # Clean up dead servers first
            await self.registry.cleanup_dead_servers()

            # Get all servers
            servers = await self.registry.get_all_servers()

            status_list = []
            for server in servers:
                try:
                    status = await self.get_server_status(server.id)
                    status_list.append(status)
                except Exception as e:
                    # Include error information for failed status checks
                    status_list.append(
                        {
                            "server": server.to_dict(),
                            "status": "error",
                            "error": str(e),
                        }
                    )

            return status_list

        except Exception as e:
            raise ServerError(f"Failed to get all servers status: {str(e)}")

    async def restart_server(self, server_id: str, timeout: int = 30) -> Dict[str, Any]:
        """Restart a running server.

        Args:
            server_id: Server identifier
            timeout: Shutdown timeout

        Returns:
            Dict[str, Any]: Restart result
        """
        try:
            # Get current server config
            server = await self.registry.get_server(server_id)
            if not server:
                raise ServerError(f"Server '{server_id}' not found")

            # Store configuration
            server_config = {
                "name": server.name,
                "host": server.host,
                "port": server.port,
                "config_file": server.config_file,
                "working_directory": server.working_directory,
                "api_title": server.api_title,
                "swagger_file": server.swagger_file,
            }

            # Determine if it was a daemon
            daemon_mode = server_id in self.daemon_manager.daemon_processes

            # Stop the server
            stop_result = await self.stop_server(server_id, timeout=timeout)

            # Wait a moment for cleanup
            await asyncio.sleep(1)

            # Start the server again
            start_result = await self.start_server(server_config, daemon=daemon_mode)

            return {
                "status": "restarted",
                "old_server_id": server_id,
                "new_server_id": start_result["server_id"],
                "stop_time": stop_result.get("shutdown_time", 0),
                "start_time": start_result.get("startup_time", 0),
            }

        except Exception as e:
            if isinstance(e, ServerError):
                raise
            else:
                raise ServerError(f"Failed to restart server: {str(e)}")

    async def _validate_server_config(self, config: Dict[str, Any]):
        """Validate server configuration."""
        required_fields = ["name", "host", "port"]

        for field in required_fields:
            if field not in config:
                raise ServerError(f"Missing required configuration: {field}")

        # Validate port range
        port = config["port"]
        if not isinstance(port, int) or port < 1 or port > 65535:
            raise ServerError(f"Invalid port number: {port}")

        # Validate working directory if provided
        if "working_directory" in config:
            work_dir = Path(config["working_directory"])
            if not work_dir.exists():
                raise ServerError(
                    f"Working directory does not exist: {work_dir}",
                    "Create the directory or specify a valid path",
                )

    async def _start_daemon_server(
        self, server_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Start server in daemon mode."""
        # Start daemon process
        process_info = await self.daemon_manager.start_daemon_server(server_config)

        # Register server
        server_instance = await self.registry.register_server(
            {**server_config, "pid": process_info["pid"]}
        )

        # Wait for server to be ready
        await self._wait_for_server_ready(server_instance.host, server_instance.port)

        # Update status to running
        await self.registry.update_server_status(server_instance.id, "running")

        return {
            "status": "started",
            "server_id": server_instance.id,
            "process_id": process_info["pid"],
            "host": server_instance.host,
            "port": server_instance.port,
            "daemon": True,
            "startup_time": time.time() - server_instance.start_time,
        }

    async def _start_interactive_server(
        self, server_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Start server in interactive mode."""
        # For interactive mode, we'll use a simpler approach
        # In a real implementation, this would start the actual MCP server
        raise ServerError(
            "Interactive server mode not yet implemented",
            "Use daemon mode with --daemon flag for now",
        )

    async def _stop_daemon_server(
        self, server_id: str, force: bool, timeout: int
    ) -> bool:
        """Stop daemon server."""
        return await self.daemon_manager.stop_daemon_server(server_id, timeout)

    async def _stop_interactive_server(
        self, server_id: str, force: bool, timeout: int
    ) -> bool:
        """Stop interactive server."""
        if server_id not in self.interactive_servers:
            return False

        process = self.interactive_servers[server_id]

        try:
            if force:
                process.kill()
            else:
                process.terminate()

            # Wait for shutdown
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                if not force:
                    process.kill()
                    process.wait()

            # Remove from tracking
            del self.interactive_servers[server_id]
            return True

        except Exception as e:
            logger.error(
                "Failed to stop interactive server",
                server_id=server_id,
                error=str(e),
            )
            return False

    async def _wait_for_server_ready(self, host: str, port: int, timeout: int = 30):
        """Wait for server to be ready to accept connections."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex((host, port))
                sock.close()

                if result == 0:
                    logger.info("Server is ready", host=host, port=port)
                    return

            except Exception:
                pass

            await asyncio.sleep(0.5)

        raise ServerError(
            f"Server did not become ready within {timeout} seconds",
            "Check server logs for startup errors",
        )
