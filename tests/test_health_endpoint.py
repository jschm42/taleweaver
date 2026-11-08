"""The liveness endpoint the frontend's backend status banner probes."""

import pytest


@pytest.mark.asyncio
async def test_health_is_reachable_under_api_without_login(client):
    # Act
    api = await client.get("/api/health")
    root = await client.get("/health")

    # Assert
    assert api.status_code == 200 and api.json() == {"status": "ok"}
    assert root.status_code == 200
