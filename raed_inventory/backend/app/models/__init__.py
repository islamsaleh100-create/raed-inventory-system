"""
All database models for Raed Inventory System
"""
import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, Float, DateTime, Date,
    ForeignKey, Text, Enum as SAEnum, UniqueConstraint, Index, Numeric, Table
)
from sqlalchemy.orm import relationship
from app.database import Base


# ─────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────

class UserStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    suspended = "suspended"


class RoleName(str, enum.Enum):
    super_admin = "super_admin"
    admin = "admin"
    internal_auditor = "internal_auditor"
    branch_user = "branch_user"
    branch_manager = "branch_manager"
    warehouse_user = "warehouse_user"
    warehouse_manager = "warehouse_manager"
    operations_manager = "operations_manager"
    # Quality & Training
    quality_visitor = "quality_visitor"
    quality_manager = "quality_manager"
    trainer = "trainer"
    area_manager = "area_manager"
    evaluator = "evaluator"
    hr_manager = "hr_manager"
    # Commercial / Delivery Analytics
    sales_manager = "sales_manager"
    # Supply Chain V1 Phase 2
    kitchen_manager = "kitchen_manager"  # legacy value only; production access is section-assignment based
    kitchen_section_manager = "kitchen_section_manager"
    delivery_user = "delivery_user"


class InventoryStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    pending_approval = "pending_approval"   # alias: submitted to manager, waiting review
    approved = "approved"
    rejected = "rejected"


class OrderStatus(str, enum.Enum):
    draft = "draft"
    system_generated = "system_generated"
    branch_reviewed = "branch_reviewed"
    area_manager_review = "area_manager_review"
    submitted_to_warehouse = "submitted_to_warehouse"
    under_review = "under_review"
    approved = "approved"
    partially_approved = "partially_approved"
    rejected = "rejected"
    picking = "picking"
    dispatched = "dispatched"
    received = "received"
    closed = "closed"
    cancelled = "cancelled"


class OrderType(str, enum.Enum):
    auto_replenishment = "auto_replenishment"
    exceptional = "exceptional"
    daily_order = "daily_order"
    inter_branch = "inter_branch"  # تحويل بين فرعين (source → destination)


class TransactionType(str, enum.Enum):
    opening_balance = "opening_balance"
    inventory_adjustment = "inventory_adjustment"
    replenishment_request = "replenishment_request"
    warehouse_issue = "warehouse_issue"
    warehouse_dispatch = "warehouse_dispatch"
    branch_receipt = "branch_receipt"
    transfer = "transfer"
    wastage = "wastage"
    manual_adjustment = "manual_adjustment"
    adjustment_in = "adjustment_in"
    adjustment_out = "adjustment_out"


class AvgConsumptionMode(str, enum.Enum):
    last_7_days = "last_7_days"
    last_14_days = "last_14_days"
    last_30_days = "last_30_days"


class ItemType(str, enum.Enum):
    raw_material = "raw_material"
    packaging = "packaging"
    consumable = "consumable"
    finished_good = "finished_good"


class StorageType(str, enum.Enum):
    ambient = "ambient"
    chilled = "chilled"
    frozen = "frozen"


class SupplySourceType(str, enum.Enum):
    WAREHOUSE = "WAREHOUSE"
    KITCHEN = "KITCHEN"
    BOTH = "BOTH"
    NOT_REQUESTABLE = "NOT_REQUESTABLE"


class SupplyDefaultSource(str, enum.Enum):
    WAREHOUSE = "WAREHOUSE"
    KITCHEN = "KITCHEN"


class BranchRequestStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    AREA_APPROVED = "AREA_APPROVED"
    AREA_REJECTED = "AREA_REJECTED"
    SPLIT = "SPLIT"
    IN_EXECUTION = "IN_EXECUTION"
    DELIVERED = "DELIVERED"


class BranchRequestLineStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SPLIT_TO_WAREHOUSE = "SPLIT_TO_WAREHOUSE"
    SPLIT_TO_PRODUCTION = "SPLIT_TO_PRODUCTION"
    IN_PRODUCTION = "IN_PRODUCTION"
    READY_IN_WAREHOUSE = "READY_IN_WAREHOUSE"
    PARTIAL_WAREHOUSE = "PARTIAL_WAREHOUSE"
    DELIVERED = "DELIVERED"


class ProductionOrderStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING_FOR_MATERIALS = "WAITING_FOR_MATERIALS"
    PARTIAL_READY = "PARTIAL_READY"
    READY = "READY"
    SENT_TO_WAREHOUSE = "SENT_TO_WAREHOUSE"


class KitchenMaterialRequestStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    ISSUED = "ISSUED"
    REJECTED = "REJECTED"


class WarehouseLineSourceType(str, enum.Enum):
    BRANCH_REQUEST = "BRANCH_REQUEST"
    KITCHEN_OUTPUT = "KITCHEN_OUTPUT"
    KITCHEN_MATERIAL_REQUEST = "KITCHEN_MATERIAL_REQUEST"


class WarehouseLineStatus(str, enum.Enum):
    PENDING = "PENDING"
    AVAILABLE = "AVAILABLE"
    PARTIAL = "PARTIAL"
    BACKORDER = "BACKORDER"
    READY_FOR_DISPATCH = "READY_FOR_DISPATCH"
    DELIVERED = "DELIVERED"


class DeliveryOrderStatus(str, enum.Enum):
    READY = "READY"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    PARTIAL_DELIVERED = "PARTIAL_DELIVERED"
    DELIVERED = "DELIVERED"


class DeliveryOrderLineStatus(str, enum.Enum):
    READY = "READY"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"
    PARTIAL_DELIVERED = "PARTIAL_DELIVERED"


class EvaluationType(str, enum.Enum):
    BRANCH = "BRANCH"
    EMPLOYEE = "EMPLOYEE"
    STORE_VISIT = "STORE_VISIT"
    MANAGER = "MANAGER"
    ROLE_SPECIFIC = "ROLE_SPECIFIC"


class EvaluationTargetMode(str, enum.Enum):
    BRANCH = "BRANCH"
    EMPLOYEE = "EMPLOYEE"
    NONE = "NONE"


class EvaluationTemplateVersionStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class EvaluationStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    REVIEWED = "REVIEWED"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class EvaluationActionPlanStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class EvaluationFinalRating(str, enum.Enum):
    POOR = "POOR"
    NEEDS_IMPROVEMENT = "NEEDS_IMPROVEMENT"
    GOOD = "GOOD"
    EXCELLENT = "EXCELLENT"


# ─────────────────────────────────────────────
# AUTH & USERS
# ─────────────────────────────────────────────

class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True)
    name = Column(SAEnum(RoleName), unique=True, nullable=False)
    display_name = Column(String(100), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    user_roles = relationship("UserRole", back_populates="role")
    role_permissions = relationship("RolePermission", back_populates="role")


class Permission(Base):
    __tablename__ = "permissions"
    id = Column(Integer, primary_key=True)
    code = Column(String(100), unique=True, nullable=False)
    module = Column(String(50), nullable=False)
    action = Column(String(50), nullable=False)
    description = Column(Text)

    role_permissions = relationship("RolePermission", back_populates="permission")


class RolePermission(Base):
    __tablename__ = "role_permissions"
    id = Column(Integer, primary_key=True)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    permission_id = Column(Integer, ForeignKey("permissions.id"), nullable=False)
    __table_args__ = (UniqueConstraint("role_id", "permission_id"),)

    role = relationship("Role", back_populates="role_permissions")
    permission = relationship("Permission", back_populates="role_permissions")


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(150), unique=True, nullable=False)
    full_name = Column(String(150), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    status = Column(SAEnum(UserStatus), default=UserStatus.active)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=True)
    phone = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    is_deleted = Column(Boolean, default=False)

    user_roles = relationship("UserRole", back_populates="user")
    branch = relationship("Branch", foreign_keys=[branch_id])
    warehouse = relationship("Warehouse", foreign_keys=[warehouse_id])


class UserRole(Base):
    __tablename__ = "user_roles"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    __table_args__ = (UniqueConstraint("user_id", "role_id"),)

    user = relationship("User", back_populates="user_roles")
    role = relationship("Role", back_populates="user_roles")


