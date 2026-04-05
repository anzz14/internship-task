from __future__ import annotations

from datetime import date
from decimal import Decimal

import httpx


def _as_decimal(value) -> Decimal:
    return Decimal(str(value))


async def test_viewer_cannot_apply_transaction_filters(
    client: httpx.AsyncClient,
    tokens,
    sample_categories,
    make_transaction,
    auth_header,
):
    viewer = tokens["viewer"]["user"]
    make_transaction(
        user_id=viewer.id,
        category_id=sample_categories["income"].id,
        tx_type="income",
        amount=Decimal("10.00"),
        tx_date=date(2026, 4, 1),
    )

    r = await client.get(
        "/api/transactions",
        params={"type": "income"},
        headers=auth_header(tokens["viewer"]["token"]),
    )
    assert r.status_code == 403
    assert r.json() == {"detail": "Viewer cannot apply filters to transactions"}


async def test_admin_can_create_transaction_for_self_and_other_user(
    client: httpx.AsyncClient,
    tokens,
    sample_categories,
    auth_header,
):
    admin = tokens["admin"]["user"]
    viewer = tokens["viewer"]["user"]

    payload = {
        "amount": "123.45",
        "type": "income",
        "category_id": str(sample_categories["income"].id),
        "date": "2026-04-02",
        "notes": "bonus",
    }

    created_self = await client.post(
        "/api/transactions",
        json=payload,
        headers=auth_header(tokens["admin"]["token"]),
    )
    assert created_self.status_code == 201, created_self.text
    body = created_self.json()
    assert body["user_id"] == str(admin.id)
    assert _as_decimal(body["amount"]) == Decimal("123.45")
    assert body["type"] == "income"
    assert body["category_id"] == str(sample_categories["income"].id)
    assert body["date"] == "2026-04-02"
    assert body["notes"] == "bonus"

    payload_other = {**payload, "target_user_id": str(viewer.id), "amount": "10.00"}
    created_other = await client.post(
        "/api/transactions",
        json=payload_other,
        headers=auth_header(tokens["admin"]["token"]),
    )
    assert created_other.status_code == 201, created_other.text
    body2 = created_other.json()
    assert body2["user_id"] == str(viewer.id)
    assert _as_decimal(body2["amount"]) == Decimal("10.00")


async def test_admin_cannot_create_transaction_for_missing_target_user(
    client: httpx.AsyncClient,
    tokens,
    sample_categories,
    auth_header,
):
    payload = {
        "amount": "10.00",
        "type": "income",
        "category_id": str(sample_categories["income"].id),
        "date": "2026-04-02",
        "target_user_id": "00000000-0000-0000-0000-000000000000",
    }

    created = await client.post(
        "/api/transactions",
        json=payload,
        headers=auth_header(tokens["admin"]["token"]),
    )
    assert created.status_code == 404
    assert created.json() == {"detail": "Target user not found"}


async def test_non_admin_can_create_and_update_but_cannot_delete_transactions(
    client: httpx.AsyncClient,
    tokens,
    sample_categories,
    make_transaction,
    auth_header,
):
    analyst = tokens["analyst"]["user"]

    create = await client.post(
        "/api/transactions",
        json={
            "amount": "1.00",
            "type": "expense",
            "category_id": str(sample_categories["expense"].id),
            "date": "2026-04-01",
        },
        headers=auth_header(tokens["analyst"]["token"]),
    )
    assert create.status_code == 201
    created_body = create.json()
    assert created_body["user_id"] == str(analyst.id)

    tx = make_transaction(
        user_id=analyst.id,
        category_id=sample_categories["expense"].id,
        tx_type="expense",
        amount=Decimal("5.00"),
        tx_date=date(2026, 4, 1),
    )

    upd = await client.put(
        f"/api/transactions/{tx.id}",
        json={"notes": "new"},
        headers=auth_header(tokens["analyst"]["token"]),
    )
    assert upd.status_code == 200
    assert upd.json()["notes"] == "new"

    delete = await client.delete(
        f"/api/transactions/{tx.id}",
        headers=auth_header(tokens["analyst"]["token"]),
    )
    assert delete.status_code == 403
    assert delete.json() == {"detail": "Admin access required"}


