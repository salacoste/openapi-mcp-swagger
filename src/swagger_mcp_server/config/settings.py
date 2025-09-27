"""Application configuration settings."""

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class LoggingConfig(BaseSettings):
    """Logging configuration settings."""

    level: str = Field(default="INFO", description="Log level")
    file_path: Optional[str] = Field(default=None, description="Log file path")
    json_format: bool = Field(default=True, description="Use JSON log format")
    enable_performance: bool = Field(
        default=True, description="Enable performance logging"
    )

    class Config:
        env_prefix = "LOG_"


class DatabaseConfig(BaseSettings):
    """Database configuration settings."""

    path: str = Field(
        default="swagger_mcp.db", description="Database file path"
    )
    pool_size: int = Field(default=10, description="Connection pool size")
    timeout: int = Field(default=30, description="Query timeout in seconds")

    class Config:
        env_prefix = "DB_"


class ServerConfig(BaseSettings):
    """MCP server configuration settings."""

    name: str = Field(default="swagger-mcp-server", description="Server name")
    version: str = Field(default="0.1.0", description="Server version")
    max_connections: int = Field(
        default=100, description="Maximum concurrent connections"
    )
    request_timeout: int = Field(
        default=30, description="Request timeout in seconds"
    )

    class Config:
        env_prefix = "SERVER_"


class ParserConfig(BaseSettings):
    """Parser configuration settings."""

    max_file_size: int = Field(
        default=10 * 1024 * 1024, description="Max file size in bytes (10MB)"
    )
    chunk_size: int = Field(
        default=8192, description="JSON parsing chunk size"
    )
    validate_openapi: bool = Field(
        default=True, description="Validate OpenAPI specification"
    )
    progress_interval: int = Field(
        default=1024 * 1024, description="Progress reporting interval"
    )

    class Config:
        env_prefix = "PARSER_"


class SearchIndexingConfig(BaseSettings):
    """Search indexing configuration."""

    batch_size: int = Field(default=1000, description="Index batch size")
    optimization_threshold: int = Field(
        default=10000, description="Docs before optimization"
    )
    incremental_updates: bool = Field(
        default=True, description="Enable incremental updates"
    )

    class Config:
        env_prefix = "SEARCH_INDEXING_"


class SearchPerformanceConfig(BaseSettings):
    """Search performance configuration."""

    cache_size_mb: int = Field(default=64, description="Cache size in MB")
    max_search_results: int = Field(
        default=1000, description="Maximum search results"
    )
    query_timeout: int = Field(
        default=5, description="Query timeout in seconds"
    )

    class Config:
        env_prefix = "SEARCH_PERFORMANCE_"


class SearchFieldWeights(BaseSettings):
    """Search field weight configuration."""

    endpoint_path: float = Field(
        default=1.5, description="Endpoint path weight"
    )
    description: float = Field(default=1.0, description="Description weight")
    parameters: float = Field(default=0.8, description="Parameters weight")
    tags: float = Field(default=0.6, description="Tags weight")
    summary: float = Field(default=1.2, description="Summary weight")
    operation_id: float = Field(default=0.9, description="Operation ID weight")

    class Config:
        env_prefix = "SEARCH_WEIGHTS_"


class SearchConfig(BaseSettings):
    """Search configuration settings."""

    enabled: bool = Field(default=True, description="Enable search engine")
    engine_type: str = Field(
        default="whoosh", description="Search engine type"
    )
    index_directory: str = Field(
        default="./search_index", description="Index directory"
    )

    # Sub-configurations
    indexing: SearchIndexingConfig = Field(
        default_factory=SearchIndexingConfig
    )
    performance: SearchPerformanceConfig = Field(
        default_factory=SearchPerformanceConfig
    )
    field_weights: SearchFieldWeights = Field(
        default_factory=SearchFieldWeights
    )

    # Legacy fields for backward compatibility
    max_results: int = Field(
        default=50, description="Maximum search results (deprecated)"
    )
    cache_ttl: int = Field(
        default=3600, description="Search cache TTL in seconds"
    )
    enable_bm25: bool = Field(default=True, description="Enable BM25 ranking")

    class Config:
        env_prefix = "SEARCH_"

    def get_index_path(self, data_dir: str = "data") -> Path:
        """Get the search index directory path."""
        index_path = Path(self.index_directory)
        if index_path.is_absolute():
            return index_path
        return Path(data_dir) / index_path


class Settings(BaseSettings):
    """Main application settings."""

    # Sub-configurations
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    parser: ParserConfig = Field(default_factory=ParserConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)

    # Global settings
    debug: bool = Field(default=False, description="Enable debug mode")
    data_dir: str = Field(default="data", description="Data directory path")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def get_log_file_path(self) -> Optional[Path]:
        """Get the log file path if configured."""
        if self.logging.file_path:
            return Path(self.logging.file_path)
        return None

    def get_database_path(self) -> Path:
        """Get the database file path."""
        if Path(self.database.path).is_absolute():
            return Path(self.database.path)
        return Path(self.data_dir) / self.database.path

    def get_data_dir(self) -> Path:
        """Get the data directory path."""
        return Path(self.data_dir)


# Global settings instance
settings = Settings()
