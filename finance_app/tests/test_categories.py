import httpx
from sqlalchemy import delete

from finance_app.app.models.category import Category
from finance_app.app.models.transaction import Transaction


async def test_categories_empty_returns_message(
    client: httpx.AsyncClient,
    tokens,
    auth_header,
    db_session,
):
    db_session.execute(delete(Transaction))
    db_session.execute(delete(Category))
    db_session.commit()

    response = await client.get(
        "/api/categories",
        headers=auth_header(tokens["viewer"]["token"]),
    )
    assert response.status_code == 200
    assert response.json() == []


async def test_any_authenticated_user_can_list_and_get_categories(
    client: httpx.AsyncClient,
    tokens,
    sample_categories,
    auth_header,
):
    listed = await client.get(
        "/api/categories",
        headers=auth_header(tokens["viewer"]["token"]),
    )
    assert listed.status_code == 200
    body = listed.json()
    assert isinstance(body, list)
    assert len(body) >= 2

    category_id = sample_categories["income"].id
    got = await client.get(
        f"/api/categories/{category_id}",
        headers=auth_header(tokens["analyst"]["token"]),
    )
    assert got.status_code == 200
    assert got.json()["id"] == str(category_id)


async def test_categories_filter_by_type(
    client: httpx.AsyncClient,
    tokens,
    sample_categories,
    auth_header,
):
    income = await client.get(
        "/api/categories",
        params={"type": "income"},
        headers=auth_header(tokens["viewer"]["token"]),
    )
    assert income.status_code == 200
    assert all(item["type"] == "income" for item in income.json())

    expense = await client.get(
        "/api/categories",
        params={"type": "expense"},
        headers=auth_header(tokens["viewer"]["token"]),
    )
    assert expense.status_code == 200
    assert all(item["type"] == "expense" for item in expense.json())


async def test_only_admin_can_create_update_delete_categories(
    client: httpx.AsyncClient,
    tokens,
    sample_categories,
    auth_header,
):
    forbidden_create = await client.post(
        "/api/categories",
        json={"name": "Investments", "type": "income"},
        headers=auth_header(tokens["analyst"]["token"]),
    )
    assert forbidden_create.status_code == 403
    assert forbidden_create.json() == {"detail": "Admin access required"}

    created = await client.post(
        "/api/categories",
        json={"name": "Investments", "type": "income"},
        headers=auth_header(tokens["admin"]["token"]),
    )
    assert created.status_code == 201, created.text
    created_body = created.json()
    assert created_body["name"] == "Investments"
    assert created_body["type"] == "income"

    category_id = created_body["id"]

    updated = await client.put(
        f"/api/categories/{category_id}",
        json={"name": "Long Term Investments", "type": "income"},
        headers=auth_header(tokens["admin"]["token"]),
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Long Term Investments"

    forbidden_delete = await client.delete(
        f"/api/categories/{category_id}",
        headers=auth_header(tokens["viewer"]["token"]),
    )
    assert forbidden_delete.status_code == 403
    assert forbidden_delete.json() == {"detail": "Admin access required"}

    deleted = await client.delete(
        f"/api/categories/{category_id}",
        headers=auth_header(tokens["admin"]["token"]),
    )
    assert deleted.status_code == 204


async def test_categories_conflict_and_not_found_errors(
    client: httpx.AsyncClient,
    tokens,
    sample_categories,
    auth_header,
):
    duplicate = await client.post(
        "/api/categories",
        json={"name": sample_categories["income"].name, "type": "income"},
        headers=auth_header(tokens["admin"]["token"]),
    )
    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": "Category with same name and type already exists"}

    missing = await client.get(
        "/api/categories/00000000-0000-0000-0000-000000000000",
        headers=auth_header(tokens["viewer"]["token"]),
    )
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Category not found"}
