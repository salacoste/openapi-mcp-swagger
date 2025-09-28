"""Validation system for converted MCP servers."""

import asyncio
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


class ConversionValidator:
    """Validates generated MCP server functionality and deployment readiness."""

    def __init__(self):
        self.validation_timeout = 30  # seconds

    async def validate_generated_server(self, package_dir: str) -> Dict[str, Any]:
        """Comprehensive validation of generated MCP server."""
        logger.info("Starting MCP server validation", package_dir=package_dir)

        validation_results = {
            "server_files": await self._validate_server_files(package_dir),
            "configuration": await self._validate_configuration(package_dir),
            "dependencies": await self._validate_dependencies(package_dir),
            "database": await self._validate_database(package_dir),
            "search_index": await self._validate_search_index(package_dir),
            "deployment_readiness": await self._validate_deployment_readiness(
                package_dir
            ),
        }

        # Determine overall status
        all_passed = all(
            result.get("passed", False) for result in validation_results.values()
        )

        overall_result = {
            "overall_status": "passed" if all_passed else "failed",
            "validation_results": validation_results,
            "recommendations": self._generate_validation_recommendations(
                validation_results
            ),
            "summary": self._generate_validation_summary(validation_results),
        }

        logger.info(
            "Validation completed",
            status=overall_result["overall_status"],
            total_checks=len(validation_results),
        )

        return overall_result

    async def _validate_server_files(self, package_dir: str) -> Dict[str, Any]:
        """Validate that all required server files are present and valid."""
        required_files = [
            "server.py",
            "requirements.txt",
            "README.md",
            "config/server.yaml",
            "start.sh",
            "start.bat",
        ]

        optional_files = [
            "Dockerfile",
            "docker-compose.yml",
            "mcp-server.service",
            ".env.example",
            ".gitignore",
            "docs/examples.md",
        ]

        missing_required = []
        missing_optional = []
        invalid_files = []

        # Check required files
        for file_path in required_files:
            full_path = os.path.join(package_dir, file_path)
            if not os.path.exists(full_path):
                missing_required.append(file_path)
            else:
                # Basic validation for key files
                if file_path == "server.py":
                    if not await self._validate_python_syntax(full_path):
                        invalid_files.append(file_path)

        # Check optional files
        for file_path in optional_files:
            full_path = os.path.join(package_dir, file_path)
            if not os.path.exists(full_path):
                missing_optional.append(file_path)

        passed = len(missing_required) == 0 and len(invalid_files) == 0

        return {
            "passed": passed,
            "missing_required": missing_required,
            "missing_optional": missing_optional,
            "invalid_files": invalid_files,
            "details": {
                "required_files_found": len(required_files) - len(missing_required),
                "total_required_files": len(required_files),
                "optional_files_found": len(optional_files) - len(missing_optional),
                "total_optional_files": len(optional_files),
            },
        }

    async def _validate_python_syntax(self, file_path: str) -> bool:
        """Validate Python file syntax."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source = f.read()

            compile(source, file_path, "exec")
            return True
        except SyntaxError as e:
            logger.warning("Python syntax error", file=file_path, error=str(e))
            return False
        except Exception as e:
            logger.warning("Error validating Python file", file=file_path, error=str(e))
            return False

    async def _validate_configuration(self, package_dir: str) -> Dict[str, Any]:
        """Validate configuration files."""
        config_issues = []
        config_warnings = []

        # Check server.yaml
        config_file = os.path.join(package_dir, "config", "server.yaml")
        if os.path.exists(config_file):
            try:
                import yaml

                with open(config_file, "r", encoding="utf-8") as f:
                    config_data = yaml.safe_load(f)

                # Validate config structure
                required_sections = ["server", "database", "search"]
                for section in required_sections:
                    if section not in config_data:
                        config_issues.append(
                            f"Missing {section} section in server.yaml"
                        )

                # Validate server config
                server_config = config_data.get("server", {})
                if "port" in server_config:
                    port = server_config["port"]
                    if not isinstance(port, int) or port < 1024 or port > 65535:
                        config_issues.append(f"Invalid port number: {port}")

            except ImportError:
                config_warnings.append("PyYAML not available to validate YAML syntax")
            except Exception as e:
                config_issues.append(f"Error parsing server.yaml: {str(e)}")
        else:
            config_issues.append("server.yaml configuration file not found")

        # Check requirements.txt
        requirements_file = os.path.join(package_dir, "requirements.txt")
        if os.path.exists(requirements_file):
            try:
                with open(requirements_file, "r", encoding="utf-8") as f:
                    requirements = f.read()

                if "swagger-mcp-server" not in requirements:
                    config_warnings.append(
                        "swagger-mcp-server not found in requirements.txt"
                    )

            except Exception as e:
                config_issues.append(f"Error reading requirements.txt: {str(e)}")
        else:
            config_issues.append("requirements.txt file not found")

        passed = len(config_issues) == 0

        return {
            "passed": passed,
            "issues": config_issues,
            "warnings": config_warnings,
            "details": {
                "config_files_checked": 2,
                "issues_found": len(config_issues),
                "warnings_found": len(config_warnings),
            },
        }

    async def _validate_dependencies(self, package_dir: str) -> Dict[str, Any]:
        """Validate Python dependencies can be installed."""
        requirements_file = os.path.join(package_dir, "requirements.txt")
        if not os.path.exists(requirements_file):
            return {
                "passed": False,
                "error": "requirements.txt not found",
                "details": {},
            }

        try:
            # Create a temporary virtual environment for testing
            with tempfile.TemporaryDirectory() as temp_dir:
                venv_path = os.path.join(temp_dir, "test_venv")

                # Create virtual environment
                result = subprocess.run(
                    [sys.executable, "-m", "venv", venv_path],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                if result.returncode != 0:
                    return {
                        "passed": False,
                        "error": "Failed to create virtual environment",
                        "details": {"stderr": result.stderr},
                    }

                # Get pip path
                if os.name == "nt":  # Windows
                    pip_path = os.path.join(venv_path, "Scripts", "pip")
                else:  # Unix/Linux/macOS
                    pip_path = os.path.join(venv_path, "bin", "pip")

                # Try to install dependencies (dry run)
                result = subprocess.run(
                    [
                        pip_path,
                        "install",
                        "--dry-run",
                        "-r",
                        requirements_file,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )

                # Note: --dry-run might not be available in all pip versions
                # If it fails, we'll do a basic syntax check instead
                if result.returncode != 0 and "--dry-run" in result.stderr:
                    # Fallback: just check if requirements file is readable
                    with open(requirements_file, "r") as f:
                        requirements_content = f.read()

                    # Basic validation - check for obvious issues
                    lines = requirements_content.strip().split("\n")
                    invalid_lines = []
                    for i, line in enumerate(lines, 1):
                        line = line.strip()
                        if line and not line.startswith("#"):
                            # Very basic check for package name format
                            if not any(
                                c.isalnum() or c in "-_."
                                for c in line.split(">=")[0].split("==")[0]
                            ):
                                invalid_lines.append(f"Line {i}: {line}")

                    if invalid_lines:
                        return {
                            "passed": False,
                            "error": "Invalid package specifications",
                            "details": {"invalid_lines": invalid_lines},
                        }

                return {
                    "passed": True,
                    "details": {
                        "requirements_validated": True,
                        "method": "syntax_check"
                        if "--dry-run" in (result.stderr or "")
                        else "dry_run",
                    },
                }

        except subprocess.TimeoutExpired:
            return {
                "passed": False,
                "error": "Dependency validation timed out",
                "details": {},
            }
        except Exception as e:
            return {
                "passed": False,
                "error": f"Dependency validation failed: {str(e)}",
                "details": {},
            }

    async def _validate_database(self, package_dir: str) -> Dict[str, Any]:
        """Validate database files and structure."""
        data_dir = os.path.join(package_dir, "data")
        database_file = os.path.join(data_dir, "mcp_server.db")

        if not os.path.exists(data_dir):
            return {
                "passed": False,
                "error": "Data directory not found",
                "details": {},
            }

        if not os.path.exists(database_file):
            return {
                "passed": False,
                "error": "Database file not found",
                "details": {"expected_path": database_file},
            }

        try:
            # Basic SQLite file validation
            import sqlite3

            # Try to connect and run a simple query
            conn = sqlite3.connect(database_file)
            cursor = conn.cursor()

            # Check if basic tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]

            expected_tables = ["endpoints", "schemas", "metadata"]
            missing_tables = [table for table in expected_tables if table not in tables]

            # Get database size
            db_size = os.path.getsize(database_file)

            conn.close()

            passed = len(missing_tables) == 0 and db_size > 0

            return {
                "passed": passed,
                "missing_tables": missing_tables,
                "details": {
                    "tables_found": len(tables),
                    "database_size_bytes": db_size,
                    "tables": tables,
                },
            }

        except Exception as e:
            return {
                "passed": False,
                "error": f"Database validation failed: {str(e)}",
                "details": {},
            }

    async def _validate_search_index(self, package_dir: str) -> Dict[str, Any]:
        """Validate search index files and structure."""
        search_index_dir = os.path.join(package_dir, "data", "search_index")

        if not os.path.exists(search_index_dir):
            return {
                "passed": False,
                "error": "Search index directory not found",
                "details": {"expected_path": search_index_dir},
            }

        try:
            # Check for search index files
            index_files = os.listdir(search_index_dir)

            if not index_files:
                return {
                    "passed": False,
                    "error": "Search index directory is empty",
                    "details": {},
                }

            # Calculate total index size
            total_size = 0
            for file_name in index_files:
                file_path = os.path.join(search_index_dir, file_name)
                if os.path.isfile(file_path):
                    total_size += os.path.getsize(file_path)

            return {
                "passed": True,
                "details": {
                    "index_files_count": len(index_files),
                    "total_size_bytes": total_size,
                    "files": index_files[:10],  # Limit to first 10 files
                },
            }

        except Exception as e:
            return {
                "passed": False,
                "error": f"Search index validation failed: {str(e)}",
                "details": {},
            }

    async def _validate_deployment_readiness(self, package_dir: str) -> Dict[str, Any]:
        """Validate that the package is ready for deployment."""
        readiness_issues = []
        readiness_warnings = []

        # Check executable permissions on scripts
        startup_scripts = ["start.sh", "start.bat"]
        for script in startup_scripts:
            script_path = os.path.join(package_dir, script)
            if os.path.exists(script_path):
                if script == "start.sh" and os.name != "nt":
                    # Check if executable on Unix systems
                    if not os.access(script_path, os.X_OK):
                        readiness_issues.append(f"{script} is not executable")
            else:
                readiness_warnings.append(f"Startup script {script} not found")

        # Check server.py permissions
        server_file = os.path.join(package_dir, "server.py")
        if os.path.exists(server_file):
            if os.name != "nt" and not os.access(server_file, os.X_OK):
                readiness_warnings.append("server.py is not executable")
        else:
            readiness_issues.append("server.py not found")

        # Check directory structure
        required_dirs = ["data", "config", "docs"]
        for dir_name in required_dirs:
            dir_path = os.path.join(package_dir, dir_name)
            if not os.path.exists(dir_path):
                readiness_issues.append(f"Required directory {dir_name} not found")

        # Check for README
        readme_file = os.path.join(package_dir, "README.md")
        if not os.path.exists(readme_file):
            readiness_issues.append("README.md not found")
        else:
            # Check README size (should have content)
            readme_size = os.path.getsize(readme_file)
            if readme_size < 100:  # Less than 100 bytes
                readiness_warnings.append("README.md appears to be empty or very small")

        passed = len(readiness_issues) == 0

        return {
            "passed": passed,
            "issues": readiness_issues,
            "warnings": readiness_warnings,
            "details": {
                "checks_performed": len(startup_scripts) + len(required_dirs) + 2,
                "issues_found": len(readiness_issues),
                "warnings_found": len(readiness_warnings),
            },
        }

    def _generate_validation_recommendations(
        self, validation_results: Dict[str, Any]
    ) -> List[str]:
        """Generate actionable recommendations based on validation results."""
        recommendations = []

        for category, result in validation_results.items():
            if not result.get("passed", False):
                if category == "server_files":
                    if result.get("missing_required"):
                        recommendations.append(
                            f"Generate missing required files: {', '.join(result['missing_required'])}"
                        )
                    if result.get("invalid_files"):
                        recommendations.append(
                            f"Fix syntax errors in: {', '.join(result['invalid_files'])}"
                        )

                elif category == "configuration":
                    if result.get("issues"):
                        recommendations.append("Review and fix configuration issues")
                        recommendations.extend(
                            f"  - {issue}" for issue in result["issues"][:3]
                        )

                elif category == "dependencies":
                    recommendations.append(
                        "Check Python dependencies and requirements.txt"
                    )
                    if result.get("error"):
                        recommendations.append(f"  - {result['error']}")

                elif category == "database":
                    recommendations.append("Verify database creation and structure")
                    if result.get("missing_tables"):
                        recommendations.append(
                            f"  - Missing tables: {', '.join(result['missing_tables'])}"
                        )

                elif category == "search_index":
                    recommendations.append("Rebuild search index")
                    if result.get("error"):
                        recommendations.append(f"  - {result['error']}")

                elif category == "deployment_readiness":
                    if result.get("issues"):
                        recommendations.append("Fix deployment readiness issues")
                        recommendations.extend(
                            f"  - {issue}" for issue in result["issues"][:3]
                        )

        if not recommendations:
            recommendations.append(
                "All validations passed - server is ready for deployment"
            )

        return recommendations

    def _generate_validation_summary(
        self, validation_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate a summary of validation results."""
        total_checks = len(validation_results)
        passed_checks = sum(
            1 for result in validation_results.values() if result.get("passed", False)
        )

        issues_count = 0
        warnings_count = 0

        for result in validation_results.values():
            issues_count += len(result.get("issues", []))
            warnings_count += len(result.get("warnings", []))

        return {
            "total_validation_categories": total_checks,
            "passed_categories": passed_checks,
            "failed_categories": total_checks - passed_checks,
            "success_rate": (passed_checks / total_checks) * 100
            if total_checks > 0
            else 0,
            "total_issues": issues_count,
            "total_warnings": warnings_count,
            "overall_status": "ready"
            if passed_checks == total_checks
            else "needs_attention",
        }