async def test_admin_update_and_delete_transaction_happy_path(
    client: httpx.AsyncClient,
    tokens,
    sample_categories,
    auth_header,
):
    created = await client.post(
        "/api/transactions",
        json={
            "amount": "9.99",
            "type": "expense",
            "category_id": str(sample_categories["expense"].id),
            "date": "2026-04-01",
            "notes": "old",
        },
        headers=auth_header(tokens["admin"]["token"]),
    )
    assert created.status_code == 201
    tx_id = created.json()["id"]

    updated = await client.put(
        f"/api/transactions/{tx_id}",
        json={"amount": "10.00", "notes": "new"},
        headers=auth_header(tokens["admin"]["token"]),
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert _as_decimal(body["amount"]) == Decimal("10.00")
    assert body["notes"] == "new"

    deleted = await client.delete(
        f"/api/transactions/{tx_id}",
        headers=auth_header(tokens["admin"]["token"]),
    )
    assert deleted.status_code == 204, deleted.text

    missing = await client.get(
        f"/api/transactions/{tx_id}",
        headers=auth_header(tokens["admin"]["token"]),
    )
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Transaction not found"}


async def test_transaction_category_validation_errors(
    client: httpx.AsyncClient,
    tokens,
    sample_categories,
    auth_header,
):
    # Category mismatch => 422
    mismatch = await client.post(
        "/api/transactions",
        json={
            "amount": "1.00",
            "type": "income",
            "category_id": str(sample_categories["expense"].id),
            "date": "2026-04-01",
        },
        headers=auth_header(tokens["admin"]["token"]),
    )
    assert mismatch.status_code == 422
    assert mismatch.json() == {"detail": "Category type mismatch"}

    # Missing category => 404
    missing = await client.post(
        "/api/transactions",
        json={
            "amount": "1.00",
            "type": "expense",
            "category_id": "00000000-0000-0000-0000-000000000000",
            "date": "2026-04-01",
        },
        headers=auth_header(tokens["admin"]["token"]),
    )
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Category not found"}


async def test_transaction_scoping_and_pagination(
    client: httpx.AsyncClient,
    tokens,
    sample_categories,
    make_transaction,
    auth_header,
):
    viewer = tokens["viewer"]["user"]
    analyst = tokens["analyst"]["user"]

    # Create 3 transactions: 2 for viewer, 1 for analyst.
    tx_v1 = make_transaction(
        user_id=viewer.id,
        category_id=sample_categories["income"].id,
        tx_type="income",
        amount=Decimal("10.00"),
        tx_date=date(2026, 4, 2),
        notes="v1",
    )
    tx_v2 = make_transaction(
        user_id=viewer.id,
        category_id=sample_categories["expense"].id,
        tx_type="expense",
        amount=Decimal("2.00"),
        tx_date=date(2026, 4, 1),
        notes="v2",
    )
    tx_a1 = make_transaction(
        user_id=analyst.id,
        category_id=sample_categories["expense"].id,
        tx_type="expense",
        amount=Decimal("3.00"),
        tx_date=date(2026, 4, 3),
        notes="a1",
    )

    # Viewer sees only their own, ordered by date desc.
    r_viewer = await client.get(
        "/api/transactions",
        params={"page": 1, "page_size": 1},
        headers=auth_header(tokens["viewer"]["token"]),
    )
    assert r_viewer.status_code == 200
    body = r_viewer.json()
    assert body["page"] == 1
    assert body["page_size"] == 1
    assert body["total"] == 2
    assert body["total_pages"] == 2
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == str(tx_v1.id)

    r_viewer_p2 = await client.get(
        "/api/transactions",
        params={"page": 2, "page_size": 1},
        headers=auth_header(tokens["viewer"]["token"]),
    )
    assert r_viewer_p2.status_code == 200
    body2 = r_viewer_p2.json()
    assert body2["page"] == 2
    assert body2["total"] == 2
    assert len(body2["items"]) == 1
    assert body2["items"][0]["id"] == str(tx_v2.id)

    # Viewer cannot access analyst transaction (403 due to ownership checks).
    r_forbidden = await client.get(
        f"/api/transactions/{tx_a1.id}",
        headers=auth_header(tokens["viewer"]["token"]),
    )
    assert r_forbidden.status_code == 403
    assert r_forbidden.json() == {"detail": "You are not allowed to access this transaction"}

    # Admin sees all transactions.
    r_admin_income = await client.get(
        "/api/transactions",
        params={"category_id": str(sample_categories["income"].id)},
        headers=auth_header(tokens["admin"]["token"]),
    )
    assert r_admin_income.status_code == 200
    assert r_admin_income.json()["total"] == 1

    r_admin_expense = await client.get(
        "/api/transactions",
        params={"category_id": str(sample_categories["expense"].id)},
        headers=auth_header(tokens["admin"]["token"]),
    )
    assert r_admin_expense.status_code == 200
    assert r_admin_expense.json()["total"] == 2
