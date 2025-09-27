"""Server registry for tracking and managing MCP server instances."""

import asyncio
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ServerInstance:
    """Represents a registered MCP server instance."""

    id: str
    name: str
    host: str
    port: int
    pid: int
    start_time: float
    config_file: Optional[str] = None
    working_directory: Optional[str] = None
    status: str = "running"
    api_title: Optional[str] = None
    swagger_file: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ServerInstance":
        """Create instance from dictionary."""
        return cls(**data)

    @property
    def uptime(self) -> float:
        """Get server uptime in seconds."""
        return time.time() - self.start_time

    @property
    def url(self) -> str:
        """Get server URL."""
        return f"http://{self.host}:{self.port}"


class ServerRegistry:
    """Registry for managing MCP server instances."""

    def __init__(self, registry_dir: Optional[Path] = None):
        """Initialize server registry.

        Args:
            registry_dir: Directory for registry files (default: ~/.swagger-mcp-server)
        """
        self.registry_dir = registry_dir or (
            Path.home() / ".swagger-mcp-server"
        )
        self.registry_file = self.registry_dir / "servers.json"
        self.lock_file = self.registry_dir / "registry.lock"

        # Ensure directory exists
        self.registry_dir.mkdir(exist_ok=True)

        # Initialize empty registry if it doesn't exist
        if not self.registry_file.exists():
            self._save_registry({})

    async def register_server(
        self, server_info: Dict[str, Any]
    ) -> ServerInstance:
        """Register a new server instance.

        Args:
            server_info: Server configuration and process information

        Returns:
            ServerInstance: The registered server instance
        """
        async with self._registry_lock():
            servers = await self._load_registry()

            # Generate unique server ID
            timestamp = int(time.time())
            server_id = (
                f"{server_info['name']}-{server_info['port']}-{timestamp}"
            )

            # Create server instance
            instance = ServerInstance(
                id=server_id,
                name=server_info["name"],
                host=server_info["host"],
                port=server_info["port"],
                pid=server_info["pid"],
                start_time=time.time(),
                config_file=server_info.get("config_file"),
                working_directory=server_info.get("working_directory"),
                api_title=server_info.get("api_title"),
                swagger_file=server_info.get("swagger_file"),
                status="starting",
            )

            # Add to registry
            servers[server_id] = instance.to_dict()

            # Save registry
            await self._save_registry(servers)

            logger.info(
                "Server registered",
                server_id=server_id,
                port=server_info["port"],
            )
            return instance

    async def unregister_server(self, server_id: str) -> bool:
        """Remove server from registry.

        Args:
            server_id: Server identifier

        Returns:
            bool: True if server was removed, False if not found
        """
        async with self._registry_lock():
            servers = await self._load_registry()

            if server_id in servers:
                del servers[server_id]
                await self._save_registry(servers)
                logger.info("Server unregistered", server_id=server_id)
                return True

            return False

    async def get_server(self, server_id: str) -> Optional[ServerInstance]:
        """Get server instance by ID.

        Args:
            server_id: Server identifier

        Returns:
            Optional[ServerInstance]: Server instance or None if not found
        """
        servers = await self._load_registry()

        if server_id in servers:
            return ServerInstance.from_dict(servers[server_id])

        return None

    async def get_all_servers(self) -> List[ServerInstance]:
        """Get all registered servers.

        Returns:
            List[ServerInstance]: List of all server instances
        """
        servers = await self._load_registry()
        return [ServerInstance.from_dict(data) for data in servers.values()]

    async def get_servers_by_name(self, name: str) -> List[ServerInstance]:
        """Get servers by name.

        Args:
            name: Server name to search for

        Returns:
            List[ServerInstance]: List of matching server instances
        """
        servers = await self.get_all_servers()
        return [server for server in servers if server.name == name]

    async def get_server_by_port(self, port: int) -> Optional[ServerInstance]:
        """Get server by port number.

        Args:
            port: Port number to search for

        Returns:
            Optional[ServerInstance]: Server instance or None if not found
        """
        servers = await self.get_all_servers()

        for server in servers:
            if server.port == port:
                return server

        return None

    async def update_server_status(self, server_id: str, status: str) -> bool:
        """Update server status.

        Args:
            server_id: Server identifier
            status: New status

        Returns:
            bool: True if updated, False if server not found
        """
        async with self._registry_lock():
            servers = await self._load_registry()

            if server_id in servers:
                servers[server_id]["status"] = status
                await self._save_registry(servers)
                logger.debug(
                    "Server status updated", server_id=server_id, status=status
                )
                return True

            return False

    async def cleanup_dead_servers(self) -> List[str]:
        """Remove servers with dead processes from registry.

        Returns:
            List[str]: List of removed server IDs
        """
        async with self._registry_lock():
            servers = await self._load_registry()
            active_servers = {}
            removed_server_ids = []

            for server_id, server_data in servers.items():
                if await self._is_process_alive(server_data["pid"]):
                    active_servers[server_id] = server_data
                else:
                    removed_server_ids.append(server_id)
                    logger.info(
                        "Removing dead server",
                        server_id=server_id,
                        pid=server_data["pid"],
                    )

            if removed_server_ids:
                await self._save_registry(active_servers)

            return removed_server_ids

    async def is_port_available(
        self, port: int, exclude_server_id: Optional[str] = None
    ) -> bool:
        """Check if port is available for new server.

        Args:
            port: Port number to check
            exclude_server_id: Server ID to exclude from check

        Returns:
            bool: True if port is available
        """
        servers = await self.get_all_servers()

        for server in servers:
            if server.port == port and server.id != exclude_server_id:
                # Check if process is still alive
                if await self._is_process_alive(server.pid):
                    return False

        # Also check system port availability
        import socket

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(("localhost", port))
                return True
        except OSError:
            return False

    async def _load_registry(self) -> Dict[str, Any]:
        """Load registry from disk."""
        try:
            if self.registry_file.exists():
                with open(self.registry_file, "r") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning("Failed to load registry", error=str(e))

        return {}

    async def _save_registry(self, servers: Dict[str, Any]):
        """Save registry to disk."""
        try:
            with open(self.registry_file, "w") as f:
                json.dump(servers, f, indent=2)
        except Exception as e:
            logger.error("Failed to save registry", error=str(e))
            raise

    async def _is_process_alive(self, pid: int) -> bool:
        """Check if process is still alive."""
        try:
            import psutil

            process = psutil.Process(pid)
            return process.is_running()
        except (psutil.NoSuchProcess, ImportError):
            return False

    def _registry_lock(self):
        """Context manager for registry file locking."""
        return _RegistryLock(self.lock_file)


class _RegistryLock:
    """Simple file-based lock for registry operations."""

    def __init__(self, lock_file: Path):
        self.lock_file = lock_file

    async def __aenter__(self):
        # Simple lock implementation - wait for lock file to be available
        while self.lock_file.exists():
            await asyncio.sleep(0.1)

        # Create lock file
        self.lock_file.touch()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Remove lock file
        try:
            self.lock_file.unlink()
        except FileNotFoundError:
            pass
