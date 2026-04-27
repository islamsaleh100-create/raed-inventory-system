"""
seed_4months.py
===============
يضيف بيانات وهمية واقعية للفترة 2026-01-01 → 2026-04-14 (جرد، طلبيات، مخزون، معاملات، جودة، تدريب، توصيل).

الاستخدام (من مجلد backend):
    python seed_4months.py
"""

from __future__ import annotations

import os
import random
import secrets
import sys
import traceback
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

random.seed(42)

# ── إعداد المسار (يعمل على أي جهاز طالما السكريبت داخل backend)
_BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(_BACKEND))
os.chdir(str(_BACKEND))

from app.database import SessionLocal
from app.models import (
    AssessmentStatus,
    AssessmentVerdict,
    Branch,
    BranchStock,
    DailyInventory,
    DailyInventoryLine,
    DeliveryRecord,
    InventoryStatus,
    Item,
    ItemCategory,
    ItemType,
    OrderStatus,
    OrderType,
    QualityResponseStatus,
    QualityVisit,
    QualityVisitItem,
    QualityVisitResponse,
    QualityVisitStatus,
    ReplenishmentOrder,
    ReplenishmentOrderLine,
    StockTransaction,
    StorageType,
    TrainingAssessment,
    TrainingAssessmentItem,
    TrainingTemplate,
    TrainingTemplateItem,
    TrainingTemplateSection,
    TransactionType,
    UnitOfMeasure,
    User,
    Warehouse,
    WarehouseStock,
)

DATE_START = date(2026, 1, 1)
DATE_END = date(2026, 4, 14)
COMMIT_EVERY = 100


def _d(v: float | int | Decimal) -> Decimal:
    return Decimal(str(round(float(v), 4)))


def weekly_dates() -> list[date]:
    out: list[date] = []
    d = DATE_START
    while d <= DATE_END:
        out.append(d)
        d += timedelta(days=7)
    return out


def biweekly_dates() -> list[date]:
    out: list[date] = []
    d = DATE_START
    while d <= DATE_END:
        out.append(d)
        d += timedelta(days=14)
    return out


def variance_pct(counted: Decimal, book: Decimal) -> Decimal:
    if book == 0:
        return _d(100 if counted > 0 else 0)
    return _d(abs((counted - book) / book) * 100)


def variance_status(pct: Decimal) -> str:
    p = float(pct)
    if p < 10:
        return "ok"
    if p < 25:
        return "warning"
    return "critical"


def pick_branch_actor_id(db: Session, branch_id: int) -> int:
    u = (
        db.query(User)
        .filter(User.branch_id == branch_id, User.is_deleted.is_(False))
        .order_by(User.id)
        .first()
    )
    return u.id if u else 1


def pick_trainee_id(db: Session, branch_id: int) -> int | None:
    u = (
        db.query(User)
        .filter(
            User.branch_id == branch_id,
            User.is_deleted.is_(False),
            User.username.like("branch.user%"),
        )
        .order_by(User.id)
        .first()
    )
    if u:
        return u.id
    u2 = (
        db.query(User)
        .filter(User.branch_id == branch_id, User.is_deleted.is_(False))
        .order_by(User.id)
        .first()
    )
    return u2.id if u2 else None


class CommitBatcher:
    def __init__(self, db: Session, every: int = COMMIT_EVERY) -> None:
        self.db = db
        self.every = every
        self.n = 0

    def bump(self) -> None:
        self.n += 1
        if self.n >= self.every:
            self.db.commit()
            self.n = 0

    def flush(self) -> None:
        if self.n:
            self.db.commit()
            self.n = 0


