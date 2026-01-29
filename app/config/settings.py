"""Environment-based application settings. Read-only; no business logic."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="embedding-service", description="Service name")
    environment: Literal["development", "staging", "production"] = Field(
        default="development", description="Runtime environment"
    )
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default="INFO", description="Log level name")

    # Server
    host: str = Field(default="0.0.0.0", description="Listen host")
    port: int = Field(default=8000, ge=1, le=65535, description="Listen port")

    # MongoDB (see config/storage/mongo for connection semantics)
    mongo_uri: str = Field(
        default="mongodb://localhost:27017",
        description="MongoDB connection URI",
    )
    mongo_database: str = Field(default="embedding_db", description="Default database name")
    mongo_connect_timeout_ms: int = Field(default=5000, ge=100, description="Connection timeout (ms)")
    mongo_server_selection_timeout_ms: int = Field(
        default=5000, ge=100, description="Server selection timeout (ms)"
    )
    mongo_max_pool_size: int = Field(default=50, ge=1, le=500, description="Max connection pool size")

    # OpenAI (for embedding strategy)
    openai_api_key: str = Field(default="", description="OpenAI API key for embeddings")

    # AWS Bedrock (for embedding strategy)
    aws_region: str = Field(default="us-east-1", description="AWS region for Bedrock")

    # OpenSearch
    opensearch_host: str = Field(default="http://localhost:9200", description="OpenSearch base URL")
    opensearch_username: str = Field(default="admin", description="OpenSearch username")
    opensearch_password: str = Field(default="admin", description="OpenSearch password")
    opensearch_use_ssl: bool = Field(default=True, description="Use HTTPS to OpenSearch")
    opensearch_verify_certs: bool = Field(default=False, description="Verify TLS certificates")
    opensearch_timeout: int = Field(default=30, ge=1, description="Request timeout (seconds)")


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance. Use for app lifetime."""
    return Settings()
