"""
Seed operational demo data for Onda branches.
Creates branch stock, daily inventories, replenishment orders, and stock transactions.
"""
import sys
import os
from datetime import date, datetime, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models import (
    Branch,
    BranchStock,
    DailyInventory,
    DailyInventoryLine,
    InventoryStatus,
    Item,
    OrderStatus,
    OrderType,
    ReplenishmentOrder,
    ReplenishmentOrderLine,
    StockTransaction,
    TransactionType,
    User,
    Warehouse,
    WarehouseStock,
)


ACTIVE_BRANCH_CODES = [
    "BR-RYD-05", "BR-DMM-03", "BR-DMM-04", "BR-RYD-06", "BR-HSA-01",
    "BR-DMM-05", "BR-DMM-06", "BR-DMM-07", "BR-RYD-07", "BR-DMM-08",
    "BR-RTN-01", "BR-DMM-09", "BR-KHB-02", "BR-DMM-10", "BR-RTN-02",
    "BR-DMM-11", "BR-RYD-08", "BR-RYD-09", "BR-RYD-10", "BR-DMM-12",
    "BR-KHB-03", "BR-DMM-13", "BR-KHB-04", "BR-DMM-14", "BR-RYD-11",
]

RAW_ITEM_CODES = [
    "ONDA-RAW-001", "ONDA-RAW-002", "ONDA-RAW-003", "ONDA-RAW-004",
    "ONDA-RAW-006", "ONDA-RAW-007", "ONDA-RAW-010", "ONDA-RAW-013",
    "ONDA-RAW-014", "ONDA-RAW-015",
]


def decimal_str(value):
    return Decimal(str(value))


def seed_branch_stock(db, branches, items):
    db.query(BranchStock).delete()

    for branch_index, branch in enumerate(branches):
        for item_index, item in enumerate(items):
            if item.item_code.startswith("ONDA-PRD-"):
                continue

            if item.max_qty and Decimal(item.max_qty) > 0:
                base_qty = Decimal(item.max_qty) * Decimal("0.55")
            else:
                base_qty = Decimal("12")

            adjustment = Decimal((branch_index + item_index) % 4)
            current_qty = max(Decimal("0"), base_qty - adjustment)

            if branch.branch_code in {"BR-RYD-06", "BR-DMM-05"} and item.item_code in {"ONDA-RAW-003", "ONDA-RAW-013"}:
                current_qty = Decimal("2")
            if branch.branch_code == "BR-RYD-07" and item.item_code == "ONDA-RAW-001":
                current_qty = Decimal("0")

            db.add(
                BranchStock(
                    branch_id=branch.id,
                    item_id=item.id,
                    current_qty=current_qty.quantize(Decimal("0.001")),
                    reserved_qty=Decimal("0"),
                    in_transit_qty=Decimal("0"),
                )
            )
    db.commit()


def seed_consumption_history(db, branches_by_code, items_by_code, users_by_username):
    db.query(StockTransaction).delete()
    today = datetime.utcnow()

    patterns = [
        ("BR-RYD-05", "branch.user1", "ONDA-RAW-001", [-2.0, -1.5, -2.2, -1.8, -2.0]),
        ("BR-RYD-05", "branch.user1", "ONDA-RAW-003", [-12, -10, -11, -9, -13]),
        ("BR-DMM-04", "branch.user2", "ONDA-RAW-001", [-1.2, -1.4, -1.1, -1.3]),
        ("BR-DMM-04", "branch.user2", "ONDA-RAW-004", [-6, -5, -6, -4]),
        ("BR-RYD-06", "branch.user1", "ONDA-RAW-013", [-8, -7, -6]),
    ]

    for branch_code, username, item_code, qty_list in patterns:
        branch = branches_by_code[branch_code]
        user = users_by_username[username]
        item = items_by_code[item_code]
        for day_offset, qty in enumerate(qty_list, start=1):
            db.add(
                StockTransaction(
                    transaction_date=today - timedelta(days=day_offset),
                    transaction_type=TransactionType.inventory_adjustment,
                    source_type="branch",
                    source_id=branch.id,
                    destination_type="branch",
                    destination_id=branch.id,
                    item_id=item.id,
                    qty=decimal_str(qty),
                    reference_no=f"CONS-{branch.branch_code}-{day_offset}",
                    notes="Demo consumption history",
                    created_by=user.id,
                )
            )
    db.commit()