def ensure_demo_items(db: Session, batch: CommitBatcher, note_lines: list[str]) -> list[Item]:
    n = db.query(Item).filter(Item.is_deleted.is_(False)).count()
    if n >= 5:
        return db.query(Item).filter(Item.is_deleted.is_(False), Item.active.is_(True)).all()

    note_lines.append("⚠️ عدد الأصناف كان أقل من 5 — تمت إضافة 10 أصناف تجريبية (SEED-DEMO-001 … 010).")
    cat = db.query(ItemCategory).filter(ItemCategory.active.is_(True)).first()
    unit = db.query(UnitOfMeasure).filter(UnitOfMeasure.active.is_(True)).first()
    if not cat or not unit:
        note_lines.append("❌ لا يوجد تصنيف أو وحدة قياس — تعذر إنشاء أصناف تجريبية.")
        return db.query(Item).filter(Item.is_deleted.is_(False)).all()

    for i in range(1, 11):
        code = f"SEED-DEMO-{i:03d}"
        if db.query(Item).filter(Item.item_code == code).first():
            continue
        it = Item(
            item_code=code,
            item_name_ar=f"صنف تجريبي سيد {i}",
            item_name_en=f"Seed demo item {i}",
            category_id=cat.id,
            unit_id=unit.id,
            item_type=ItemType.raw_material,
            storage_type=StorageType.ambient,
            min_qty=_d(10 + i),
            max_qty=_d(500),
            reorder_point=_d(15 + i),
            active=True,
            is_deleted=False,
        )
        db.add(it)
        batch.bump()
    db.commit()
    return db.query(Item).filter(Item.is_deleted.is_(False), Item.active.is_(True)).all()


def seed_daily_inventory(db: Session, batch: CommitBatcher, rng: random.Random) -> int:
    added = 0
    branches = db.query(Branch).filter(Branch.is_deleted.is_(False)).all()
    items = db.query(Item).filter(Item.is_deleted.is_(False), Item.active.is_(True)).all()
    if not branches or not items:
        return 0

    wdates = weekly_dates()
    now = datetime.utcnow()

    for br in branches:
        prev_counted: dict[int, Decimal] = {}
        for inv_date in wdates:
            exists = (
                db.query(DailyInventory)
                .filter(
                    DailyInventory.branch_id == br.id,
                    DailyInventory.inventory_date == inv_date,
                )
                .first()
            )
            if exists:
                # حمّل الأرقام من الجرد الموجود لسلسلة book التالية
                lines = (
                    db.query(DailyInventoryLine)
                    .filter(DailyInventoryLine.inventory_id == exists.id)
                    .all()
                )
                prev_counted = {ln.item_id: ln.counted_qty for ln in lines}
                continue

            actor = pick_branch_actor_id(db, br.id)
            inv = DailyInventory(
                branch_id=br.id,
                inventory_date=inv_date,
                status=InventoryStatus.approved,
                submitted_at=now,
                submitted_by=actor,
                approved_at=now,
                approved_by=actor,
                created_by=actor,
            )
            db.add(inv)
            db.flush()

            for it in items:
                mn = float(it.min_qty or 0)
                if mn > 0:
                    counted_f = mn * rng.uniform(0.6, 1.3)
                else:
                    counted_f = rng.uniform(15, 120)
                counted = _d(counted_f)
                book = prev_counted.get(it.id, _d(0))
                var_q = counted - book
                pct = variance_pct(counted, book)
                st = variance_status(pct)
                below = counted < _d(it.min_qty or 0)
                oos = counted <= _d(0)

                ln = DailyInventoryLine(
                    inventory_id=inv.id,
                    item_id=it.id,
                    book_qty=book,
                    counted_qty=counted,
                    variance_qty=var_q,
                    variance_pct=pct,
                    variance_status=st,
                    below_min_flag=below,
                    out_of_stock_flag=oos,
                )
                db.add(ln)
                prev_counted[it.id] = counted

            added += 1
            batch.bump()

    return added


