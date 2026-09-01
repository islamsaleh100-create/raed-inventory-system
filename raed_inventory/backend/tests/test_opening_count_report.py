"""Report display for opening count — display-only; movement_diff unchanged in DB."""
from decimal import Decimal

from tests.test_shift_ops_gaps import (
    API,
    _fill_and_submit_cash,
    _login,
    _open_shift,
    _seed,
)


def _submit_opening_count(client, hdr, shift_id, closing_first=10):
    body = client.post(f"{API}/shifts/{shift_id}/count", headers=hdr).json()
    line = body["lines"][0]
    payload = [
        {
            "item_id": ln["item_id"],
            "received_qty": 0,
            "returned_qty": 0,
            "damaged_qty": 0,
            "closing_balance": closing_first if ln["item_id"] == line["item_id"] else 0,
        }
        for ln in body["lines"]
    ]
    client.patch(f"{API}/shifts/{shift_id}/count/lines", json={"lines": payload}, headers=hdr)
    client.post(f"{API}/shifts/{shift_id}/count/submit", headers=hdr)
    _fill_and_submit_cash(client, hdr, shift_id)
    return line["item_id"]


def test_opening_count_report_tag_and_filter_exclusion(db, client):
    seed = _seed(db, items=2, suffix="RP")
    bhdr = _login(client, seed["usernames"]["branch"])
    ahdr = _login(client, seed["usernames"]["admin"])

    shift1 = _open_shift(client, bhdr, day="2026-08-01", number=1)
    item_id = _submit_opening_count(client, bhdr, shift1, closing_first=10)

    report = client.get(f"{API}/reports/shift-operations", headers=ahdr).json()
    row = next(i for i in report["items"] if i["id"] == shift1)
    assert row["is_opening_count"] is True
    assert row["negative_movement_exceptions"] == []
    assert len(row["opening_balance_lines"]) >= 1
    assert Decimal(row["opening_balance_lines"][0]["movement_diff"]) == Decimal("-10")

    filtered = client.get(
        f"{API}/reports/shift-operations",
        params={"negative_movement_only": True},
        headers=ahdr,
    ).json()
    assert shift1 not in {i["id"] for i in filtered["items"]}

    shift2 = _open_shift(client, bhdr, day="2026-08-02", number=1)
    client.post(f"{API}/shifts/{shift2}/count", headers=bhdr)
    count2 = client.get(f"{API}/shifts/{shift2}/count", headers=bhdr).json()
    line2 = next(ln for ln in count2["lines"] if ln["item_id"] == item_id)
    client.patch(
        f"{API}/shifts/{shift2}/count/lines",
        json={"lines": [{
            "item_id": line2["item_id"],
            "received_qty": 0,
            "returned_qty": 0,
            "damaged_qty": 0,
            "closing_balance": 15,
            "movement_exception_reason": "Unregistered delivery",
        }]},
        headers=bhdr,
    )
    client.post(f"{API}/shifts/{shift2}/count/submit", headers=bhdr)
    _fill_and_submit_cash(client, bhdr, shift2)

    report2 = client.get(f"{API}/reports/shift-operations", headers=ahdr).json()
    row2 = next(i for i in report2["items"] if i["id"] == shift2)
    assert row2["is_opening_count"] is False
    assert len(row2["negative_movement_exceptions"]) == 1

    filtered2 = client.get(
        f"{API}/reports/shift-operations",
        params={"negative_movement_only": True},
        headers=ahdr,
    ).json()
    assert shift2 in {i["id"] for i in filtered2["items"]}
