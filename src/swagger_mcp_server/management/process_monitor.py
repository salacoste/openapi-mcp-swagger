"""Process monitoring and health checking for MCP servers."""

import asyncio
import socket
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    import psutil
except ImportError:
    psutil = None

import aiohttp
import structlog

logger = structlog.get_logger(__name__)


class HealthLevel(Enum):
    """Health check severity levels."""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class HealthCheck:
    """Individual health check result."""

    name: str
    passed: bool
    level: HealthLevel
    message: str
    details: Optional[Dict[str, Any]] = None
    duration_ms: Optional[float] = None


@dataclass
class HealthStatus:
    """Complete health status for a server."""

    overall_level: HealthLevel
    checks: List[HealthCheck]
    timestamp: float
    issues: List[str]

    @property
    def is_healthy(self) -> bool:
        """Check if server is healthy."""
        return self.overall_level in [HealthLevel.HEALTHY, HealthLevel.WARNING]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "overall_level": self.overall_level.value,
            "checks": [
                {
                    "name": check.name,
                    "passed": check.passed,
                    "level": check.level.value,
                    "message": check.message,
                    "details": check.details,
                    "duration_ms": check.duration_ms,
                }
                for check in self.checks
            ],
            "timestamp": self.timestamp,
            "issues": self.issues,
        }


@dataclass
class ProcessMetrics:
    """Process performance metrics."""

    cpu_percent: float
    memory_mb: float
    memory_percent: float
    threads: int
    connections: int
    uptime_seconds: float
    status: str


@dataclass
class ServerMetrics:
    """Complete server metrics."""

    process: ProcessMetrics
    requests_total: int
    requests_per_minute: float
    response_time_avg_ms: float
    response_time_p95_ms: float
    active_connections: int
    error_rate: float
    last_request_time: Optional[float] = None