def add_inventory_with_lines(db, branch, user, inventory_date, status, item_specs):
    inventory = DailyInventory(
        branch_id=branch.id,
        inventory_date=inventory_date,
        status=status,
        submitted_at=datetime.utcnow() if status in {InventoryStatus.submitted, InventoryStatus.approved} else None,
        submitted_by=user.id if status in {InventoryStatus.submitted, InventoryStatus.approved} else None,
        approved_at=datetime.utcnow() if status == InventoryStatus.approved else None,
        approved_by=user.id if status == InventoryStatus.approved else None,
        notes="Onda demo inventory",
        created_by=user.id,
    )
    db.add(inventory)
    db.flush()

    for item, book_qty, counted_qty, note in item_specs:
        variance_qty = decimal_str(counted_qty) - decimal_str(book_qty)
        variance_pct = Decimal("0") if decimal_str(book_qty) == 0 else (variance_qty / decimal_str(book_qty) * Decimal("100"))
        variance_status = "ok"
        if abs(variance_pct) >= Decimal("25"):
            variance_status = "critical"
        elif abs(variance_pct) >= Decimal("10"):
            variance_status = "warning"

        db.add(
            DailyInventoryLine(
                inventory_id=inventory.id,
                item_id=item.id,
                book_qty=decimal_str(book_qty),
                counted_qty=decimal_str(counted_qty),
                variance_qty=variance_qty,
                variance_pct=variance_pct.quantize(Decimal("0.01")),
                variance_status=variance_status,
                below_min_flag=decimal_str(counted_qty) < decimal_str(item.min_qty),
                out_of_stock_flag=decimal_str(counted_qty) <= 0,
                notes=note,
            )
        )

        if status == InventoryStatus.approved:
            stock = db.query(BranchStock).filter(
                BranchStock.branch_id == branch.id,
                BranchStock.item_id == item.id,
            ).first()
            if stock:
                stock.current_qty = decimal_str(counted_qty)

    db.commit()
    return inventory


def seed_inventories(db, branches_by_code, items_by_code, users_by_username):
    db.query(DailyInventoryLine).delete()
    db.query(DailyInventory).delete()
    today = date.today()

    add_inventory_with_lines(
        db,
        branches_by_code["BR-RYD-05"],
        users_by_username["branch.user1"],
        today,
        InventoryStatus.approved,
        [
            (items_by_code["ONDA-RAW-001"], 18, 16.5, "High espresso sales"),
            (items_by_code["ONDA-RAW-003"], 40, 34, "Morning rush"),
            (items_by_code["ONDA-RAW-013"], 22, 20, "Cup usage counted"),
        ],
    )

    add_inventory_with_lines(
        db,
        branches_by_code["BR-DMM-04"],
        users_by_username["branch.user2"],
        today,
        InventoryStatus.approved,
        [
            (items_by_code["ONDA-RAW-001"], 14, 13, "Normal variance"),
            (items_by_code["ONDA-RAW-004"], 18, 14, "Oat milk demand"),
            (items_by_code["ONDA-RAW-014"], 16, 15, "Cold cups recounted"),
        ],
    )

    add_inventory_with_lines(
        db,
        branches_by_code["BR-RYD-06"],
        users_by_username["branch.user1"],
        today,
        InventoryStatus.submitted,
        [
            (items_by_code["ONDA-RAW-003"], 8, 5, "Needs replenishment"),
            (items_by_code["ONDA-RAW-013"], 6, 3, "Low cup stock"),
            (items_by_code["ONDA-RAW-001"], 7, 6, "Beans counted"),
        ],
    )

    for offset, branch_code in enumerate(["BR-DMM-05", "BR-RYD-07", "BR-KHB-02"], start=1):
        branch_user = users_by_username["branch.user2"] if branch_code.startswith("BR-DMM") or branch_code.startswith("BR-KHB") else users_by_username["branch.user1"]
        add_inventory_with_lines(
            db,
            branches_by_code[branch_code],
            branch_user,
            today - timedelta(days=offset),
            InventoryStatus.approved,
            [
                (items_by_code["ONDA-RAW-001"], 12, 11, "Historical approved inventory"),
                (items_by_code["ONDA-RAW-003"], 28, 24, "Historical approved inventory"),
                (items_by_code["ONDA-RAW-013"], 18, 17, "Historical approved inventory"),
            ],
        )


