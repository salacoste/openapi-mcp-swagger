"""Pytest configuration and shared fixtures."""

import asyncio
import tempfile
from pathlib import Path
from typing import AsyncGenerator, Dict, Any
import pytest
import aiosqlite
from faker import Faker

fake = Faker()


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def temp_db() -> AsyncGenerator[str, None]:
    """Create a temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        temp_path = f.name

    try:
        yield temp_path
    finally:
        Path(temp_path).unlink(missing_ok=True)


@pytest.fixture
def sample_openapi_spec() -> Dict[str, Any]:
    """Provide a minimal valid OpenAPI 3.0 specification for testing."""
    return {
        "openapi": "3.0.0",
        "info": {
            "title": "Test API",
            "version": "1.0.0",
            "description": "Test API for unit tests"
        },
        "paths": {
            "/users": {
                "get": {
                    "summary": "List users",
                    "description": "Retrieve a list of users",
                    "responses": {
                        "200": {
                            "description": "Success",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {"$ref": "#/components/schemas/User"}
                                    }
                                }
                            }
                        }
                    }
                },
                "post": {
                    "summary": "Create user",
                    "description": "Create a new user",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/User"}
                            }
                        }
                    },
                    "responses": {
                        "201": {
                            "description": "User created",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/User"}
                                }
                            }
                        }
                    }
                }
            },
            "/users/{id}": {
                "get": {
                    "summary": "Get user by ID",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"}
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "User found",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/User"}
                                }
                            }
                        },
                        "404": {
                            "description": "User not found"
                        }
                    }
                }
            }
        },
        "components": {
            "schemas": {
                "User": {
                    "type": "object",
                    "required": ["id", "name", "email"],
                    "properties": {
                        "id": {
                            "type": "integer",
                            "description": "User ID"
                        },
                        "name": {
                            "type": "string",
                            "description": "User full name"
                        },
                        "email": {
                            "type": "string",
                            "format": "email",
                            "description": "User email address"
                        },
                        "created_at": {
                            "type": "string",
                            "format": "date-time",
                            "description": "User creation timestamp"
                        }
                    }
                }
            }
        }
    }


@pytest.fixture
def large_openapi_spec(sample_openapi_spec) -> Dict[str, Any]:
    """Generate a larger OpenAPI spec for performance testing."""
    spec = sample_openapi_spec.copy()

    # Add many endpoints for performance testing
    for i in range(100):
        endpoint_name = fake.word()
        spec["paths"][f"/{endpoint_name}"] = {
            "get": {
                "summary": f"Get {endpoint_name}",
                "description": f"Retrieve {endpoint_name} data",
                "responses": {
                    "200": {
                        "description": "Success",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "id": {"type": "integer"},
                                        "name": {"type": "string"}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

    return spec