def seed_replenishment_and_stock_tx(
    db: Session, batch: CommitBatcher, rng: random.Random
) -> tuple[int, int]:
    orders_added = 0
    tx_added = 0
    branches = db.query(Branch).filter(Branch.is_deleted.is_(False)).all()
    items = [it.id for it in db.query(Item).filter(Item.is_deleted.is_(False), Item.active.is_(True)).all()]
    if not branches or len(items) < 5:
        return 0, 0

    cutoff = DATE_END - timedelta(days=14)
    admin_id = 1

    for br in branches:
        wh_id = br.warehouse_id
        for od in biweekly_dates():
            if (
                db.query(ReplenishmentOrder)
                .filter(ReplenishmentOrder.branch_id == br.id, ReplenishmentOrder.order_date == od)
                .first()
            ):
                continue

            suffix = secrets.token_hex(3).upper()
            order_no = f"ORD-{od.strftime('%Y%m%d')}-{suffix}"
            if len(order_no) > 30:
                order_no = order_no[:30]

            st = OrderStatus.dispatched if od >= cutoff else OrderStatus.received
            ro = ReplenishmentOrder(
                order_no=order_no,
                branch_id=br.id,
                warehouse_id=wh_id,
                order_type=OrderType.auto_replenishment,
                status=st,
                order_date=od,
                created_by=admin_id,
            )
            if st == OrderStatus.received:
                ro.wh_approved_at = datetime.utcnow()
                ro.wh_approved_by = admin_id
                ro.dispatched_at = datetime.utcnow()
                ro.dispatched_by = admin_id
                ro.received_at = datetime.utcnow()
                ro.closed_at = datetime.utcnow()
            else:
                ro.wh_approved_at = datetime.utcnow()
                ro.wh_approved_by = admin_id
                ro.dispatched_at = datetime.utcnow()
                ro.dispatched_by = admin_id

            db.add(ro)
            db.flush()

            k = rng.randint(5, 10)
            pick_ids = rng.sample(items, k=min(k, len(items)))
            line_qty: list[tuple[int, Decimal]] = []
            for iid in pick_ids:
                sq = _d(rng.randint(10, 50))
                bq = _d(rng.randint(10, 50))
                wq = bq
                pq = bq
                dq = bq
                rq: Decimal = bq if st == OrderStatus.received else _d(0)
                line = ReplenishmentOrderLine(
                    order_id=ro.id,
                    item_id=iid,
                    suggested_qty=sq,
                    branch_requested_qty=bq,
                    wh_approved_qty=wq,
                    picked_qty=pq,
                    dispatched_qty=dq,
                    received_qty=rq,
                    line_status="received" if st == OrderStatus.received else "dispatched",
                )
                db.add(line)
                line_qty.append((iid, rq))

            if st == OrderStatus.received:
                ts = ro.received_at or datetime.utcnow()
                for iid, rq in line_qty:
                    if rq <= 0:
                        continue
                    exists_tx = (
                        db.query(StockTransaction)
                        .filter(
                            StockTransaction.reference_no == order_no,
                            StockTransaction.item_id == iid,
                            StockTransaction.transaction_type == TransactionType.branch_receipt,
                        )
                        .first()
                    )
                    if exists_tx:
                        continue
                    tx = StockTransaction(
                        transaction_date=ts,
                        transaction_type=TransactionType.branch_receipt,
                        source_type="warehouse",
                        source_id=wh_id,
                        destination_type="branch",
                        destination_id=br.id,
                        item_id=iid,
                        qty=rq,
                        reference_no=order_no,
                        created_by=admin_id,
                    )
                    db.add(tx)
                    tx_added += 1

            orders_added += 1
            batch.bump()

    return orders_added, tx_added


def upsert_branch_warehouse_stock(db: Session, batch: CommitBatcher, rng: random.Random) -> int:
    updated = 0
    branches = db.query(Branch).filter(Branch.is_deleted.is_(False)).all()
    warehouses = db.query(Warehouse).filter(Warehouse.is_deleted.is_(False)).all()
    items = db.query(Item).filter(Item.is_deleted.is_(False)).all()

    for br in branches:
        for it in items:
            q = _d(rng.randint(20, 200))
            row = (
                db.query(BranchStock)
                .filter(BranchStock.branch_id == br.id, BranchStock.item_id == it.id)
                .first()
            )
            if row:
                row.current_qty = q
            else:
                db.add(BranchStock(branch_id=br.id, item_id=it.id, current_qty=q))
            updated += 1
            batch.bump()

    for wh in warehouses:
        for it in items:
            q = _d(rng.randint(500, 2000))
            row = (
                db.query(WarehouseStock)
                .filter(WarehouseStock.warehouse_id == wh.id, WarehouseStock.item_id == it.id)
                .first()
            )
            if row:
                row.current_qty = q
            else:
                db.add(WarehouseStock(warehouse_id=wh.id, item_id=it.id, current_qty=q))
            updated += 1
            batch.bump()

    return updated