def create_order(db, order_no, branch, warehouse, status, user, inventory_id, order_date, lines, note):
    order = ReplenishmentOrder(
        order_no=order_no,
        branch_id=branch.id,
        warehouse_id=warehouse.id,
        order_type=OrderType.auto_replenishment,
        status=status,
        inventory_id=inventory_id,
        order_date=order_date,
        notes=note,
        created_by=user.id,
        branch_reviewed_at=datetime.utcnow() if status not in {OrderStatus.system_generated, OrderStatus.draft} else None,
        branch_reviewed_by=user.id if status not in {OrderStatus.system_generated, OrderStatus.draft} else None,
        submitted_to_warehouse_at=datetime.utcnow() if status in {
            OrderStatus.submitted_to_warehouse, OrderStatus.under_review, OrderStatus.approved,
            OrderStatus.partially_approved, OrderStatus.picking, OrderStatus.dispatched,
            OrderStatus.received, OrderStatus.closed
        } else None,
        wh_reviewed_at=datetime.utcnow() if status in {
            OrderStatus.under_review, OrderStatus.approved, OrderStatus.partially_approved,
            OrderStatus.picking, OrderStatus.dispatched, OrderStatus.received, OrderStatus.closed
        } else None,
        wh_reviewed_by=user.id if status in {
            OrderStatus.under_review, OrderStatus.approved, OrderStatus.partially_approved,
            OrderStatus.picking, OrderStatus.dispatched, OrderStatus.received, OrderStatus.closed
        } else None,
        wh_approved_at=datetime.utcnow() if status in {
            OrderStatus.approved, OrderStatus.partially_approved, OrderStatus.picking,
            OrderStatus.dispatched, OrderStatus.received, OrderStatus.closed
        } else None,
        wh_approved_by=user.id if status in {
            OrderStatus.approved, OrderStatus.partially_approved, OrderStatus.picking,
            OrderStatus.dispatched, OrderStatus.received, OrderStatus.closed
        } else None,
        picking_started_at=datetime.utcnow() if status in {
            OrderStatus.picking, OrderStatus.dispatched, OrderStatus.received, OrderStatus.closed
        } else None,
        dispatched_at=datetime.utcnow() if status in {
            OrderStatus.dispatched, OrderStatus.received, OrderStatus.closed
        } else None,
        dispatched_by=user.id if status in {
            OrderStatus.dispatched, OrderStatus.received, OrderStatus.closed
        } else None,
        received_at=datetime.utcnow() if status in {OrderStatus.received, OrderStatus.closed} else None,
        closed_at=datetime.utcnow() if status == OrderStatus.closed else None,
        dispatch_note_no=f"DN-{order_no}" if status in {OrderStatus.dispatched, OrderStatus.received, OrderStatus.closed} else None,
    )
    db.add(order)
    db.flush()

    for item, requested, approved, dispatched, received, shortage in lines:
        db.add(
            ReplenishmentOrderLine(
                order_id=order.id,
                item_id=item.id,
                suggested_qty=decimal_str(requested),
                branch_requested_qty=decimal_str(requested),
                wh_approved_qty=decimal_str(approved),
                picked_qty=decimal_str(dispatched if status in {OrderStatus.picking, OrderStatus.dispatched, OrderStatus.received, OrderStatus.closed} else 0),
                dispatched_qty=decimal_str(dispatched if status in {OrderStatus.dispatched, OrderStatus.received, OrderStatus.closed} else 0),
                received_qty=decimal_str(received if status in {OrderStatus.received, OrderStatus.closed} else 0),
                shortage_flag=shortage,
                shortage_reason="Supplier shortage" if shortage else None,
                line_status="received" if status in {OrderStatus.received, OrderStatus.closed} else (
                    "dispatched" if status == OrderStatus.dispatched else (
                        "approved" if status in {OrderStatus.approved, OrderStatus.partially_approved, OrderStatus.picking} else "pending"
                    )
                ),
                notes="Demo replenishment line",
            )
        )
    db.commit()
    return order


