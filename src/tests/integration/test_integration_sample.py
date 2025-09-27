"""Sample integration test to verify setup."""

import pytest


@pytest.mark.integration
def test_integration_setup():
    """Test integration test setup."""
    assert True


@pytest.mark.integration
async def test_temp_db_fixture(temp_db):
    """Test temporary database fixture."""
    import aiosqlite

    async with aiosqlite.connect(temp_db) as db:
        await db.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
        await db.commit()

        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = await cursor.fetchall()
        assert len(tables) == 1
        assert tables[0][0] == "test"