class ProcessMonitor:
    """Monitors server processes and health."""

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=10)
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    async def get_process_metrics(self, pid: int) -> Optional[ProcessMetrics]:
        """Get detailed process metrics.

        Args:
            pid: Process ID

        Returns:
            Optional[ProcessMetrics]: Process metrics or None if process not found
        """
        try:
            if psutil is None:
                logger.warning(
                    "psutil not available, cannot get process metrics"
                )
                return None

            process = psutil.Process(pid)

            # Get memory info
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024

            # Get CPU percentage (requires some time to calculate)
            cpu_percent = process.cpu_percent()

            # Get connection count
            try:
                connections = len(process.connections())
            except Exception:
                connections = 0

            return ProcessMetrics(
                cpu_percent=cpu_percent,
                memory_mb=memory_mb,
                memory_percent=process.memory_percent(),
                threads=process.num_threads(),
                connections=connections,
                uptime_seconds=time.time() - process.create_time(),
                status=process.status(),
            )

        except Exception as e:
            logger.warning(
                "Failed to get process metrics", pid=pid, error=str(e)
            )
            return None

    async def check_server_health(
        self, host: str, port: int, server_id: str
    ) -> HealthStatus:
        """Perform comprehensive health check on server.

        Args:
            host: Server host
            port: Server port
            server_id: Server identifier

        Returns:
            HealthStatus: Complete health status
        """
        checks = []
        issues = []

        # Network connectivity check
        network_check = await self._check_network_connectivity(host, port)
        checks.append(network_check)
        if not network_check.passed:
            issues.append(f"Network: {network_check.message}")

        # MCP protocol health check
        mcp_check = await self._check_mcp_health(host, port)
        checks.append(mcp_check)
        if not mcp_check.passed:
            issues.append(f"MCP Protocol: {mcp_check.message}")

        # Response time check
        response_check = await self._check_response_time(host, port)
        checks.append(response_check)
        if not response_check.passed:
            issues.append(f"Response Time: {response_check.message}")

        # Determine overall health level
        overall_level = self._determine_overall_health(checks)

        return HealthStatus(
            overall_level=overall_level,
            checks=checks,
            timestamp=time.time(),
            issues=issues,
        )

    async def get_server_metrics(
        self, pid: int, host: str, port: int
    ) -> Optional[ServerMetrics]:
        """Get comprehensive server metrics.

        Args:
            pid: Process ID
            host: Server host
            port: Server port

        Returns:
            Optional[ServerMetrics]: Complete server metrics
        """
        # Get process metrics
        process_metrics = await self.get_process_metrics(pid)
        if not process_metrics:
            return None

        # Try to get MCP server metrics
        mcp_metrics = await self._get_mcp_metrics(host, port)

        return ServerMetrics(
            process=process_metrics,
            requests_total=mcp_metrics.get("requests_total", 0),
            requests_per_minute=mcp_metrics.get("requests_per_minute", 0.0),
            response_time_avg_ms=mcp_metrics.get("response_time_avg_ms", 0.0),
            response_time_p95_ms=mcp_metrics.get("response_time_p95_ms", 0.0),
            active_connections=mcp_metrics.get("active_connections", 0),
            error_rate=mcp_metrics.get("error_rate", 0.0),
            last_request_time=mcp_metrics.get("last_request_time"),
        )

    async def _check_network_connectivity(
        self, host: str, port: int
    ) -> HealthCheck:
        """Check basic network connectivity."""
        start_time = time.time()

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((host, port))
            sock.close()

            duration_ms = (time.time() - start_time) * 1000

            if result == 0:
                return HealthCheck(
                    name="network_connectivity",
                    passed=True,
                    level=HealthLevel.HEALTHY,
                    message=f"Port {port} is reachable",
                    duration_ms=duration_ms,
                )
            else:
                return HealthCheck(
                    name="network_connectivity",
                    passed=False,
                    level=HealthLevel.CRITICAL,
                    message=f"Cannot connect to port {port}",
                    duration_ms=duration_ms,
                )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheck(
                name="network_connectivity",
                passed=False,
                level=HealthLevel.CRITICAL,
                message=f"Connection error: {str(e)}",
                duration_ms=duration_ms,
            )

    async def _check_mcp_health(self, host: str, port: int) -> HealthCheck:
        """Check MCP protocol health."""
        start_time = time.time()

        try:
            if not self.session:
                self.session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=10)
                )

            # Try to access health endpoint (if available)
            health_url = f"http://{host}:{port}/health"

            async with self.session.get(health_url) as response:
                duration_ms = (time.time() - start_time) * 1000

                if response.status == 200:
                    health_data = await response.json()
                    return HealthCheck(
                        name="mcp_health",
                        passed=True,
                        level=HealthLevel.HEALTHY,
                        message="MCP server is healthy",
                        details=health_data,
                        duration_ms=duration_ms,
                    )
                else:
                    return HealthCheck(
                        name="mcp_health",
                        passed=False,
                        level=HealthLevel.WARNING,
                        message=f"Health endpoint returned status {response.status}",
                        duration_ms=duration_ms,
                    )

        except aiohttp.ClientConnectorError:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheck(
                name="mcp_health",
                passed=False,
                level=HealthLevel.CRITICAL,
                message="Cannot connect to MCP server",
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheck(
                name="mcp_health",
                passed=False,
                level=HealthLevel.WARNING,
                message=f"Health check failed: {str(e)}",
                duration_ms=duration_ms,
            )

    async def _check_response_time(self, host: str, port: int) -> HealthCheck:
        """Check server response time."""
        start_time = time.time()

        try:
            if not self.session:
                self.session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=10)
                )

            # Try a simple request to measure response time
            url = f"http://{host}:{port}/"

            async with self.session.get(url) as response:
                duration_ms = (time.time() - start_time) * 1000

                if duration_ms < 200:
                    level = HealthLevel.HEALTHY
                    message = f"Response time: {duration_ms:.1f}ms (excellent)"
                elif duration_ms < 1000:
                    level = HealthLevel.HEALTHY
                    message = f"Response time: {duration_ms:.1f}ms (good)"
                elif duration_ms < 5000:
                    level = HealthLevel.WARNING
                    message = f"Response time: {duration_ms:.1f}ms (slow)"
                else:
                    level = HealthLevel.CRITICAL
                    message = f"Response time: {duration_ms:.1f}ms (very slow)"

                return HealthCheck(
                    name="response_time",
                    passed=duration_ms < 5000,
                    level=level,
                    message=message,
                    duration_ms=duration_ms,
                )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheck(
                name="response_time",
                passed=False,
                level=HealthLevel.WARNING,
                message=f"Response time check failed: {str(e)}",
                duration_ms=duration_ms,
            )

    async def _get_mcp_metrics(self, host: str, port: int) -> Dict[str, Any]:
        """Get MCP server-specific metrics."""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=10)
                )

            # Try to access metrics endpoint (if available)
            metrics_url = f"http://{host}:{port}/metrics"

            async with self.session.get(metrics_url) as response:
                if response.status == 200:
                    return await response.json()

        except Exception as e:
            logger.debug("Failed to get MCP metrics", error=str(e))

        # Return default metrics if endpoint not available
        return {
            "requests_total": 0,
            "requests_per_minute": 0.0,
            "response_time_avg_ms": 0.0,
            "response_time_p95_ms": 0.0,
            "active_connections": 0,
            "error_rate": 0.0,
        }

    def _determine_overall_health(
        self, checks: List[HealthCheck]
    ) -> HealthLevel:
        """Determine overall health level from individual checks."""
        if not checks:
            return HealthLevel.UNKNOWN

        # Find the worst health level
        levels = [check.level for check in checks]

        if HealthLevel.CRITICAL in levels:
            return HealthLevel.CRITICAL
        elif HealthLevel.WARNING in levels:
            return HealthLevel.WARNING
        elif HealthLevel.HEALTHY in levels:
            return HealthLevel.HEALTHY
        else:
            return HealthLevel.UNKNOWN
