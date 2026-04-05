from __future__ import annotations

from datetime import date
from decimal import Decimal

import httpx


def _as_decimal(value) -> Decimal:
    return Decimal(str(value))


async def test_viewer_cannot_access_analytics(client: httpx.AsyncClient, tokens, auth_header):
    r = await client.get("/api/analytics/summary", headers=auth_header(tokens["viewer"]["token"]))
    assert r.status_code == 403
    assert r.json() == {"detail": "Viewer cannot view analytics"}


async def test_analytics_scoped_for_analyst_and_global_for_admin(
    client: httpx.AsyncClient,
    tokens,
    sample_categories,
    make_transaction,
    auth_header,
):
    analyst = tokens["analyst"]["user"]
    viewer = tokens["viewer"]["user"]

    # Since tests run against the main DB, we capture a baseline for the admin to compute deltas.
    # This ensures that pre-existing real data does not cause failing test assertions.
    admin_before = await client.get(
        "/api/analytics/summary",
        headers=auth_header(tokens["admin"]["token"]),
    )
    assert admin_before.status_code == 200
    before = admin_before.json()

    make_transaction(
        user_id=analyst.id,
        category_id=sample_categories["income"].id,
        tx_type="income",
        amount=Decimal("100.00"),
        tx_date=date(2026, 4, 1),
    )
    make_transaction(
        user_id=analyst.id,
        category_id=sample_categories["expense"].id,
        tx_type="expense",
        amount=Decimal("30.00"),
        tx_date=date(2026, 4, 2),
    )

    # Other user's data should not affect analyst analytics.
    make_transaction(
        user_id=viewer.id,
        category_id=sample_categories["expense"].id,
        tx_type="expense",
        amount=Decimal("999.00"),
        tx_date=date(2026, 4, 3),
    )

    analyst_summary = await client.get(
        "/api/analytics/summary",
        headers=auth_header(tokens["analyst"]["token"]),
    )
    assert analyst_summary.status_code == 200, analyst_summary.text
    s = analyst_summary.json()
    assert _as_decimal(s["total_income"]) == Decimal("100.00")
    assert _as_decimal(s["total_expenses"]) == Decimal("30.00")
    assert _as_decimal(s["balance"]) == Decimal("70.00")
    assert s["period"] == "all-time"

    admin_summary = await client.get(
        "/api/analytics/summary",
        headers=auth_header(tokens["admin"]["token"]),
    )
    assert admin_summary.status_code == 200
    after = admin_summary.json()

    # Assert the delta differences, allowing tests to safely run side-by-side with local dev data.
    assert _as_decimal(after["total_income"]) - _as_decimal(before["total_income"]) == Decimal("100.00")
    assert _as_decimal(after["total_expenses"]) - _as_decimal(before["total_expenses"]) == Decimal("1029.00")
    assert _as_decimal(after["balance"]) - _as_decimal(before["balance"]) == Decimal("-929.00")


async def test_recent_limit_validation(client: httpx.AsyncClient, tokens, auth_header):
    bad_low = await client.get(
        "/api/analytics/recent",
        params={"limit": 0},
        headers=auth_header(tokens["admin"]["token"]),
    )
    assert bad_low.status_code == 422

    bad_high = await client.get(
        "/api/analytics/recent",
        params={"limit": 101},
        headers=auth_header(tokens["admin"]["token"]),
    )
    assert bad_high.status_code == 422