def seed_quality(db: Session, batch: CommitBatcher, rng: random.Random) -> int:
    qitems = db.query(QualityVisitItem).filter(QualityVisitItem.is_active.is_(True)).all()
    if not qitems:
        return 0

    added = 0
    branches = db.query(Branch).filter(Branch.is_deleted.is_(False)).all()
    visitor_id = 1
    for br in branches:
        for m in (1, 2, 3, 4):
            vd = date(2026, m, 10 if m < 4 else min(10, DATE_END.day))
            if vd > DATE_END:
                continue
            exists = (
                db.query(QualityVisit)
                .filter(
                    QualityVisit.branch_id == br.id,
                    QualityVisit.visit_date == vd,
                    QualityVisit.is_deleted.is_(False),
                )
                .first()
            )
            if exists:
                continue

            comp = _d(rng.uniform(70, 100))
            v = QualityVisit(
                branch_id=br.id,
                visitor_id=visitor_id,
                visit_date=vd,
                status=QualityVisitStatus.closed,
                compliance_pct=comp,
                closed_at=datetime.utcnow(),
                created_by=visitor_id,
            )
            db.add(v)
            db.flush()

            for qi in qitems:
                r = rng.random()
                if r < 0.8:
                    st = QualityResponseStatus.yes
                elif r < 0.9:
                    st = QualityResponseStatus.no
                else:
                    st = QualityResponseStatus.na
                db.add(QualityVisitResponse(visit_id=v.id, item_id=qi.id, status=st))

            added += 1
            batch.bump()

    return added


def seed_training(db: Session, batch: CommitBatcher, rng: random.Random) -> int:
    tpl = db.query(TrainingTemplate).filter(TrainingTemplate.is_active.is_(True)).first()
    if not tpl:
        return 0

    t_items = (
        db.query(TrainingTemplateItem)
        .join(TrainingTemplateSection, TrainingTemplateItem.section_id == TrainingTemplateSection.id)
        .filter(TrainingTemplateSection.template_id == tpl.id, TrainingTemplateItem.is_active.is_(True))
        .order_by(TrainingTemplateItem.id)
        .all()
    )
    if not t_items:
        return 0

    added = 0
    branches = db.query(Branch).filter(Branch.is_deleted.is_(False)).all()
    trainer_id = 1

    for br in branches:
        trainee_id = pick_trainee_id(db, br.id)
        if not trainee_id:
            continue

        slots = [(date(2026, 1, 18), AssessmentStatus.certified), (date(2026, 3, 18), AssessmentStatus.approved)]
        for ad, st in slots:
            if ad > DATE_END:
                continue
            exists = (
                db.query(TrainingAssessment)
                .filter(
                    TrainingAssessment.branch_id == br.id,
                    TrainingAssessment.assessment_date == ad,
                    TrainingAssessment.template_id == tpl.id,
                )
                .first()
            )
            if exists:
                continue

            scores = [rng.randint(3, 5) for _ in t_items]
            overall = sum(scores) / len(scores)
            ov_dec = _d(overall)
            if overall >= 3.5:
                ver = AssessmentVerdict.passed
            elif overall >= 2.5:
                ver = AssessmentVerdict.conditional
            else:
                ver = AssessmentVerdict.failed

            ta = TrainingAssessment(
                template_id=tpl.id,
                trainee_id=trainee_id,
                trainer_id=trainer_id,
                branch_id=br.id,
                assessment_date=ad,
                status=st,
                overall_score=ov_dec,
                verdict=ver,
            )
            if st == AssessmentStatus.approved:
                ta.approved_by = trainer_id
                ta.approved_at = datetime.utcnow()

            db.add(ta)
            db.flush()

            for ti, sc in zip(t_items, scores):
                db.add(
                    TrainingAssessmentItem(
                        assessment_id=ta.id,
                        item_id=ti.id,
                        score=sc,
                    )
                )

            added += 1
            batch.bump()

    return added