def seed_orders_and_transactions(db, branches_by_code, items_by_code, users_by_username, inventories_by_branch):
    db.query(ReplenishmentOrderLine).delete()
    db.query(ReplenishmentOrder).delete()

    today = date.today()
    wh_ryd = db.query(Warehouse).filter(Warehouse.warehouse_code == "WH-RYD").first()
    wh_dmm = db.query(Warehouse).filter(Warehouse.warehouse_code == "WH-DMM").first()
    manager_ryd = users_by_username["branch.mgr1"]
    manager_dmm = users_by_username["branch.mgr2"]

    order1 = create_order(
        db,
        "ORD-ONDA-0001",
        branches_by_code["BR-RYD-06"],
        wh_ryd,
        OrderStatus.submitted_to_warehouse,
        manager_ryd,
        inventories_by_branch["BR-RYD-06"].id,
        today,
        [
            (items_by_code["ONDA-RAW-003"], 24, 0, 0, 0, False),
            (items_by_code["ONDA-RAW-013"], 12, 0, 0, 0, False),
        ],
        "Submitted after low stock count",
    )

    order2 = create_order(
        db,
        "ORD-ONDA-0002",
        branches_by_code["BR-DMM-04"],
        wh_dmm,
        OrderStatus.approved,
        manager_dmm,
        inventories_by_branch["BR-DMM-04"].id,
        today,
        [
            (items_by_code["ONDA-RAW-001"], 8, 8, 0, 0, False),
            (items_by_code["ONDA-RAW-004"], 10, 8, 0, 0, True),
        ],
        "Approved and waiting for picking",
    )

    order3 = create_order(
        db,
        "ORD-ONDA-0003",
        branches_by_code["BR-RYD-05"],
        wh_ryd,
        OrderStatus.dispatched,
        manager_ryd,
        inventories_by_branch["BR-RYD-05"].id,
        today,
        [
            (items_by_code["ONDA-RAW-001"], 6, 6, 6, 0, False),
            (items_by_code["ONDA-RAW-013"], 10, 10, 9, 0, True),
        ],
        "Dispatched and pending branch receipt",
    )

    order4 = create_order(
        db,
        "ORD-ONDA-0004",
        branches_by_code["BR-DMM-05"],
        wh_dmm,
        OrderStatus.closed,
        manager_dmm,
        None,
        today - timedelta(days=1),
        [
            (items_by_code["ONDA-RAW-003"], 20, 20, 20, 19, False),
            (items_by_code["ONDA-RAW-014"], 10, 9, 9, 9, False),
        ],
        "Completed historical order",
    )

    tx_specs = [
        (TransactionType.warehouse_dispatch, wh_ryd.id, branches_by_code["BR-RYD-05"].id, items_by_code["ONDA-RAW-001"].id, 6, "ORD-ONDA-0003", manager_ryd.id),
        (TransactionType.warehouse_dispatch, wh_ryd.id, branches_by_code["BR-RYD-05"].id, items_by_code["ONDA-RAW-013"].id, 9, "ORD-ONDA-0003", manager_ryd.id),
        (TransactionType.warehouse_dispatch, wh_dmm.id, branches_by_code["BR-DMM-05"].id, items_by_code["ONDA-RAW-003"].id, 20, "ORD-ONDA-0004", manager_dmm.id),
        (TransactionType.branch_receipt, wh_dmm.id, branches_by_code["BR-DMM-05"].id, items_by_code["ONDA-RAW-003"].id, 19, "ORD-ONDA-0004", manager_dmm.id),
        (TransactionType.branch_receipt, wh_dmm.id, branches_by_code["BR-DMM-05"].id, items_by_code["ONDA-RAW-014"].id, 9, "ORD-ONDA-0004", manager_dmm.id),
    ]
    for tx_type, source_id, destination_id, item_id, qty, ref_no, user_id in tx_specs:
        db.add(
            StockTransaction(
                transaction_date=datetime.utcnow(),
                transaction_type=tx_type,
                source_type="warehouse",
                source_id=source_id,
                destination_type="branch",
                destination_id=destination_id,
                item_id=item_id,
                qty=decimal_str(qty),
                reference_no=ref_no,
                notes="Onda demo operation",
                created_by=user_id,
            )
        )
    db.commit()

    return [order1, order2, order3, order4]


def main():
    db = SessionLocal()
    try:
        branches = db.query(Branch).filter(
            Branch.branch_code.in_(ACTIVE_BRANCH_CODES),
            Branch.active == True,
            Branch.is_deleted == False,
        ).all()
        items = db.query(Item).filter(Item.active == True, Item.is_deleted == False).all()
        users = db.query(User).filter(User.username.in_(["branch.user1", "branch.user2", "branch.mgr1", "branch.mgr2"])).all()

        branches_by_code = {b.branch_code: b for b in branches}
        items_by_code = {i.item_code: i for i in items}
        users_by_username = {u.username: u for u in users}

        seed_branch_stock(db, branches, items)
        seed_consumption_history(db, branches_by_code, items_by_code, users_by_username)
        seed_inventories(db, branches_by_code, items_by_code, users_by_username)

        inventories = db.query(DailyInventory).filter(
            DailyInventory.branch_id.in_([b.id for b in branches]),
            DailyInventory.inventory_date == date.today(),
        ).all()
        inventories_by_branch = {b.branch_code: None for b in branches}
        for inv in inventories:
            for code, branch in branches_by_code.items():
                if branch.id == inv.branch_id:
                    inventories_by_branch[code] = inv

        orders = seed_orders_and_transactions(db, branches_by_code, items_by_code, users_by_username, inventories_by_branch)

        print(f"Seeded branch stock for {len(branches)} branches")
        print(f"Seeded {len(inventories)} inventories for today")
        print(f"Seeded {len(orders)} replenishment orders")
        print("Operational demo data ready")
    finally:
        db.close()


if __name__ == "__main__":
    main()
