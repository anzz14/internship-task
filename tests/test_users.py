import httpx


async def test_users_admin_only_endpoints(
    client: httpx.AsyncClient,
    tokens,
    auth_header,
):
    # Non-admin forbidden
    forbidden = await client.get("/api/users", headers=auth_header(tokens["viewer"]["token"]))
    assert forbidden.status_code == 403
    assert forbidden.json() == {"detail": "Admin access required"}

    # Admin can list
    listed = await client.get("/api/users", headers=auth_header(tokens["admin"]["token"]))
    assert listed.status_code == 200
    users = listed.json()
    assert isinstance(users, list)

    emails = {u["email"] for u in users}
    assert {tokens["viewer"]["user"].email, tokens["analyst"]["user"].email, tokens["admin"]["user"].email}.issubset(emails)


async def test_admin_can_get_update_role_and_delete_user(
    client: httpx.AsyncClient,
    tokens,
    auth_header,
):
    viewer = tokens["viewer"]["user"]

    got = await client.get(f"/api/users/{viewer.id}", headers=auth_header(tokens["admin"]["token"]))
    assert got.status_code == 200
    assert got.json()["id"] == str(viewer.id)

    updated = await client.put(
        f"/api/users/{viewer.id}/role",
        json={"role": "analyst"},
        headers=auth_header(tokens["admin"]["token"]),
    )
    assert updated.status_code == 200
    assert updated.json()["role"] == "analyst"

    # Role change applies immediately for auth checks (token sub is user id).
    analytics = await client.get(
        "/api/analytics/summary",
        headers=auth_header(tokens["viewer"]["token"]),
    )
    assert analytics.status_code == 200

    # Delete an existing user
    analyst = tokens["analyst"]["user"]
    deleted = await client.delete(
        f"/api/users/{analyst.id}",
        headers=auth_header(tokens["admin"]["token"]),
    )
    assert deleted.status_code == 204

    # Their token should no longer authenticate.
    whoami = await client.get(
        "/api/transactions",
        headers=auth_header(tokens["analyst"]["token"]),
    )
    assert whoami.status_code == 401
    assert whoami.json() == {"detail": "Invalid authentication credentials"}
