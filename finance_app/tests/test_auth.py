from uuid import uuid4

import httpx


async def test_register_and_login_roundtrip(client: httpx.AsyncClient):
    email = f"user-{uuid4()}@example.com"

    reg = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123", "full_name": "Test User"},
    )
    assert reg.status_code == 201, reg.text
    body = reg.json()
    assert body["email"] == email
    assert body["full_name"] == "Test User"
    assert body["role"] == "viewer"
    assert "id" in body and body["id"]
    assert "created_at" in body and body["created_at"]

    login = await client.post("/api/auth/login", json={"email": email, "password": "password123"})
    assert login.status_code == 200, login.text
    token = login.json()
    assert token["token_type"] == "bearer"
    assert isinstance(token["access_token"], str) and token["access_token"]


async def test_register_duplicate_email_conflict(client: httpx.AsyncClient):
    email = f"dup-{uuid4()}@example.com"

    r1 = await client.post("/api/auth/register", json={"email": email, "password": "password123"})
    assert r1.status_code == 201, r1.text

    r2 = await client.post("/api/auth/register", json={"email": email, "password": "password123"})
    assert r2.status_code == 409
    assert r2.json() == {"detail": "Email already registered"}


async def test_login_rejects_wrong_password(client: httpx.AsyncClient):
    email = f"pw-{uuid4()}@example.com"
    await client.post("/api/auth/register", json={"email": email, "password": "password123"})

    bad = await client.post("/api/auth/login", json={"email": email, "password": "wrongpass123"})
    assert bad.status_code == 401
    assert bad.json() == {"detail": "Invalid authentication credentials"}


async def test_refresh_requires_auth(client: httpx.AsyncClient):
    r = await client.post("/api/auth/refresh")
    assert r.status_code == 401
    assert r.json()["detail"] == "Not authenticated"