# ─────────────────────────────────────────────
# MASTER DATA
# ─────────────────────────────────────────────

class Warehouse(Base):
    __tablename__ = "warehouses"
    id = Column(Integer, primary_key=True)
    warehouse_code = Column(String(20), unique=True, nullable=False)
    warehouse_name = Column(String(150), nullable=False)
    location = Column(String(200))
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_deleted = Column(Boolean, default=False)

    branches = relationship("Branch", back_populates="warehouse")
    warehouse_stock = relationship("WarehouseStock", back_populates="warehouse")


class Branch(Base):
    __tablename__ = "branches"
    id = Column(Integer, primary_key=True)
    branch_code = Column(String(20), unique=True, nullable=False)
    branch_name = Column(String(150), nullable=False)
    city = Column(String(100))
    area = Column(String(100))
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_deleted = Column(Boolean, default=False)

    warehouse = relationship("Warehouse", back_populates="branches")
    branch_stock = relationship("BranchStock", back_populates="branch")
    daily_inventories = relationship("DailyInventory", back_populates="branch")
    branch_brands = relationship("BranchBrand", back_populates="branch", cascade="all, delete-orphan")
    branch_employees = relationship("BranchEmployee", back_populates="branch", cascade="all, delete-orphan")
    branch_requests = relationship("BranchRequest", back_populates="branch")
    # Two FKs from replenishment_orders → branches (branch_id + destination_branch_id); disambiguate.
    replenishment_orders = relationship(
        "ReplenishmentOrder",
        back_populates="branch",
        foreign_keys="ReplenishmentOrder.branch_id",
    )


class ItemCategory(Base):
    __tablename__ = "item_categories"
    id = Column(Integer, primary_key=True)
    code = Column(String(20), unique=True, nullable=False)
    name_ar = Column(String(100), nullable=False)
    name_en = Column(String(100), nullable=False)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    items = relationship("Item", back_populates="category")


class UnitOfMeasure(Base):
    __tablename__ = "units"
    id = Column(Integer, primary_key=True)
    code = Column(String(20), unique=True, nullable=False)
    name_ar = Column(String(50), nullable=False)
    name_en = Column(String(50), nullable=False)
    active = Column(Boolean, default=True)

    items = relationship("Item", foreign_keys="Item.unit_id", back_populates="unit")


class Brand(Base):
    __tablename__ = "brands"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    branch_brands = relationship("BranchBrand", back_populates="brand", cascade="all, delete-orphan")
    item_brands = relationship("ItemBrand", back_populates="brand", cascade="all, delete-orphan")
    area_manager_assignments = relationship("AreaManagerAssignment", back_populates="brand")