def seed_delivery_feb_apr(db: Session, batch: CommitBatcher) -> int:
    """ينسخ نمط يناير 2026 مع نمو ~5% شهرياً للأشهر الناقصة."""
    jan_rows = db.query(DeliveryRecord).filter(DeliveryRecord.year == 2026, DeliveryRecord.month == 1).all()
    if not jan_rows:
        return 0

    added = 0
    for target_month in (2, 3, 4):
        growth = Decimal("1.05") ** (target_month - 1)
        for row in jan_rows:
            dup = (
                db.query(DeliveryRecord)
                .filter(
                    DeliveryRecord.year == 2026,
                    DeliveryRecord.month == target_month,
                    DeliveryRecord.brand_id == row.brand_id,
                    DeliveryRecord.app_id == row.app_id,
                    DeliveryRecord.raw_branch_name == row.raw_branch_name,
                )
                .first()
            )
            if dup:
                continue
            new_orders = max(0, int(round(float(row.orders or 0) * float(growth))))
            new_rev = _d(float(row.revenue or 0) * float(growth))
            new_aov = _d(float(new_rev) / new_orders) if new_orders else row.aov
            rec = DeliveryRecord(
                year=2026,
                month=target_month,
                brand_id=row.brand_id,
                branch_id=row.branch_id,
                app_id=row.app_id,
                orders=new_orders,
                revenue=new_rev,
                aov=new_aov,
                raw_branch_name=row.raw_branch_name,
                raw_brand_name=row.raw_brand_name,
                is_outlier=row.is_outlier,
                import_batch="seed_4months",
            )
            db.add(rec)
            added += 1
            batch.bump()

    return added


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    rng = random.Random(42)
    notes: list[str] = []

    db = SessionLocal()
    counts = {
        "inventory": 0,
        "orders": 0,
        "stock_rows": 0,
        "stock_tx": 0,
        "quality": 0,
        "training": 0,
        "delivery": 0,
    }

    try:
        batch0 = CommitBatcher(db)
        try:
            ensure_demo_items(db, batch0, notes)
            batch0.flush()
            db.commit()
        except Exception as e:
            db.rollback()
            notes.append(f"أصناف تجريبية: {e}\n{traceback.format_exc()}")

        try:
            b = CommitBatcher(db)
            counts["inventory"] = seed_daily_inventory(db, b, rng)
            b.flush()
            db.commit()
        except Exception as e:
            db.rollback()
            notes.append(f"جرد يومي: {e}\n{traceback.format_exc()}")

        try:
            b = CommitBatcher(db)
            counts["orders"], counts["stock_tx"] = seed_replenishment_and_stock_tx(db, b, rng)
            b.flush()
            db.commit()
        except Exception as e:
            db.rollback()
            notes.append(f"طلبيات/معاملات: {e}\n{traceback.format_exc()}")

        try:
            b = CommitBatcher(db)
            counts["stock_rows"] = upsert_branch_warehouse_stock(db, b, rng)
            b.flush()
            db.commit()
        except Exception as e:
            db.rollback()
            notes.append(f"مخزون: {e}\n{traceback.format_exc()}")

        try:
            b = CommitBatcher(db)
            counts["quality"] = seed_quality(db, b, rng)
            b.flush()
            db.commit()
        except Exception as e:
            db.rollback()
            notes.append(f"جودة: {e}\n{traceback.format_exc()}")

        try:
            b = CommitBatcher(db)
            counts["training"] = seed_training(db, b, rng)
            b.flush()
            db.commit()
        except Exception as e:
            db.rollback()
            notes.append(f"تدريب: {e}\n{traceback.format_exc()}")

        try:
            b = CommitBatcher(db)
            counts["delivery"] = seed_delivery_feb_apr(db, b)
            b.flush()
            db.commit()
        except Exception as e:
            db.rollback()
            notes.append(f"توصيل: {e}\n{traceback.format_exc()}")

    finally:
        db.close()

    print()
    print(f"✅ تم إضافة {counts['inventory']} جرد يومي")
    print(f"✅ تم إضافة {counts['orders']} طلبية تجديد")
    print(f"✅ تم تحديث {counts['stock_rows']} صف مخزون (فرع + مستودع)")
    print(f"✅ تم إضافة {counts['stock_tx']} معاملة مخزون")
    print(f"✅ تم إضافة {counts['quality']} زيارة جودة")
    print(f"✅ تم إضافة {counts['training']} تقييم تدريبي")
    print(f"✅ تم إضافة {counts['delivery']} سجل توصيل")
    if notes:
        print("\n── ملاحظات / أخطاء جزئية ──")
        for n in notes:
            print(n)


if __name__ == "__main__":
    main()
