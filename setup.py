"""Setup configuration for swagger-mcp-server package."""

from setuptools import setup, find_packages
import os
import sys
from pathlib import Path

# Ensure Python version compatibility
if sys.version_info < (3, 9):
    sys.exit("Python 3.9 or higher is required")

def read_requirements(filename):
    """Read requirements from file."""
    req_file = Path(__file__).parent / filename
    if not req_file.exists():
        return []

    with open(req_file, 'r') as f:
        return [line.strip() for line in f if line.strip() and not line.startswith('#')]

def read_long_description():
    """Read long description from README."""
    readme_file = Path(__file__).parent / "README.md"
    if not readme_file.exists():
        return "Universal Swagger → MCP Server Converter"

    with open(readme_file, "r", encoding="utf-8") as f:
        return f.read()

def get_version():
    """Get version from package."""
    version_file = Path(__file__).parent / "src" / "swagger_mcp_server" / "__version__.py"
    if version_file.exists():
        with open(version_file) as f:
            exec(f.read())
            return locals()['__version__']
    return "1.0.0"

setup(
    name="swagger-mcp-server",
    version=get_version(),
    author="Universal Swagger MCP Server Team",
    author_email="support@swagger-mcp-server.com",
    description="Universal Swagger → MCP Server Converter",
    long_description=read_long_description(),
    long_description_content_type="text/markdown",
    url="https://github.com/swagger-mcp-server/swagger-mcp-server",

    packages=find_packages(where="src"),
    package_dir={"": "src"},

    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
        "Topic :: Documentation",
        "Topic :: Text Processing :: Markup",
        "Topic :: Utilities",
    ],

    python_requires=">=3.9",

    install_requires=[
        "click>=8.0.0",
        "pyyaml>=6.0",
        "aiofiles>=0.8.0",
        "whoosh>=2.7.4",
        "psutil>=5.8.0",
        "aiohttp>=3.8.0",
        "jsonref>=0.2",
        "openapi-spec-validator>=0.4.0",
        "structlog>=22.0.0",
        "asyncio-throttle>=1.0.0",
    ],

    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
            "black>=22.0.0",
            "flake8>=5.0.0",
            "mypy>=1.0.0",
            "isort>=5.10.0",
        ],
        "test": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
            "pytest-mock>=3.10.0",
        ],
    },

    entry_points={
        "console_scripts": [
            "swagger-mcp-server=swagger_mcp_server.main:cli",
        ],
    },

    include_package_data=True,
    package_data={
        "swagger_mcp_server": [
            "templates/*.yaml",
            "templates/*.json",
            "schemas/*.json",
            "config/templates/*.yaml",
        ],
    },

    keywords="swagger openapi mcp server converter api documentation",

    project_urls={
        "Homepage": "https://github.com/swagger-mcp-server/swagger-mcp-server",
        "Documentation": "https://docs.swagger-mcp-server.com",
        "Repository": "https://github.com/swagger-mcp-server/swagger-mcp-server",
        "Issues": "https://github.com/swagger-mcp-server/swagger-mcp-server/issues",
        "Changelog": "https://github.com/swagger-mcp-server/swagger-mcp-server/blob/main/CHANGELOG.md",
    },
)