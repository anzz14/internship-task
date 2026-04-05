import httpx


async def test_health_ok(client: httpx.AsyncClient):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_health_db_ok(client: httpx.AsyncClient):
    r = await client.get("/health/db")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