class BranchBrand(Base):
    __tablename__ = "branch_brands"
    id = Column(Integer, primary_key=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    __table_args__ = (UniqueConstraint("branch_id", "brand_id", name="uq_branch_brand"),)

    branch = relationship("Branch", back_populates="branch_brands")
    brand = relationship("Brand", back_populates="branch_brands")


class BranchEmployee(Base):
    __tablename__ = "branch_employees"
    id = Column(Integer, primary_key=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False, index=True)
    full_name = Column(String(150), nullable=False)
    job_title = Column(String(120), nullable=False)
    work_number = Column(String(50), nullable=False, unique=True)
    phone = Column(String(30), nullable=True)
    active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    branch = relationship("Branch", back_populates="branch_employees")


class AreaManagerAssignment(Base):
    __tablename__ = "area_manager_assignments"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    city = Column(String(100), nullable=False)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    __table_args__ = (
        Index(
            "uq_area_manager_active_assignment",
            "user_id", "city", "brand_id",
            unique=True,
            sqlite_where=active == True,
            postgresql_where=active == True,
        ),
    )

    user = relationship("User")
    brand = relationship("Brand", back_populates="area_manager_assignments")


# Links blueprint-style Kitchen sites (per city) to shared KitchenSection master rows.
kitchen_kitchen_sections = Table(
    "kitchen_kitchen_sections",
    Base.metadata,
    Column("kitchen_id", Integer, ForeignKey("kitchens.id", ondelete="CASCADE"), primary_key=True),
    Column("kitchen_section_id", Integer, ForeignKey("kitchen_sections.id", ondelete="CASCADE"), primary_key=True),
)


class Kitchen(Base):
    """First-class kitchen site (name + city). Sections attach via M2M — items still use global section ids."""

    __tablename__ = "kitchens"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    city = Column(String(100), nullable=False, index=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    sections = relationship(
        "KitchenSection",
        secondary=kitchen_kitchen_sections,
        back_populates="kitchens",
    )

    @property
    def section_ids(self) -> list[int]:
        return [s.id for s in (self.sections or [])]


class KitchenSection(Base):
    __tablename__ = "kitchen_sections"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    items = relationship("Item", back_populates="kitchen_section")
    assignments = relationship("KitchenSectionAssignment", back_populates="kitchen_section")
    kitchens = relationship(
        "Kitchen",
        secondary=kitchen_kitchen_sections,
        back_populates="sections",
    )

    @property
    def kitchen_ids(self) -> list[int]:
        return [k.id for k in (self.kitchens or [])]


class KitchenSectionAssignment(Base):
    __tablename__ = "kitchen_section_assignments"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    kitchen_section_id = Column(Integer, ForeignKey("kitchen_sections.id"), nullable=False)
    # When set, production orders for this section are visible only if destination_branch.city matches (case-insensitive).
    # NULL = legacy/global scope (all cities) for that section.
    service_city = Column(String(100), nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    __table_args__ = (
        Index(
            "uq_kitchen_section_active_assignment",
            "user_id", "kitchen_section_id",
            unique=True,
            sqlite_where=active == True,
            postgresql_where=active == True,
        ),
    )

    user = relationship("User")
    kitchen_section = relationship("KitchenSection", back_populates="assignments")


class ItemBrand(Base):
    __tablename__ = "item_brands"
    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False)
    __table_args__ = (UniqueConstraint("item_id", "brand_id", name="uq_item_brand"),)

    item = relationship("Item", back_populates="item_brands")
    brand = relationship("Brand", back_populates="item_brands")


class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True)
    item_code = Column(String(30), unique=True, nullable=False, index=True)
    item_name_ar = Column(String(200), nullable=False)
    item_name_en = Column(String(200), nullable=False)
    category_id = Column(Integer, ForeignKey("item_categories.id"), nullable=False)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False)
    item_type = Column(SAEnum(ItemType), default=ItemType.raw_material, nullable=False)
    storage_type = Column(SAEnum(StorageType), default=StorageType.ambient, nullable=False)
    purchase_unit_id = Column(Integer, ForeignKey("units.id"), nullable=True)
    supply_unit_id = Column(Integer, ForeignKey("units.id"), nullable=True)
    conversion_ratio = Column(Numeric(12, 4), default=1)
    branch_requestable = Column(Boolean, default=True)
    visible_in_branch_ui = Column(Boolean, default=True, nullable=False)
    active = Column(Boolean, default=True)
    min_qty = Column(Numeric(10, 3), default=0)
    max_qty = Column(Numeric(10, 3), default=0)
    reorder_point = Column(Numeric(10, 3), default=0)
    safety_stock = Column(Numeric(10, 3), default=0)
    lead_time_days = Column(Integer, default=1)
    shelf_life_days = Column(Integer, default=0)
    average_consumption_mode = Column(SAEnum(AvgConsumptionMode), default=AvgConsumptionMode.last_7_days)
    critical_item = Column(Boolean, default=False)
    source_type = Column(SAEnum(SupplySourceType), default=SupplySourceType.WAREHOUSE, nullable=False)
    default_source = Column(SAEnum(SupplyDefaultSource), default=SupplyDefaultSource.WAREHOUSE, nullable=False)
    kitchen_section_id = Column(Integer, ForeignKey("kitchen_sections.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_deleted = Column(Boolean, default=False)

    category = relationship("ItemCategory", back_populates="items")
    unit = relationship("UnitOfMeasure", foreign_keys=[unit_id], back_populates="items")
    purchase_unit = relationship("UnitOfMeasure", foreign_keys=[purchase_unit_id])
    supply_unit = relationship("UnitOfMeasure", foreign_keys=[supply_unit_id])
    branch_stock = relationship("BranchStock", back_populates="item")
    warehouse_stock = relationship("WarehouseStock", back_populates="item")
    kitchen_section = relationship("KitchenSection", back_populates="items")
    item_brands = relationship("ItemBrand", back_populates="item", cascade="all, delete-orphan")


class BranchRequest(Base):
    __tablename__ = "branch_requests"
    id = Column(Integer, primary_key=True)
    request_no = Column(String(40), unique=True, nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False, index=True)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False, index=True)
    brand_name_snapshot = Column(String(100), nullable=True)
    status = Column(SAEnum(BranchRequestStatus), default=BranchRequestStatus.DRAFT, nullable=False, index=True)
    priority = Column(String(30), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    submitted_at = Column(DateTime, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    rejected_at = Column(DateTime, nullable=True)
    rejected_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    rejection_note = Column(Text, nullable=True)
    approval_note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    branch = relationship("Branch", back_populates="branch_requests")
    brand = relationship("Brand")
    creator = relationship("User", foreign_keys=[created_by])
    approver = relationship("User", foreign_keys=[approved_by])
    rejector = relationship("User", foreign_keys=[rejected_by])
    lines = relationship("BranchRequestLine", back_populates="request", cascade="all, delete-orphan")


class BranchRequestLine(Base):
    __tablename__ = "branch_request_lines"
    id = Column(Integer, primary_key=True)
    request_id = Column(Integer, ForeignKey("branch_requests.id"), nullable=False, index=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    item_name_ar_snapshot = Column(String(200), nullable=True)
    item_name_en_snapshot = Column(String(200), nullable=True)
    item_code_snapshot = Column(String(30), nullable=True)
    unit_code_snapshot = Column(String(20), nullable=True)
    qty_requested = Column(Numeric(10, 3), nullable=False)
    qty_approved = Column(Numeric(10, 3), nullable=True)
    source_type = Column(SAEnum(SupplySourceType), nullable=False)
    resolved_source_type = Column(SAEnum(SupplyDefaultSource), nullable=True)
    status = Column(SAEnum(BranchRequestLineStatus), default=BranchRequestLineStatus.DRAFT, nullable=False)
    approval_note = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    request = relationship("BranchRequest", back_populates="lines")
    item = relationship("Item")


class ProductionOrder(Base):
    __tablename__ = "production_orders"
    id = Column(Integer, primary_key=True)
    source_request_id = Column(Integer, ForeignKey("branch_requests.id"), nullable=False, index=True)
    source_request_line_id = Column(Integer, ForeignKey("branch_request_lines.id"), nullable=False, unique=True)
    destination_branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False)
    kitchen_section_id = Column(Integer, ForeignKey("kitchen_sections.id"), nullable=False)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    qty_requested = Column(Numeric(10, 3), nullable=False)
    qty_ready = Column(Numeric(10, 3), default=0, nullable=False)
    qty_sent_to_warehouse = Column(Numeric(10, 3), default=0, nullable=False)
    status = Column(SAEnum(ProductionOrderStatus), default=ProductionOrderStatus.PENDING, nullable=False, index=True)
    priority = Column(String(30), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    source_request = relationship("BranchRequest")
    source_request_line = relationship("BranchRequestLine")
    destination_branch = relationship("Branch")
    brand = relationship("Brand")
    kitchen_section = relationship("KitchenSection")
    item = relationship("Item")
    material_requests = relationship("KitchenMaterialRequest", back_populates="production_order", cascade="all, delete-orphan")


class KitchenMaterialRequest(Base):
    __tablename__ = "kitchen_material_requests"
    id = Column(Integer, primary_key=True)
    production_order_id = Column(Integer, ForeignKey("production_orders.id"), nullable=False, index=True)
    kitchen_section_id = Column(Integer, ForeignKey("kitchen_sections.id"), nullable=False)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    qty = Column(Numeric(10, 3), nullable=False)
    status = Column(SAEnum(KitchenMaterialRequestStatus), default=KitchenMaterialRequestStatus.PENDING, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    production_order = relationship("ProductionOrder", back_populates="material_requests")
    kitchen_section = relationship("KitchenSection")
    item = relationship("Item")


class WarehouseLine(Base):
    __tablename__ = "warehouse_lines"
    id = Column(Integer, primary_key=True)
    source_request_id = Column(Integer, ForeignKey("branch_requests.id"), nullable=True, index=True)
    source_request_line_id = Column(Integer, ForeignKey("branch_request_lines.id"), nullable=True, index=True)
    source_type = Column(SAEnum(WarehouseLineSourceType), nullable=False)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False)
    kitchen_section_id = Column(Integer, ForeignKey("kitchen_sections.id"), nullable=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    requested_qty = Column(Numeric(10, 3), nullable=False)
    issued_qty = Column(Numeric(10, 3), default=0, nullable=False)
    pending_qty = Column(Numeric(10, 3), nullable=False)
    status = Column(SAEnum(WarehouseLineStatus), default=WarehouseLineStatus.PENDING, nullable=False, index=True)
    delay_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    __table_args__ = (
        UniqueConstraint("source_request_line_id", "source_type", name="uq_warehouse_line_request_line_source"),
    )

    source_request = relationship("BranchRequest")
    source_request_line = relationship("BranchRequestLine")
    branch = relationship("Branch")
    brand = relationship("Brand")
    kitchen_section = relationship("KitchenSection")
    item = relationship("Item")


class DeliveryOrder(Base):
    __tablename__ = "delivery_orders"
    id = Column(Integer, primary_key=True)
    source_request_id = Column(Integer, ForeignKey("branch_requests.id"), nullable=True, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False, index=True)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False, index=True)
    status = Column(SAEnum(DeliveryOrderStatus), default=DeliveryOrderStatus.READY, nullable=False, index=True)
    ready_at = Column(DateTime, nullable=True)
    out_for_delivery_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    delivered_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    receiver_name = Column(String(150), nullable=True)
    delivery_note = Column(Text, nullable=True)

    source_request = relationship("BranchRequest")
    branch = relationship("Branch")
    brand = relationship("Brand")
    creator = relationship("User", foreign_keys=[created_by])
    deliverer = relationship("User", foreign_keys=[delivered_by])
    lines = relationship("DeliveryOrderLine", back_populates="delivery_order", cascade="all, delete-orphan")


class DeliveryOrderLine(Base):
    __tablename__ = "delivery_order_lines"
    id = Column(Integer, primary_key=True)
    delivery_order_id = Column(Integer, ForeignKey("delivery_orders.id"), nullable=False, index=True)
    warehouse_line_id = Column(Integer, ForeignKey("warehouse_lines.id"), nullable=False, index=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    qty_dispatched = Column(Numeric(10, 3), nullable=False)
    qty_delivered = Column(Numeric(10, 3), default=0, nullable=False)
    shortage_qty = Column(Numeric(10, 3), default=0, nullable=False)
    status = Column(SAEnum(DeliveryOrderLineStatus), default=DeliveryOrderLineStatus.READY, nullable=False, index=True)
    delivery_note = Column(Text, nullable=True)
    shortage_reason = Column(Text, nullable=True)
    __table_args__ = (
        UniqueConstraint("warehouse_line_id", name="uq_delivery_order_line_warehouse_line"),
    )

    delivery_order = relationship("DeliveryOrder", back_populates="lines")
    warehouse_line = relationship("WarehouseLine")
    item = relationship("Item")


class PurchaseRequestStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"


class Supplier(Base):
    __tablename__ = "suppliers"
    id = Column(Integer, primary_key=True)
    supplier_code = Column(String(30), unique=True, nullable=False, index=True)
    name = Column(String(150), nullable=False)
    contact_name = Column(String(150), nullable=True)
    phone = Column(String(50), nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class PurchaseRequest(Base):
    __tablename__ = "purchase_requests"
    id = Column(Integer, primary_key=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False, index=True)
    requested_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(SAEnum(PurchaseRequestStatus), default=PurchaseRequestStatus.DRAFT, nullable=False, index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    warehouse = relationship("Warehouse")
    requester = relationship("User", foreign_keys=[requested_by])
    lines = relationship("PurchaseRequestLine", back_populates="purchase_request", cascade="all, delete-orphan")


class PurchaseRequestLine(Base):
    __tablename__ = "purchase_request_lines"
    id = Column(Integer, primary_key=True)
    purchase_request_id = Column(Integer, ForeignKey("purchase_requests.id"), nullable=False, index=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    qty_requested = Column(Numeric(10, 3), nullable=False)
    notes = Column(Text, nullable=True)

    purchase_request = relationship("PurchaseRequest", back_populates="lines")
    item = relationship("Item")


class EvaluationTemplate(Base):
    __tablename__ = "evaluation_templates"
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False, index=True)
    evaluation_type = Column(SAEnum(EvaluationType), nullable=False)
    target_mode = Column(SAEnum(EvaluationTargetMode), nullable=False)
    target_role = Column(String(100), nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    brand = relationship("Brand")
    creator = relationship("User")
    versions = relationship("EvaluationTemplateVersion", back_populates="template", cascade="all, delete-orphan")


class EvaluationTemplateVersion(Base):
    __tablename__ = "evaluation_template_versions"
    id = Column(Integer, primary_key=True)
    template_id = Column(Integer, ForeignKey("evaluation_templates.id"), nullable=False, index=True)
    version_no = Column(Integer, nullable=False)
    status = Column(SAEnum(EvaluationTemplateVersionStatus), default=EvaluationTemplateVersionStatus.DRAFT, nullable=False, index=True)
    published_at = Column(DateTime, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    notes = Column(Text, nullable=True)
    __table_args__ = (UniqueConstraint("template_id", "version_no", name="uq_evaluation_template_version_no"),)

    template = relationship("EvaluationTemplate", back_populates="versions")
    creator = relationship("User")
    sections = relationship(
        "EvaluationTemplateSection",
        back_populates="template_version",
        cascade="all, delete-orphan",
        order_by="EvaluationTemplateSection.display_order",
    )


class EvaluationTemplateSection(Base):
    __tablename__ = "evaluation_template_sections"
    id = Column(Integer, primary_key=True)
    template_version_id = Column(Integer, ForeignKey("evaluation_template_versions.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    weight_percent = Column(Numeric(6, 2), nullable=True)
    display_order = Column(Integer, default=1, nullable=False)
    active = Column(Boolean, default=True, nullable=False)

    template_version = relationship("EvaluationTemplateVersion", back_populates="sections")
    questions = relationship(
        "EvaluationTemplateQuestion",
        back_populates="section",
        cascade="all, delete-orphan",
        order_by="EvaluationTemplateQuestion.display_order",
    )


class EvaluationTemplateQuestion(Base):
    __tablename__ = "evaluation_template_questions"
    id = Column(Integer, primary_key=True)
    section_id = Column(Integer, ForeignKey("evaluation_template_sections.id"), nullable=False, index=True)
    question_text_ar = Column(Text, nullable=False)
    question_text_en = Column(Text, nullable=True)
    max_score = Column(Numeric(10, 3), default=5, nullable=False)
    allow_na = Column(Boolean, default=False, nullable=False)
    requires_note_if_low_score = Column(Boolean, default=False, nullable=False)
    low_score_threshold = Column(Numeric(10, 3), default=2, nullable=False)
    requires_photo = Column(Boolean, default=False, nullable=False)
    display_order = Column(Integer, default=1, nullable=False)
    active = Column(Boolean, default=True, nullable=False)

    section = relationship("EvaluationTemplateSection", back_populates="questions")
    answers = relationship("EvaluationAnswer", back_populates="question")


class Evaluation(Base):
    __tablename__ = "evaluations"
    id = Column(Integer, primary_key=True)
    template_id = Column(Integer, ForeignKey("evaluation_templates.id"), nullable=False, index=True)
    template_version_id = Column(Integer, ForeignKey("evaluation_template_versions.id"), nullable=False, index=True)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True, index=True)
    employee_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    evaluation_type = Column(SAEnum(EvaluationType), nullable=False)
    target_mode = Column(SAEnum(EvaluationTargetMode), nullable=False)
    evaluated_role = Column(String(100), nullable=True)
    evaluator_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    evaluation_date = Column(Date, nullable=False)
    status = Column(SAEnum(EvaluationStatus), default=EvaluationStatus.DRAFT, nullable=False, index=True)
    total_score = Column(Numeric(10, 3), nullable=True)
    total_percentage = Column(Numeric(6, 2), nullable=True)
    final_rating = Column(SAEnum(EvaluationFinalRating), nullable=True)
    general_notes = Column(Text, nullable=True)
    low_score_count = Column(Integer, nullable=True)
    action_required_flag = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    submitted_at = Column(DateTime, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    closed_at = Column(DateTime, nullable=True)
    closed_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    template = relationship("EvaluationTemplate")
    template_version = relationship("EvaluationTemplateVersion")
    brand = relationship("Brand")
    branch = relationship("Branch")
    employee = relationship("User", foreign_keys=[employee_id])
    evaluator = relationship("User", foreign_keys=[evaluator_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    closer = relationship("User", foreign_keys=[closed_by])
    answers = relationship("EvaluationAnswer", back_populates="evaluation", cascade="all, delete-orphan")
    attachments = relationship("EvaluationAttachment", back_populates="evaluation", cascade="all, delete-orphan")


class EvaluationAnswer(Base):
    __tablename__ = "evaluation_answers"
    id = Column(Integer, primary_key=True)
    evaluation_id = Column(Integer, ForeignKey("evaluations.id"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("evaluation_template_questions.id"), nullable=False, index=True)
    score = Column(Numeric(10, 3), nullable=True)
    is_na = Column(Boolean, default=False, nullable=False)
    note = Column(Text, nullable=True)
    question_text_snapshot = Column(Text, nullable=False)
    section_name_snapshot = Column(String(200), nullable=False)
    max_score_snapshot = Column(Numeric(10, 3), nullable=False)
    section_weight_snapshot = Column(Numeric(6, 2), nullable=True)
    display_order_snapshot = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    __table_args__ = (UniqueConstraint("evaluation_id", "question_id", name="uq_evaluation_answer_question"),)

    evaluation = relationship("Evaluation", back_populates="answers")
    question = relationship("EvaluationTemplateQuestion", back_populates="answers")
    attachments = relationship("EvaluationAttachment", back_populates="answer")


class EvaluationAttachment(Base):
    __tablename__ = "evaluation_attachments"
    id = Column(Integer, primary_key=True)
    evaluation_id = Column(Integer, ForeignKey("evaluations.id"), nullable=False, index=True)
    answer_id = Column(Integer, ForeignKey("evaluation_answers.id"), nullable=True, index=True)
    storage_disk = Column(String(50), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_name = Column(String(255), nullable=False)
    mime_type = Column(String(100), nullable=False)
    file_size = Column(Integer, nullable=True)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    evaluation = relationship("Evaluation", back_populates="attachments")
    answer = relationship("EvaluationAnswer", back_populates="attachments")
    uploader = relationship("User")


class EvaluationActionPlan(Base):
    __tablename__ = "evaluation_action_plans"
    id = Column(Integer, primary_key=True)
    evaluation_id = Column(Integer, ForeignKey("evaluations.id"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    issue = Column(Text, nullable=False)
    corrective_action = Column(Text, nullable=False)
    responsible_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    due_date = Column(Date, nullable=False)
    status = Column(SAEnum(EvaluationActionPlanStatus), default=EvaluationActionPlanStatus.OPEN, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    closed_at = Column(DateTime, nullable=True)
    closed_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    evaluation = relationship("Evaluation")
    branch = relationship("Branch")
    employee = relationship("User", foreign_keys=[employee_id])
    responsible_user = relationship("User", foreign_keys=[responsible_user_id])
    closer = relationship("User", foreign_keys=[closed_by])


class EvaluationAuditLog(Base):
    __tablename__ = "evaluation_audit_logs"
    id = Column(Integer, primary_key=True)
    evaluation_id = Column(Integer, ForeignKey("evaluations.id"), nullable=True, index=True)
    template_id = Column(Integer, ForeignKey("evaluation_templates.id"), nullable=True, index=True)
    template_version_id = Column(Integer, ForeignKey("evaluation_template_versions.id"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(100), nullable=False, index=True)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    evaluation = relationship("Evaluation")
    template = relationship("EvaluationTemplate")
    template_version = relationship("EvaluationTemplateVersion")
    user = relationship("User")


# ─────────────────────────────────────────────
# STOCK
# ─────────────────────────────────────────────

class BranchStock(Base):
    __tablename__ = "branch_stock"
    id = Column(Integer, primary_key=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    current_qty = Column(Numeric(10, 3), default=0)
    reserved_qty = Column(Numeric(10, 3), default=0)
    in_transit_qty = Column(Numeric(10, 3), default=0)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (UniqueConstraint("branch_id", "item_id"),)

    branch = relationship("Branch", back_populates="branch_stock")
    item = relationship("Item", back_populates="branch_stock")


class WarehouseStock(Base):
    __tablename__ = "warehouse_stock"
    id = Column(Integer, primary_key=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    current_qty = Column(Numeric(10, 3), default=0)
    reserved_qty = Column(Numeric(10, 3), default=0)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (UniqueConstraint("warehouse_id", "item_id"),)

    warehouse = relationship("Warehouse", back_populates="warehouse_stock")
    item = relationship("Item", back_populates="warehouse_stock")


class BranchItemAvailability(Base):
    __tablename__ = "branch_item_availability"
    id = Column(Integer, primary_key=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False, index=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False, index=True)
    active = Column(Boolean, default=True, nullable=False)
    added_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    removed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    __table_args__ = (UniqueConstraint("branch_id", "item_id", name="uq_branch_item_availability"),)

    branch = relationship("Branch")
    item = relationship("Item")
    added_by_user = relationship("User", foreign_keys=[added_by])
    removed_by_user = relationship("User", foreign_keys=[removed_by])


class ItemChangeRequest(Base):
    __tablename__ = "item_change_requests"
    id = Column(Integer, primary_key=True)
    request_no = Column(String(40), unique=True, nullable=False, index=True)
    request_type = Column(String(40), nullable=False, index=True)
    status = Column(String(30), default="pending", nullable=False, index=True)
    target_type = Column(String(30), nullable=False, index=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=True, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=True, index=True)
    proposed_item_name_ar = Column(String(200), nullable=True)
    proposed_item_name_en = Column(String(200), nullable=True)
    proposed_item_code = Column(String(50), nullable=True)
    proposed_unit = Column(String(80), nullable=True)
    proposed_source_type = Column(String(30), nullable=True)
    reason = Column(Text, nullable=True)
    review_note = Column(Text, nullable=True)
    failure_reason = Column(Text, nullable=True)
    requested_by = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    reviewed_at = Column(DateTime, nullable=True)
    executed_at = Column(DateTime, nullable=True)

    warehouse = relationship("Warehouse")
    branch = relationship("Branch")
    item = relationship("Item")
    requester = relationship("User", foreign_keys=[requested_by])
    reviewer = relationship("User", foreign_keys=[reviewed_by])


# ─────────────────────────────────────────────
# DAILY INVENTORY
# ─────────────────────────────────────────────

class DailyInventory(Base):
    __tablename__ = "daily_inventory"
    id = Column(Integer, primary_key=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)
    inventory_date = Column(Date, nullable=False)
    # H9: classify as daily / weekly / monthly — null treated as "daily" for legacy rows
    inventory_type = Column(String(20), default="daily", index=True)
    status = Column(SAEnum(InventoryStatus), default=InventoryStatus.draft)
    submitted_at = Column(DateTime)
    submitted_by = Column(Integer, ForeignKey("users.id"))
    approved_at = Column(DateTime)
    approved_by = Column(Integer, ForeignKey("users.id"))
    rejection_reason = Column(Text)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    __table_args__ = (UniqueConstraint("branch_id", "inventory_date"),)

    branch = relationship("Branch", back_populates="daily_inventories")
    lines = relationship("DailyInventoryLine", back_populates="inventory", cascade="all, delete-orphan")


class DailyInventoryLine(Base):
    __tablename__ = "daily_inventory_lines"
    id = Column(Integer, primary_key=True)
    inventory_id = Column(Integer, ForeignKey("daily_inventory.id"), nullable=False)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    book_qty = Column(Numeric(10, 3), default=0)
    counted_qty = Column(Numeric(10, 3), nullable=False)
    variance_qty = Column(Numeric(10, 3), default=0)
    variance_pct = Column(Numeric(6, 2), default=0)
    variance_status = Column(String(20))  # ok / warning / critical
    below_min_flag = Column(Boolean, default=False)
    out_of_stock_flag = Column(Boolean, default=False)
    variance_reason_id = Column(Integer, ForeignKey("inventory_variance_reasons.id"), nullable=True)
    notes = Column(Text)

    inventory = relationship("DailyInventory", back_populates="lines")
    item = relationship("Item")
    variance_reason = relationship("InventoryVarianceReason")


class InventoryVarianceReason(Base):
    __tablename__ = "inventory_variance_reasons"
    id = Column(Integer, primary_key=True)
    reason_ar = Column(String(200), nullable=False)
    reason_en = Column(String(200), nullable=False)
    active = Column(Boolean, default=True)


class ReceivingVarianceReason(Base):
    __tablename__ = "receiving_variance_reasons"
    id = Column(Integer, primary_key=True)
    reason_ar = Column(String(200), nullable=False)
    reason_en = Column(String(200), nullable=False)
    active = Column(Boolean, default=True)


# ─────────────────────────────────────────────
# REPLENISHMENT ORDERS
# ─────────────────────────────────────────────

class ReplenishmentOrder(Base):
    __tablename__ = "replenishment_orders"
    id = Column(Integer, primary_key=True)
    order_no = Column(String(30), unique=True, nullable=False)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False)
    # For OrderType.inter_branch: branch_id = source, destination_branch_id = target.
    # NULL for all other order types.
    destination_branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True, index=True)
    order_type = Column(SAEnum(OrderType), default=OrderType.auto_replenishment)
    status = Column(SAEnum(OrderStatus), default=OrderStatus.system_generated)
    inventory_id = Column(Integer, ForeignKey("daily_inventory.id"), nullable=True)
    order_date = Column(Date, nullable=False)

    branch_reviewed_at = Column(DateTime)
    branch_reviewed_by = Column(Integer, ForeignKey("users.id"))
    submitted_to_warehouse_at = Column(DateTime)
    wh_reviewed_at = Column(DateTime)
    wh_reviewed_by = Column(Integer, ForeignKey("users.id"))
    wh_approved_at = Column(DateTime)
    wh_approved_by = Column(Integer, ForeignKey("users.id"))
    picking_started_at = Column(DateTime)
    dispatched_at = Column(DateTime)
    dispatched_by = Column(Integer, ForeignKey("users.id"))
    received_at = Column(DateTime)
    closed_at = Column(DateTime)
    cancelled_at = Column(DateTime)
    cancelled_by = Column(Integer, ForeignKey("users.id"))
    cancellation_reason = Column(Text)

    rejection_reason = Column(Text)
    notes = Column(Text)
    dispatch_note_no = Column(String(30))

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"))

    branch = relationship("Branch", back_populates="replenishment_orders", foreign_keys=[branch_id])
    destination_branch = relationship("Branch", foreign_keys=[destination_branch_id])
    warehouse = relationship("Warehouse")
    lines = relationship("ReplenishmentOrderLine", back_populates="order", cascade="all, delete-orphan")
    inventory = relationship("DailyInventory")


class ReplenishmentOrderLine(Base):
    __tablename__ = "replenishment_order_lines"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("replenishment_orders.id"), nullable=False)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)

    suggested_qty = Column(Numeric(10, 3), default=0)
    branch_requested_qty = Column(Numeric(10, 3), default=0)
    wh_approved_qty = Column(Numeric(10, 3), default=0)
    picked_qty = Column(Numeric(10, 3), default=0)
    dispatched_qty = Column(Numeric(10, 3), default=0)
    received_qty = Column(Numeric(10, 3), default=0)
    damaged_qty = Column(Numeric(10, 3), default=0)
    missing_qty = Column(Numeric(10, 3), default=0)

    shortage_flag = Column(Boolean, default=False)
    shortage_reason = Column(Text)
    rejection_reason = Column(Text)
    receiving_variance_reason_id = Column(Integer, ForeignKey("receiving_variance_reasons.id"), nullable=True)

    line_status = Column(String(30), default="pending")  # pending/approved/rejected/partial/dispatched/received
    notes = Column(Text)

    order = relationship("ReplenishmentOrder", back_populates="lines")
    item = relationship("Item")
    receiving_variance_reason = relationship("ReceivingVarianceReason")


# ─────────────────────────────────────────────
# STOCK TRANSACTIONS
# ─────────────────────────────────────────────

class StockTransaction(Base):
    __tablename__ = "stock_transactions"
    id = Column(Integer, primary_key=True)
    transaction_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    transaction_type = Column(SAEnum(TransactionType), nullable=False)
    source_type = Column(String(50))   # branch / warehouse
    source_id = Column(Integer)
    destination_type = Column(String(50))  # branch / warehouse
    destination_id = Column(Integer)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    qty = Column(Numeric(10, 3), nullable=False)
    reference_no = Column(String(50))
    notes = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    item = relationship("Item")


# ─────────────────────────────────────────────
# SYSTEM SETTINGS & AUDIT
# ─────────────────────────────────────────────

class SystemSetting(Base):
    __tablename__ = "system_settings"
    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text, nullable=False)
    description = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(Integer, ForeignKey("users.id"))


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String(100), nullable=False)
    module = Column(String(50))
    entity_type = Column(String(50))
    entity_id = Column(Integer)
    old_values = Column(Text)
    new_values = Column(Text)
    ip_address = Column(String(45))
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditFinding(Base):
    __tablename__ = "audit_findings"

    id = Column(Integer, primary_key=True)
    finding_no = Column(String(40), unique=True, nullable=False, index=True)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(Integer, nullable=False)
    severity = Column(String(20), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    acknowledged_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    response_text = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="open")

    __table_args__ = (
        Index("idx_audit_findings_entity", "entity_type", "entity_id"),
        Index("idx_audit_findings_severity", "severity"),
        Index("idx_audit_findings_status", "status"),
        Index("idx_audit_findings_created_by", "created_by"),
    )


class IdempotencyRequest(Base):
    __tablename__ = "idempotency_requests"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, nullable=False)
    client_request_id = Column(String(100), nullable=False)
    operation_name = Column(String(100), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(String(30), nullable=False, default="pending")
    response_reference_type = Column(String(50), nullable=True)
    response_reference_id = Column(String(100), nullable=True)
    request_hash = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "client_request_id", "operation_name", name="uq_idempotency_request"),
    )


# ─────────────────────────────────────────────
# QUALITY VISIT MODULE
# ─────────────────────────────────────────────

class QualityVisitStatus(str, enum.Enum):
    draft     = "draft"
    submitted = "submitted"
    reviewed  = "reviewed"
    closed    = "closed"


class QualityResponseStatus(str, enum.Enum):
    yes = "yes"
    no  = "no"
    na  = "na"


class QualityItemResponseType(str, enum.Enum):
    """كيف بيتعبى البند: نعم/لا، رقم، أو نص حر"""
    yes_no  = "yes_no"
    numeric = "numeric"
    text    = "text"


class QualityVisitSection(Base):
    __tablename__ = "quality_visit_sections"
    id        = Column(Integer, primary_key=True)
    brand_key = Column(String(32), nullable=True)
    name_ar   = Column(String(100), nullable=False)
    name_en   = Column(String(100), nullable=False)
    order     = Column(Integer, default=0)
    weight    = Column(Numeric(5, 2), default=1.0)
    is_active = Column(Boolean, default=True)

    items = relationship("QualityVisitItem", back_populates="section",
                         order_by="QualityVisitItem.order")


class QualityVisitItem(Base):
    __tablename__ = "quality_visit_items"
    id            = Column(Integer, primary_key=True)
    section_id    = Column(Integer, ForeignKey("quality_visit_sections.id"), nullable=False)
    text_ar       = Column(Text, nullable=False)
    text_en       = Column(Text, nullable=True)
    benchmark_ar  = Column(Text, nullable=True)
    benchmark_en  = Column(Text, nullable=True)
    response_type = Column(String(10), nullable=False, default="yes_no")   # yes_no | numeric | text
    numeric_unit  = Column(String(20), nullable=True)                      # SAR, °C, ppm, count, ...
    order         = Column(Integer, default=0)
    is_active     = Column(Boolean, default=True)

    section = relationship("QualityVisitSection", back_populates="items")


class QualityVisit(Base):
    __tablename__ = "quality_visits"
    id               = Column(Integer, primary_key=True)
    branch_id        = Column(Integer, ForeignKey("branches.id"), nullable=False)
    brand_key        = Column(String(32), nullable=True)
    visitor_id       = Column(Integer, ForeignKey("users.id"), nullable=False)
    branch_in_charge = Column(Integer, ForeignKey("users.id"), nullable=True)
    visit_date       = Column(Date, nullable=False)
    shift            = Column(String(20), nullable=True)
    status           = Column(SAEnum(QualityVisitStatus), default=QualityVisitStatus.draft)
    compliance_pct   = Column(Numeric(5, 2), nullable=True)
    summary_notes    = Column(Text, nullable=True)
    follow_up_date   = Column(Date, nullable=True)
    reviewed_by      = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at      = Column(DateTime, nullable=True)
    closed_at        = Column(DateTime, nullable=True)
    # E8 — e-signatures
    visitor_signature      = Column(String(200), nullable=True)
    visitor_signed_at      = Column(DateTime, nullable=True)
    branch_mgr_signature   = Column(String(200), nullable=True)
    branch_mgr_signed_at   = Column(DateTime, nullable=True)
    tenant_id        = Column(Integer, default=1)
    is_deleted       = Column(Boolean, default=False)
    created_at       = Column(DateTime, default=datetime.utcnow)
    updated_at       = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by       = Column(Integer, ForeignKey("users.id"), nullable=True)

    branch   = relationship("Branch")
    visitor  = relationship("User", foreign_keys=[visitor_id])
    in_charge= relationship("User", foreign_keys=[branch_in_charge])
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    creator  = relationship("User", foreign_keys=[created_by])
    responses= relationship("QualityVisitResponse", back_populates="visit",
                            cascade="all, delete-orphan")
    # I3 — attachments attached directly to the visit (not a specific response)
    visit_attachments = relationship("QualityVisitAttachment",
                            primaryjoin="and_(QualityVisitAttachment.visit_id==QualityVisit.id, "
                                        "QualityVisitAttachment.response_id==None)",
                            back_populates="visit",
                            cascade="all, delete-orphan",
                            foreign_keys="QualityVisitAttachment.visit_id")


class QualityVisitResponse(Base):
    __tablename__ = "quality_visit_responses"
    id                = Column(Integer, primary_key=True)
    visit_id          = Column(Integer, ForeignKey("quality_visits.id"), nullable=False)
    item_id           = Column(Integer, ForeignKey("quality_visit_items.id"), nullable=False)
    status            = Column(SAEnum(QualityResponseStatus), nullable=True)   # for yes_no items
    numeric_value     = Column(Numeric(12, 2), nullable=True)                  # for numeric items
    text_value        = Column(Text, nullable=True)                            # for text items
    notes             = Column(Text, nullable=True)
    corrective_action = Column(Text, nullable=True)
    action_owner      = Column(String(100), nullable=True)
    due_date          = Column(Date, nullable=True)
    is_resolved       = Column(Boolean, default=False)
    # E8 — resolve audit
    resolved_by       = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolved_at       = Column(DateTime, nullable=True)

    visit = relationship("QualityVisit", back_populates="responses")
    item  = relationship("QualityVisitItem")
    resolver = relationship("User", foreign_keys=[resolved_by])
    attachments = relationship(
        "QualityVisitAttachment",
        back_populates="response",
        cascade="all, delete-orphan",
    )


class QualityVisitAttachment(Base):
    """E8 — صور/ملفات مرفقة بإجابة على بند زيارة (للـ NO عادة).
    I3 — الآن يدعم كمان مرفقات على مستوى الزيارة نفسها (response_id نال، visit_id مملوء).
    """
    __tablename__ = "quality_visit_attachments"
    id            = Column(Integer, primary_key=True)
    # Either response_id (item-level) OR visit_id (visit-level) must be set, not both
    response_id   = Column(Integer,
                            ForeignKey("quality_visit_responses.id", ondelete="CASCADE"),
                            nullable=True, index=True)
    visit_id      = Column(Integer,
                            ForeignKey("quality_visits.id", ondelete="CASCADE"),
                            nullable=True, index=True)
    file_path     = Column(String(500), nullable=False)
    original_name = Column(String(255), nullable=True)
    mime_type     = Column(String(100), nullable=True)
    size_bytes    = Column(Integer, nullable=True)
    kind          = Column(String(20), default="photo")   # photo | document
    uploaded_by   = Column(Integer, ForeignKey("users.id"), nullable=True)
    uploaded_at   = Column(DateTime, default=datetime.utcnow, nullable=False)

    response = relationship("QualityVisitResponse", back_populates="attachments")
    visit    = relationship("QualityVisit", back_populates="visit_attachments")
    uploader = relationship("User", foreign_keys=[uploaded_by])


# ─────────────────────────────────────────────
# TRAINING & ASSESSMENT MODULE
# ─────────────────────────────────────────────

class TrainingRoleType(str, enum.Enum):
    branch_employee = "branch_employee"   # موظف الفرع — يقيّمه مدير المنطقة
    branch_manager  = "branch_manager"    # مدير الفرع — يقيّمه مدير المنطقة


class AssessmentStatus(str, enum.Enum):
    draft       = "draft"
    submitted   = "submitted"
    approved    = "approved"
    certified   = "certified"
    needs_reeval= "needs_reeval"


class AssessmentVerdict(str, enum.Enum):
    passed      = "passed"
    conditional = "conditional"
    failed      = "failed"


class TrainingTemplate(Base):
    __tablename__ = "training_templates"
    id        = Column(Integer, primary_key=True)
    role_type = Column(SAEnum(TrainingRoleType), nullable=False)
    name_ar   = Column(String(200), nullable=False)
    name_en   = Column(String(200), nullable=True)
    version   = Column(String(10), default="v1.0")
    is_active = Column(Boolean, default=True)
    created_at= Column(DateTime, default=datetime.utcnow)

    sections = relationship("TrainingTemplateSection", back_populates="template",
                            order_by="TrainingTemplateSection.order")


class TrainingTemplateSection(Base):
    __tablename__ = "training_template_sections"
    id          = Column(Integer, primary_key=True)
    template_id = Column(Integer, ForeignKey("training_templates.id"), nullable=False)
    name_ar     = Column(String(100), nullable=False)
    name_en     = Column(String(100), nullable=True)
    order       = Column(Integer, default=0)
    weight      = Column(Numeric(5, 2), default=1.0)

    template = relationship("TrainingTemplate", back_populates="sections")
    items    = relationship("TrainingTemplateItem", back_populates="section",
                            order_by="TrainingTemplateItem.order")


class TrainingTemplateItem(Base):
    __tablename__ = "training_template_items"
    id           = Column(Integer, primary_key=True)
    section_id   = Column(Integer, ForeignKey("training_template_sections.id"), nullable=False)
    text_ar      = Column(Text, nullable=False)
    text_en      = Column(Text, nullable=True)
    benchmark_ar = Column(Text, nullable=True)
    benchmark_en = Column(Text, nullable=True)
    order        = Column(Integer, default=0)
    is_active    = Column(Boolean, default=True)

    section = relationship("TrainingTemplateSection", back_populates="items")


class TrainingAssessment(Base):
    __tablename__ = "training_assessments"
    id              = Column(Integer, primary_key=True)
    template_id     = Column(Integer, ForeignKey("training_templates.id"), nullable=False)
    trainee_id      = Column(Integer, ForeignKey("users.id"), nullable=False)
    trainer_id      = Column(Integer, ForeignKey("users.id"), nullable=False)
    branch_id       = Column(Integer, ForeignKey("branches.id"), nullable=False)
    assessment_date = Column(Date, nullable=False)
    status          = Column(SAEnum(AssessmentStatus), default=AssessmentStatus.draft)
    overall_score   = Column(Numeric(4, 2), nullable=True)
    verdict         = Column(SAEnum(AssessmentVerdict), nullable=True)
    approved_by     = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at     = Column(DateTime, nullable=True)
    re_eval_date    = Column(Date, nullable=True)
    rejection_reason= Column(Text, nullable=True)   # set when approver rejects → draft
    # E8 — e-signatures
    evaluator_signature  = Column(String(200), nullable=True)
    evaluator_signed_at  = Column(DateTime, nullable=True)
    approver_signature   = Column(String(200), nullable=True)
    approver_signed_at   = Column(DateTime, nullable=True)
    tenant_id       = Column(Integer, default=1)
    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    template = relationship("TrainingTemplate")
    trainee  = relationship("User", foreign_keys=[trainee_id])
    trainer  = relationship("User", foreign_keys=[trainer_id])
    branch   = relationship("Branch")
    approver = relationship("User", foreign_keys=[approved_by])
    items    = relationship("TrainingAssessmentItem", back_populates="assessment",
                            cascade="all, delete-orphan")
    dev_plan = relationship("TrainingDevelopmentPlan", back_populates="assessment",
                            uselist=False, cascade="all, delete-orphan")


class TrainingAssessmentItem(Base):
    __tablename__ = "training_assessment_items"
    id            = Column(Integer, primary_key=True)
    assessment_id = Column(Integer, ForeignKey("training_assessments.id"), nullable=False)
    item_id       = Column(Integer, ForeignKey("training_template_items.id"), nullable=False)
    score         = Column(Integer, nullable=True)   # 1-5
    notes         = Column(Text, nullable=True)

    assessment = relationship("TrainingAssessment", back_populates="items")
    item       = relationship("TrainingTemplateItem")


class TrainingDevelopmentPlan(Base):
    __tablename__ = "training_development_plans"
    id                    = Column(Integer, primary_key=True)
    assessment_id         = Column(Integer, ForeignKey("training_assessments.id"),
                                   nullable=False, unique=True)
    strengths             = Column(Text, nullable=True)
    areas_for_improvement = Column(Text, nullable=True)
    required_actions      = Column(Text, nullable=True)
    re_evaluation_date    = Column(Date, nullable=True)

    assessment = relationship("TrainingAssessment", back_populates="dev_plan")


# ─────────────────────────────────────────────────────────────
# DELIVERY ANALYTICS MODULE — قسم تحليل تطبيقات التوصيل
# ─────────────────────────────────────────────────────────────

class DeliveryBrand(Base):
    # البراند / العلامة التجارية — ONDA, Ronaldos, Shawarma, Griddle
    __tablename__ = "delivery_brands"
    id         = Column(Integer, primary_key=True)
    name       = Column(String(100), unique=True, nullable=False)
    name_ar    = Column(String(100), nullable=True)
    is_active  = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    branches = relationship("DeliveryBranch", back_populates="brand", cascade="all, delete-orphan")
    records  = relationship("DeliveryRecord",  back_populates="brand")


class DeliveryBranch(Base):
    """الفروع — بيانات رسمية من ملف اللوكيشن"""
    __tablename__ = "delivery_branches"
    id              = Column(Integer, primary_key=True)
    brand_id        = Column(Integer, ForeignKey("delivery_brands.id"), nullable=False)
    name            = Column(String(200), nullable=False)   # الاسم الرسمي
    region          = Column(String(100), nullable=True)    # Eastern / Riyadh
    regular_hours   = Column(String(100), nullable=True)   # "06:00 AM TO 01:00 AM"
    weekend_hours   = Column(String(100), nullable=True)   # إذا مختلف
    hours_notes     = Column(Text, nullable=True)          # ملاحظات إضافية
    google_maps_url = Column(Text, nullable=True)
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime, default=datetime.utcnow)

    brand   = relationship("DeliveryBrand", back_populates="branches")
    aliases = relationship("DeliveryBranchAlias", back_populates="branch", cascade="all, delete-orphan")
    records = relationship("DeliveryRecord", back_populates="branch")


class DeliveryBranchAlias(Base):
    """أسماء بديلة للفرع كما تظهر في ملفات الاستيراد"""
    __tablename__ = "delivery_branch_aliases"
    id        = Column(Integer, primary_key=True)
    branch_id = Column(Integer, ForeignKey("delivery_branches.id"), nullable=False)
    alias     = Column(String(200), nullable=False)   # الاسم كما في ملف التطبيق

    branch = relationship("DeliveryBranch", back_populates="aliases")


class DeliveryApp(Base):
    """تطبيقات التوصيل — HungerStation, Keeta, Ninja"""
    __tablename__ = "delivery_apps"
    id         = Column(Integer, primary_key=True)
    name       = Column(String(100), unique=True, nullable=False)
    name_ar    = Column(String(100), nullable=True)
    is_active  = Column(Boolean, default=True)

    records = relationship("DeliveryRecord", back_populates="app")


class DeliveryRecord(Base):
    """سجل الأداء الشهري لكل فرع × تطبيق"""
    __tablename__ = "delivery_records"
    id              = Column(Integer, primary_key=True)
    year            = Column(Integer, nullable=False)
    month           = Column(Integer, nullable=False)    # 1-12
    brand_id        = Column(Integer, ForeignKey("delivery_brands.id"),   nullable=False)
    branch_id       = Column(Integer, ForeignKey("delivery_branches.id"), nullable=True)   # null = unmatched
    app_id          = Column(Integer, ForeignKey("delivery_apps.id"),     nullable=False)
    orders          = Column(Integer, default=0)
    revenue         = Column(Numeric(14, 2), default=0)
    aov             = Column(Numeric(10, 2), nullable=True)   # revenue / orders
    raw_branch_name = Column(String(200), nullable=True)      # اسم الفرع الأصلي من الملف
    raw_brand_name  = Column(String(200), nullable=True)      # اسم البراند الأصلي من الملف
    is_outlier      = Column(Boolean, default=False)          # قيمة شاذة
    import_batch    = Column(String(50), nullable=True)       # معرّف دفعة الاستيراد
    created_at      = Column(DateTime, default=datetime.utcnow)

    brand  = relationship("DeliveryBrand",  back_populates="records")
    branch = relationship("DeliveryBranch", back_populates="records")
    app    = relationship("DeliveryApp",    back_populates="records")


# ─────────────────────────────────────────────
# DOCUMENTS MODULE (Phase F3)
# الوثائق الرسمية (شهادات صحية للموظفين، رخص البلدية/الدفاع المدني/السجل التجاري للفروع)
# ─────────────────────────────────────────────

class DocumentOwnerType(str, enum.Enum):
    branch   = "branch"       # وثيقة على مستوى الفرع
    employee = "employee"     # وثيقة على مستوى موظف (user)


class DocumentType(str, enum.Enum):
    # وثائق الفروع
    municipality_license    = "municipality_license"     # رخصة بلدية
    civil_defense_license   = "civil_defense_license"    # رخصة دفاع مدني
    commercial_registration = "commercial_registration"  # سجل تجاري
    food_safety_permit      = "food_safety_permit"       # تصريح سلامة غذاء
    branch_other            = "branch_other"             # أخرى (فرع)
    # وثائق الموظفين
    health_certificate      = "health_certificate"       # شهادة صحية
    national_id             = "national_id"              # هوية وطنية / إقامة
    work_permit             = "work_permit"              # رخصة عمل
    work_contract           = "work_contract"            # عقد عمل
    employee_other          = "employee_other"           # أخرى (موظف)


class Document(Base):
    """
    وثيقة رسمية — إما للفرع أو لموظف.
    - expiry_date إلزامي (أساس نظام التذكيرات)
    - reminder_days: كم يوم قبل الانتهاء يبدأ التنبيه (افتراضي 30)
    - renewed_from_id: عند التجديد ننشئ سجل جديد ونربطه بالقديم ونرشف القديم
    - last_reminder_at: لمنع الـ scheduler من إرسال نفس التنبيه مرتين في نفس اليوم
    """
    __tablename__ = "documents"
    id               = Column(Integer, primary_key=True)
    owner_type       = Column(SAEnum(DocumentOwnerType), nullable=False, index=True)
    branch_id        = Column(Integer, ForeignKey("branches.id"), nullable=True, index=True)
    user_id          = Column(Integer, ForeignKey("users.id"),    nullable=True, index=True)
    doc_type         = Column(SAEnum(DocumentType), nullable=False, index=True)
    title            = Column(String(200), nullable=False)
    issuer           = Column(String(150), nullable=True)   # الجهة المُصدرة
    doc_number       = Column(String(100), nullable=True)   # رقم الوثيقة
    issue_date       = Column(Date, nullable=True)
    expiry_date      = Column(Date, nullable=False, index=True)
    reminder_days    = Column(Integer, default=30, nullable=False)
    file_path        = Column(String(500), nullable=True)
    file_name        = Column(String(255), nullable=True)
    mime_type        = Column(String(100), nullable=True)
    size_bytes       = Column(Integer, nullable=True)
    notes            = Column(Text, nullable=True)
    # lifecycle
    is_archived      = Column(Boolean, default=False, nullable=False, index=True)
    renewed_from_id  = Column(Integer, ForeignKey("documents.id"), nullable=True)
    last_reminder_at = Column(DateTime, nullable=True)
    # audit
    uploaded_by      = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at       = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at       = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    is_deleted       = Column(Boolean, default=False, nullable=False)
    tenant_id        = Column(Integer, default=1, nullable=False, index=True)

    branch       = relationship("Branch", foreign_keys=[branch_id])
    user         = relationship("User",   foreign_keys=[user_id])
    uploader     = relationship("User",   foreign_keys=[uploaded_by])
    renewed_from = relationship("Document", remote_side=[id], foreign_keys=[renewed_from_id])

    __table_args__ = (
        Index("ix_documents_expiry_active", "expiry_date", "is_archived", "is_deleted"),
        Index("ix_documents_owner_branch", "owner_type", "branch_id"),
        Index("ix_documents_owner_user", "owner_type", "user_id"),
    )


# ─────────────────────────────────────────────
# Sales Channels Unification & Reconciliation (Pack C / Phase 1)
# SPEC v3 — imported here so Base.metadata picks up the tables.
# ─────────────────────────────────────────────
from app.models.sales_channels import (  # noqa: E402,F401
    ChannelType,
    ClosureScopeType,
    ReconciliationStatus,
    ImportSource,
    SalesChannel,
    BranchDailySale,
    AppMonthlyStatement,
    MonthlyClosure,
    ReconciliationSnapshot,
)

# ─────────────────────────────────────────────
# AI Assistant — User Suggestions
# ─────────────────────────────────────────────


class SuggestionCategory(str, enum.Enum):
    ui = "ui"
    workflow = "workflow"
    bug = "bug"
    feature = "feature"
    other = "other"


class SuggestionPriority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class SuggestionStatus(str, enum.Enum):
    pending = "pending"
    reviewed = "reviewed"
    approved = "approved"
    rejected = "rejected"
    implemented = "implemented"


class UserSuggestion(Base):
    """
    Captures improvement suggestions detected by the AI assistant.

    The assistant tags its replies with [SUGGESTION:category:priority]
    when it senses a feature request, bug report, or workflow concern.
    The router parses the tag, persists this row, and strips it from
    the answer before responding to the frontend.
    """

    __tablename__ = "user_suggestions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    role_at_creation = Column(String(50), nullable=False)  # snapshot of role name
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True, index=True)
    suggestion_text = Column(Text, nullable=False)
    category = Column(
        SAEnum(SuggestionCategory, name="suggestion_category"),
        nullable=False,
        default=SuggestionCategory.other,
        index=True,
    )
    priority = Column(
        SAEnum(SuggestionPriority, name="suggestion_priority"),
        nullable=False,
        default=SuggestionPriority.medium,
        index=True,
    )
    status = Column(
        SAEnum(SuggestionStatus, name="suggestion_status"),
        nullable=False,
        default=SuggestionStatus.pending,
        index=True,
    )
    admin_note = Column(Text, nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    user = relationship("User", foreign_keys=[user_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    branch = relationship("Branch", foreign_keys=[branch_id])

    __table_args__ = (
        Index("idx_user_suggestions_status_created", "status", "created_at"),
    )
