"""Sample test to verify testing setup."""

import pytest


def test_basic_assertion():
    """Test basic assertion to verify pytest setup."""
    assert 1 + 1 == 2


def test_sample_openapi_fixture(sample_openapi_spec):
    """Test that OpenAPI fixture is properly formatted."""
    assert "openapi" in sample_openapi_spec
    assert sample_openapi_spec["openapi"] == "3.0.0"
    assert "info" in sample_openapi_spec
    assert "paths" in sample_openapi_spec
    assert "/users" in sample_openapi_spec["paths"]


@pytest.mark.asyncio
async def test_async_functionality():
    """Test async functionality works in tests."""
    import asyncio
    await asyncio.sleep(0.01)
    assert True


@pytest.mark.performance
def test_performance_marker():
    """Test that performance marker works."""
    # This would be a performance test
    assert True


@pytest.mark.slow
def test_slow_marker():
    """Test that slow marker works."""
    # This would be a slow test
    assert True