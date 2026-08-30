"""
Pydantic schemas for request/response validation
"""
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from typing import Any, List, Literal, Optional
from datetime import datetime, date
from decimal import Decimal
from app.models import (
    UserStatus, RoleName, InventoryStatus, OrderStatus,
    OrderType, TransactionType, AvgConsumptionMode, ItemType, StorageType,
    QualityVisitStatus, QualityResponseStatus,
    TrainingRoleType, AssessmentStatus, AssessmentVerdict,
    DocumentOwnerType, DocumentType,
    SupplySourceType, SupplyDefaultSource,
    BranchRequestStatus, BranchRequestLineStatus,
    ProductionOrderStatus, KitchenMaterialRequestStatus,
    WarehouseLineSourceType, WarehouseLineStatus,
    DeliveryOrderStatus, DeliveryOrderLineStatus,
    EvaluationType, EvaluationTargetMode, EvaluationTemplateVersionStatus,
    EvaluationStatus, EvaluationFinalRating,
)
from app.schemas.assistant import (
    AssistantAskRequest,
    AssistantAskResponse,
    AssistantStatusResponse,
    SuggestionListItem,
    SuggestionStatsResponse,
    SuggestionUpdateRequest,
)


# ─── Shared ───────────────────────────────────
class PaginatedResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list


# ─── Auth ─────────────────────────────────────
class Token(BaseModel):
    access_token: str
    token_type: str
    user: dict


class LoginRequest(BaseModel):
    username: str
    password: str


# ─── Role ─────────────────────────────────────
class RoleOut(BaseModel):
    id: int
    name: RoleName
    display_name: str
    description: Optional[str] = None
    model_config = {"from_attributes": True}


class RoleNameOut(BaseModel):
    name: RoleName


# ─── User ─────────────────────────────────────
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    full_name: str
    password: str
    phone: Optional[str] = None
    branch_id: Optional[int] = None
    warehouse_id: Optional[int] = None
    role_names: List[RoleName] = []

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    branch_id: Optional[int] = None
    warehouse_id: Optional[int] = None
    status: Optional[UserStatus] = None
    role_names: Optional[List[RoleName]] = None


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    status: UserStatus
    branch_id: Optional[int] = None
    warehouse_id: Optional[int] = None
    phone: Optional[str] = None
    roles: List[str] = []
    created_at: datetime
    model_config = {"from_attributes": True}


class AuditFindingCreate(BaseModel):
    entity_type: str = Field(..., min_length=1, max_length=50)
    entity_id: int = Field(..., ge=1)
    severity: Literal["info", "warning", "violation"]
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10)


class AuditFindingUpdate(BaseModel):
    severity: Optional[Literal["info", "warning", "violation"]] = None
    title: Optional[str] = Field(default=None, min_length=5, max_length=200)
    description: Optional[str] = Field(default=None, min_length=10)


class AuditFindingAcknowledge(BaseModel):
    response_text: str = Field(..., min_length=10)


class AuditFindingOut(BaseModel):
    id: int
    finding_no: str
    entity_type: str
    entity_id: int
    severity: str
    title: str
    description: str
    created_by: int
    created_by_name: Optional[str] = None
    created_at: datetime
    acknowledged_by: Optional[int] = None
    acknowledged_by_name: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    response_text: Optional[str] = None
    status: str


class AuditFindingListResponse(PaginatedResponse):
    items: List[AuditFindingOut]


# ─── Warehouse ────────────────────────────────
class WarehouseCreate(BaseModel):
    warehouse_code: str
    warehouse_name: str
    location: Optional[str] = None
    active: bool = True


class WarehouseUpdate(BaseModel):
    warehouse_name: Optional[str] = None
    location: Optional[str] = None
    active: Optional[bool] = None


class WarehouseOut(BaseModel):
    id: int
    warehouse_code: str
    warehouse_name: str
    location: Optional[str] = None
    active: bool
    model_config = {"from_attributes": True}


# ─── Branch ───────────────────────────────────
class BranchCreate(BaseModel):
    branch_code: str
    branch_name: str
    city: Optional[str] = None
    area: Optional[str] = None
    warehouse_id: int
    active: bool = True


class BranchUpdate(BaseModel):
    branch_name: Optional[str] = None
    city: Optional[str] = None
    area: Optional[str] = None
    warehouse_id: Optional[int] = None
    active: Optional[bool] = None


class BranchOut(BaseModel):
    id: int
    branch_code: str
    branch_name: str
    city: Optional[str] = None
    area: Optional[str] = None
    warehouse_id: int
    active: bool
    model_config = {"from_attributes": True}


class BranchEmployeeCreate(BaseModel):
    branch_id: Optional[int] = None
    full_name: str = Field(..., min_length=1, max_length=150)
    job_title: str = Field(..., min_length=1, max_length=120)
    work_number: str = Field(..., min_length=1, max_length=50)
    phone: Optional[str] = Field(default=None, max_length=30)
    active: bool = True


class BranchEmployeeUpdate(BaseModel):
    branch_id: Optional[int] = None
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    job_title: Optional[str] = Field(default=None, min_length=1, max_length=120)
    work_number: Optional[str] = Field(default=None, min_length=1, max_length=50)
    phone: Optional[str] = Field(default=None, max_length=30)
    active: Optional[bool] = None


class BranchEmployeeDeactivatePayload(BaseModel):
    active: bool = False


class BranchEmployeeOut(BaseModel):
    id: int
    branch_id: int
    full_name: str
    job_title: str
    work_number: str
    phone: Optional[str] = None
    active: bool
    created_at: datetime
    updated_at: datetime
    branch_name: Optional[str] = None
    model_config = {"from_attributes": True}


# ─── Item Category ────────────────────────────
class CategoryCreate(BaseModel):
    code: str
    name_ar: str
    name_en: str
    active: bool = True


class CategoryOut(BaseModel):
    id: int
    code: str
    name_ar: str
    name_en: str
    active: bool
    model_config = {"from_attributes": True}


# ─── Unit ─────────────────────────────────────
class UnitCreate(BaseModel):
    code: str
    name_ar: str
    name_en: str
    active: bool = True


class UnitOut(BaseModel):
    id: int
    code: str
    name_ar: str
    name_en: str
    active: bool
    model_config = {"from_attributes": True}


class BrandCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    active: bool = True


class BrandOut(BaseModel):
    id: int
    name: str
    active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class BrandCountItemBranchOut(BaseModel):
    id: int
    branch_code: str
    branch_name: str
    city: Optional[str] = None


class BrandCountItemOut(BaseModel):
    id: int
    brand_id: int
    item_id: int
    item_code: str
    item_name_ar: str
    item_name_en: str
    unit_name_ar: str
    unit_name_en: str
    display_order: int
    is_active: bool


class BrandCountItemsListResponse(BaseModel):
    brand_id: int
    brand_name: str
    branch_count: int
    branches: list[BrandCountItemBranchOut]
    items: list[BrandCountItemOut]


class BrandCountItemCreate(BaseModel):
    item_id: int
    display_order: Optional[int] = None


class BrandCountItemUpdate(BaseModel):
    display_order: Optional[int] = None
    is_active: Optional[bool] = None


class KitchenSectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    active: bool = True


class KitchenSectionOut(BaseModel):
    id: int
    name: str
    active: bool
    created_at: datetime
    kitchen_ids: list[int] = Field(default_factory=list)
    model_config = {"from_attributes": True}


class KitchenOut(BaseModel):
    id: int
    name: str
    city: str
    active: bool
    created_at: datetime
    section_ids: list[int] = Field(default_factory=list)
    model_config = {"from_attributes": True}


class KitchenCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    city: str = Field(..., min_length=1, max_length=100)
    active: bool = True
    section_ids: list[int] = Field(default_factory=list)


class KitchenSectionAssignmentCreate(BaseModel):
    user_id: int
    kitchen_section_id: int
    active: bool = True
    service_city: Optional[str] = Field(None, max_length=100)


class KitchenSectionAssignmentOut(BaseModel):
    id: int
    user_id: int
    kitchen_section_id: int
    active: bool
    service_city: Optional[str] = None
    created_at: datetime
    ended_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class BranchBrandCreate(BaseModel):
    branch_id: int
    brand_id: int


class AreaManagerAssignmentCreate(BaseModel):
    user_id: int
    city: str = Field(..., min_length=1, max_length=100)
    brand_id: int
    active: bool = True


class ItemBrandCreate(BaseModel):
    item_id: int
    brand_id: int


# ─── Item ─────────────────────────────────────
class ItemCreate(BaseModel):
    item_code: str
    item_name_ar: str
    item_name_en: str
    category_id: int
    unit_id: int
    item_type: ItemType = ItemType.raw_material
    storage_type: StorageType = StorageType.ambient
    purchase_unit_id: Optional[int] = None
    supply_unit_id: Optional[int] = None
    conversion_ratio: Decimal = Decimal("1")
    branch_requestable: bool = True
    visible_in_branch_ui: bool = True
    active: bool = True
    min_qty: Decimal = Decimal("0")
    max_qty: Decimal = Decimal("0")
    reorder_point: Decimal = Decimal("0")
    safety_stock: Decimal = Decimal("0")
    lead_time_days: int = 1
    shelf_life_days: int = 0
    average_consumption_mode: AvgConsumptionMode = AvgConsumptionMode.last_7_days
    critical_item: bool = False
    source_type: SupplySourceType = SupplySourceType.WAREHOUSE
    default_source: SupplyDefaultSource = SupplyDefaultSource.WAREHOUSE
    kitchen_section_id: Optional[int] = None

    @model_validator(mode="after")
    def validate_master_units(self):
        if self.conversion_ratio <= 0:
            raise ValueError("conversion_ratio must be greater than zero")

        has_purchase = self.purchase_unit_id is not None
        has_supply = self.supply_unit_id is not None
        if has_purchase != has_supply:
            raise ValueError("purchase_unit_id and supply_unit_id must be provided together")

        if not has_purchase and self.conversion_ratio != Decimal("1"):
            raise ValueError("conversion_ratio must be 1 when purchase and supply units are not provided")

        if self.source_type == SupplySourceType.KITCHEN and self.kitchen_section_id is None:
            raise ValueError("kitchen_section_id is required when source_type is KITCHEN")

        if self.source_type == SupplySourceType.NOT_REQUESTABLE:
            return self

        if self.source_type == SupplySourceType.WAREHOUSE and self.default_source == SupplyDefaultSource.KITCHEN:
            raise ValueError("default_source cannot be KITCHEN when source_type is WAREHOUSE")

        if self.source_type == SupplySourceType.KITCHEN and self.default_source == SupplyDefaultSource.WAREHOUSE:
            raise ValueError("default_source cannot be WAREHOUSE when source_type is KITCHEN")

        return self


class ItemUpdate(BaseModel):
    item_name_ar: Optional[str] = None
    item_name_en: Optional[str] = None
    category_id: Optional[int] = None
    unit_id: Optional[int] = None
    item_type: Optional[ItemType] = None
    storage_type: Optional[StorageType] = None
    purchase_unit_id: Optional[int] = None
    supply_unit_id: Optional[int] = None
    conversion_ratio: Optional[Decimal] = None
    branch_requestable: Optional[bool] = None
    visible_in_branch_ui: Optional[bool] = None
    active: Optional[bool] = None
    min_qty: Optional[Decimal] = None
    max_qty: Optional[Decimal] = None
    reorder_point: Optional[Decimal] = None
    safety_stock: Optional[Decimal] = None
    lead_time_days: Optional[int] = None
    shelf_life_days: Optional[int] = None
    average_consumption_mode: Optional[AvgConsumptionMode] = None
    critical_item: Optional[bool] = None
    source_type: Optional[SupplySourceType] = None
    default_source: Optional[SupplyDefaultSource] = None
    kitchen_section_id: Optional[int] = None

    @model_validator(mode="after")
    def validate_master_units(self):
        if self.conversion_ratio is not None and self.conversion_ratio <= 0:
            raise ValueError("conversion_ratio must be greater than zero")

        has_purchase = self.purchase_unit_id is not None
        has_supply = self.supply_unit_id is not None
        if has_purchase != has_supply:
            raise ValueError("purchase_unit_id and supply_unit_id must be provided together")

        if self.source_type == SupplySourceType.KITCHEN and self.kitchen_section_id is None:
            raise ValueError("kitchen_section_id is required when source_type is KITCHEN")

        if self.source_type == SupplySourceType.NOT_REQUESTABLE:
            return self

        if self.source_type == SupplySourceType.WAREHOUSE and self.default_source == SupplyDefaultSource.KITCHEN:
            raise ValueError("default_source cannot be KITCHEN when source_type is WAREHOUSE")

        if self.source_type == SupplySourceType.KITCHEN and self.default_source == SupplyDefaultSource.WAREHOUSE:
            raise ValueError("default_source cannot be WAREHOUSE when source_type is KITCHEN")

        return self


class ItemOut(BaseModel):
    id: int
    item_code: str
    item_name_ar: str
    item_name_en: str
    category_id: int
    unit_id: int
    item_type: ItemType
    storage_type: StorageType
    purchase_unit_id: Optional[int] = None
    supply_unit_id: Optional[int] = None
    conversion_ratio: Decimal
    branch_requestable: bool
    visible_in_branch_ui: bool
    active: bool
    min_qty: Decimal
    max_qty: Decimal
    reorder_point: Decimal
    safety_stock: Decimal
    lead_time_days: int
    shelf_life_days: int
    average_consumption_mode: AvgConsumptionMode
    critical_item: bool
    source_type: SupplySourceType
    default_source: SupplyDefaultSource
    kitchen_section_id: Optional[int] = None
    category: Optional[CategoryOut] = None
    unit: Optional[UnitOut] = None
    purchase_unit: Optional[UnitOut] = None
    supply_unit: Optional[UnitOut] = None
    model_config = {"from_attributes": True}


class ItemListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[ItemOut]


class BranchRequestLineCreate(BaseModel):
    item_id: int
    qty_requested: Decimal = Field(..., gt=0)
    source_type: Optional[SupplySourceType] = None
    notes: Optional[str] = None


class BranchRequestLineUpdate(BaseModel):
    item_id: int
    qty_requested: Decimal = Field(..., gt=0)
    source_type: Optional[SupplySourceType] = None
    notes: Optional[str] = None


class BranchRequestCreate(BaseModel):
    branch_id: int
    brand_id: int
    priority: Optional[str] = None
    lines: List[BranchRequestLineCreate] = Field(..., min_length=1)


class BranchRequestUpdate(BaseModel):
    priority: Optional[str] = None
    lines: List[BranchRequestLineUpdate] = Field(..., min_length=1)


class BranchRequestLineApprove(BaseModel):
    line_id: int
    qty_approved: Decimal = Field(..., gt=0)
    approval_note: Optional[str] = None


class BranchRequestApprovePayload(BaseModel):
    approval_note: Optional[str] = None


class BranchRequestModifyApprovePayload(BaseModel):
    approval_note: str = Field(..., min_length=1)
    lines: List[BranchRequestLineApprove] = Field(..., min_length=1)


class BranchRequestRejectPayload(BaseModel):
    rejection_note: str = Field(..., min_length=1)


class BranchRequestLineOut(BaseModel):
    id: int
    request_id: int
    item_id: int
    item_name_ar_snapshot: Optional[str] = None
    item_name_en_snapshot: Optional[str] = None
    item_code_snapshot: Optional[str] = None
    unit_code_snapshot: Optional[str] = None
    qty_requested: Decimal
    qty_approved: Optional[Decimal] = None
    source_type: SupplySourceType
    resolved_source_type: Optional[SupplyDefaultSource] = None
    status: BranchRequestLineStatus
    approval_note: Optional[str] = None
    notes: Optional[str] = None
    item: Optional[ItemOut] = None
    model_config = {"from_attributes": True}


class BranchRequestOut(BaseModel):
    id: int
    request_no: str
    branch_id: int
    branch_name: Optional[str] = None
    brand_id: int
    brand_name_snapshot: Optional[str] = None
    status: BranchRequestStatus
    priority: Optional[str] = None
    created_by: int
    submitted_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    approved_by: Optional[int] = None
    rejected_at: Optional[datetime] = None
    rejected_by: Optional[int] = None
    rejection_note: Optional[str] = None
    approval_note: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    lines: List[BranchRequestLineOut] = []
    model_config = {"from_attributes": True}


class BranchRequestListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[BranchRequestOut]


class BranchRequestTimelineEventOut(BaseModel):
    key: str
    label_ar: str
    at: datetime
    owner_role_ar: Optional[str] = None
    detail: Optional[str] = None
    source: str


class BranchRequestFulfillmentLineOut(BaseModel):
    request_line_id: int
    item_id: int
    item_name: str
    requested_qty: Decimal
    issued_qty: Decimal
    delivered_qty: Decimal
    remaining_qty: Decimal
    delay_reason: Optional[str] = None
    line_status: str
    route_ar: Optional[str] = None


class BranchRequestStatusSummaryOut(BaseModel):
    current_status_ar: str
    current_owner_ar: str
    next_action_ar: str
    last_updated_at: datetime


class BranchRequestDetailOut(BaseModel):
    request: BranchRequestOut
    branch_name: str
    timeline: List[BranchRequestTimelineEventOut]
    fulfillment_lines: List[BranchRequestFulfillmentLineOut]
    status_summary: BranchRequestStatusSummaryOut
    timeline_gaps: List[str] = []


class ProductionOrderOut(BaseModel):
    id: int
    source_request_id: int
    source_request_line_id: int
    destination_branch_id: int
    branch_name: Optional[str] = None
    destination_warehouse_name: Optional[str] = None
    brand_id: int
    kitchen_section_id: int
    item_id: int
    qty_requested: Decimal
    qty_ready: Decimal
    qty_sent_to_warehouse: Decimal = Decimal("0")
    status: ProductionOrderStatus
    priority: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    item: Optional[ItemOut] = None
    model_config = {"from_attributes": True}


class ProductionQtyPayload(BaseModel):
    qty_ready: Decimal = Field(..., gt=0)
    notes: Optional[str] = None


class ProductionMaterialRequestCreate(BaseModel):
    item_id: int
    qty: Decimal = Field(..., gt=0)
    notes: Optional[str] = None


class KitchenMaterialDecisionPayload(BaseModel):
    notes: Optional[str] = None


class KitchenMaterialRejectPayload(BaseModel):
    reason: str = Field(..., min_length=1)


class KitchenMaterialRequestOut(BaseModel):
    id: int
    production_order_id: int
    kitchen_section_id: int
    item_id: int
    qty: Decimal
    status: KitchenMaterialRequestStatus
    notes: Optional[str] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class WarehouseLineOut(BaseModel):
    id: int
    source_request_id: Optional[int] = None
    source_request_line_id: Optional[int] = None
    source_type: WarehouseLineSourceType
    branch_id: int
    branch_name: Optional[str] = None
    brand_id: int
    kitchen_section_id: Optional[int] = None
    item_id: int
    requested_qty: Decimal
    issued_qty: Decimal
    pending_qty: Decimal
    status: WarehouseLineStatus
    delay_reason: Optional[str] = None
    current_stock: Optional[Decimal] = None
    reserved_stock: Optional[Decimal] = None
    available_stock: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime
    item: Optional[ItemOut] = None
    model_config = {"from_attributes": True}


class WarehouseIssuePayload(BaseModel):
    qty: Optional[Decimal] = Field(None, gt=0)
    delay_reason: Optional[str] = None


class WarehouseDelayPayload(BaseModel):
    delay_reason: str = Field(..., min_length=1)


class DeliveryOrderCreate(BaseModel):
    warehouse_line_ids: List[int] = Field(..., min_length=1)


class DeliveryOrderLineReceipt(BaseModel):
    line_id: int
    qty_received: Decimal = Field(..., ge=0)
    shortage_reason: Optional[str] = None


class DeliveryOrderDeliverPayload(BaseModel):
    receiver_name: Optional[str] = None
    delivery_note: Optional[str] = None
    lines: Optional[List[DeliveryOrderLineReceipt]] = None


class DeliveryOrderLineOut(BaseModel):
    id: int
    delivery_order_id: int
    warehouse_line_id: int
    item_id: int
    qty_dispatched: Decimal
    qty_delivered: Decimal
    shortage_qty: Decimal = Decimal("0")
    status: DeliveryOrderLineStatus
    delivery_note: Optional[str] = None
    shortage_reason: Optional[str] = None
    item: Optional[ItemOut] = None
    model_config = {"from_attributes": True}


class DeliveryOrderOut(BaseModel):
    id: int
    source_request_id: Optional[int] = None
    branch_id: int
    branch_name: Optional[str] = None
    brand_id: int
    status: DeliveryOrderStatus
    ready_at: Optional[datetime] = None
    out_for_delivery_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[int] = None
    delivered_by: Optional[int] = None
    receiver_name: Optional[str] = None
    delivery_note: Optional[str] = None
    lines: List[DeliveryOrderLineOut] = []
    model_config = {"from_attributes": True}


class SupplierCreate(BaseModel):
    supplier_code: str
    name: str
    contact_name: Optional[str] = None
    phone: Optional[str] = None
    active: bool = True


class SupplierOut(BaseModel):
    id: int
    supplier_code: str
    name: str
    contact_name: Optional[str] = None
    phone: Optional[str] = None
    active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class PurchaseRequestLineCreate(BaseModel):
    item_id: int
    qty_requested: Decimal = Field(..., gt=0)
    notes: Optional[str] = None


class PurchaseRequestCreate(BaseModel):
    warehouse_id: int
    notes: Optional[str] = None
    lines: List[PurchaseRequestLineCreate] = Field(..., min_length=1)


class PurchaseRequestLineOut(BaseModel):
    id: int
    item_id: int
    qty_requested: Decimal
    notes: Optional[str] = None
    item: Optional[ItemOut] = None
    model_config = {"from_attributes": True}


class PurchaseRequestOut(BaseModel):
    id: int
    warehouse_id: int
    requested_by: int
    status: str
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    lines: List[PurchaseRequestLineOut] = []
    model_config = {"from_attributes": True}


class SupplyChainDashboardOut(BaseModel):
    pending_approvals: int = 0
    in_production: int = 0
    warehouse_delays: int = 0
    partial_orders: int = 0
    top_requested_items: List[dict[str, Any]] = Field(default_factory=list)
    requests_today: int = 0
    warehouse_pending: int = 0
    backorders: int = 0
    ready_for_delivery: int = 0
    out_for_delivery: int = 0
    delivered_today: int = 0
    production_ready: int = 0
    sent_to_warehouse: int = 0
    my_requests: int = 0
    shortages: int = 0
    partial_warehouse: int = 0


class EvaluationQuestionPayload(BaseModel):
    id: Optional[int] = None
    question_text_ar: str
    question_text_en: Optional[str] = None
    max_score: Decimal = Decimal("5")
    allow_na: bool = False
    requires_note_if_low_score: bool = False
    low_score_threshold: Decimal = Decimal("2")
    requires_photo: bool = False
    display_order: int = 1
    active: bool = True


class EvaluationSectionPayload(BaseModel):
    id: Optional[int] = None
    name: str
    weight_percent: Optional[Decimal] = None
    display_order: int = 1
    active: bool = True
    questions: List[EvaluationQuestionPayload] = []


class EvaluationTemplateCreate(BaseModel):
    name: str
    brand_id: int
    evaluation_type: EvaluationType
    target_mode: EvaluationTargetMode
    target_role: Optional[str] = None
    active: bool = True


class EvaluationTemplateUpdate(BaseModel):
    name: Optional[str] = None
    brand_id: Optional[int] = None
    evaluation_type: Optional[EvaluationType] = None
    target_mode: Optional[EvaluationTargetMode] = None
    target_role: Optional[str] = None
    active: Optional[bool] = None


class EvaluationTemplateOut(BaseModel):
    id: int
    name: str
    brand_id: int
    evaluation_type: EvaluationType
    target_mode: EvaluationTargetMode
    target_role: Optional[str] = None
    active: bool
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class EvaluationTemplateVersionCreate(BaseModel):
    notes: Optional[str] = None
    sections: List[EvaluationSectionPayload] = []


class EvaluationTemplateVersionUpdate(BaseModel):
    notes: Optional[str] = None
    sections: Optional[List[EvaluationSectionPayload]] = None


class EvaluationQuestionOut(BaseModel):
    id: int
    section_id: int
    question_text_ar: str
    question_text_en: Optional[str] = None
    max_score: Decimal
    allow_na: bool
    requires_note_if_low_score: bool
    low_score_threshold: Decimal
    requires_photo: bool
    display_order: int
    active: bool
    model_config = {"from_attributes": True}


class EvaluationSectionOut(BaseModel):
    id: int
    template_version_id: int
    name: str
    weight_percent: Optional[Decimal] = None
    display_order: int
    active: bool
    questions: List[EvaluationQuestionOut] = []
    model_config = {"from_attributes": True}


class EvaluationTemplateVersionOut(BaseModel):
    id: int
    template_id: int
    version_no: int
    status: EvaluationTemplateVersionStatus
    published_at: Optional[datetime] = None
    created_by: Optional[int] = None
    created_at: datetime
    notes: Optional[str] = None
    sections: List[EvaluationSectionOut] = []
    model_config = {"from_attributes": True}


class EvaluationCreate(BaseModel):
    template_version_id: int
    brand_id: Optional[int] = None
    branch_id: Optional[int] = None
    employee_id: Optional[int] = None
    evaluator_id: Optional[int] = None
    evaluation_date: date
    general_notes: Optional[str] = None


class EvaluationAnswerUpdate(BaseModel):
    answer_id: int
    score: Optional[Decimal] = None
    is_na: bool = False
    note: Optional[str] = None


class EvaluationUpdate(BaseModel):
    general_notes: Optional[str] = None
    answers: List[EvaluationAnswerUpdate] = []


class EvaluationTransitionPayload(BaseModel):
    notes: Optional[str] = None


class EvaluationAnswerOut(BaseModel):
    id: int
    evaluation_id: int
    question_id: int
    score: Optional[Decimal] = None
    is_na: bool
    note: Optional[str] = None
    question_text_snapshot: str
    section_name_snapshot: str
    max_score_snapshot: Decimal
    section_weight_snapshot: Optional[Decimal] = None
    display_order_snapshot: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class EvaluationOut(BaseModel):
    id: int
    template_id: int
    template_version_id: int
    brand_id: int
    branch_id: Optional[int] = None
    employee_id: Optional[int] = None
    evaluation_type: EvaluationType
    target_mode: EvaluationTargetMode
    evaluated_role: Optional[str] = None
    evaluator_id: int
    evaluation_date: date
    status: EvaluationStatus
    total_score: Optional[Decimal] = None
    total_percentage: Optional[Decimal] = None
    final_rating: Optional[EvaluationFinalRating] = None
    general_notes: Optional[str] = None
    low_score_count: Optional[int] = None
    action_required_flag: bool
    created_at: datetime
    updated_at: datetime
    submitted_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[int] = None
    closed_at: Optional[datetime] = None
    closed_by: Optional[int] = None
    answers: List[EvaluationAnswerOut] = []
    model_config = {"from_attributes": True}


class EvaluationActionPlanCreate(BaseModel):
    branch_id: Optional[int] = None
    employee_id: Optional[int] = None
    issue: str
    corrective_action: str
    responsible_user_id: int
    due_date: date


class EvaluationActionPlanUpdate(BaseModel):
    issue: Optional[str] = None
    corrective_action: Optional[str] = None
    responsible_user_id: Optional[int] = None
    due_date: Optional[date] = None
    status: Optional[str] = None


class EvaluationActionPlanOut(BaseModel):
    id: int
    evaluation_id: int
    branch_id: int
    employee_id: Optional[int] = None
    issue: str
    corrective_action: str
    responsible_user_id: int
    due_date: date
    status: str
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None
    closed_by: Optional[int] = None
    model_config = {"from_attributes": True}


class EvaluationAttachmentOut(BaseModel):
    id: int
    evaluation_id: int
    answer_id: Optional[int] = None
    storage_disk: str
    file_path: str
    file_name: str
    mime_type: str
    file_size: Optional[int] = None
    uploaded_by: int
    created_at: datetime
    model_config = {"from_attributes": True}


class StockTransactionOut(BaseModel):
    id: int
    transaction_date: datetime
    transaction_type: TransactionType
    source_type: Optional[str] = None
    source_id: Optional[int] = None
    destination_type: Optional[str] = None
    destination_id: Optional[int] = None
    item_id: int
    qty: Decimal
    reference_no: Optional[str] = None
    notes: Optional[str] = None
    created_by: Optional[int] = None
    model_config = {"from_attributes": True}


class StockCardResponse(BaseModel):
    item_id: int
    item_code: str
    item_name_ar: str
    item_name_en: str
    transactions: List[StockTransactionOut]


# ─── Daily Inventory ──────────────────────────
class InventoryLineCreate(BaseModel):
    item_id: int
    counted_qty: Decimal
    variance_reason_id: Optional[int] = None
    notes: Optional[str] = None

    @field_validator("counted_qty")
    @classmethod
    def validate_counted_qty(cls, v):
        if v < 0:
            raise ValueError("counted_qty must be >= 0")
        return v


class InventoryCreate(BaseModel):
    branch_id: int
    inventory_date: date
    lines: List[InventoryLineCreate]
    notes: Optional[str] = None
    # H9: daily (default) / weekly / monthly — purely informational
    inventory_type: Optional[str] = "daily"

    @field_validator("inventory_type")
    @classmethod
    def validate_inventory_type(cls, v):
        if v is None:
            return "daily"
        if v not in ("daily", "weekly", "monthly"):
            raise ValueError("inventory_type must be one of: daily, weekly, monthly")
        return v


class InventoryLineOut(BaseModel):
    id: int
    item_id: int
    item: Optional[ItemOut] = None
    book_qty: Decimal
    counted_qty: Decimal
    variance_qty: Decimal
    variance_pct: Decimal
    variance_status: Optional[str]
    below_min_flag: bool
    out_of_stock_flag: bool
    notes: Optional[str]
    model_config = {"from_attributes": True}


class InventoryOut(BaseModel):
    id: int
    branch_id: int
    inventory_date: date
    inventory_type: Optional[str] = "daily"
    status: InventoryStatus
    notes: Optional[str]
    submitted_at: Optional[datetime]
    approved_at: Optional[datetime]
    created_at: datetime
    lines: List[InventoryLineOut] = []
    model_config = {"from_attributes": True}


class InventorySummaryOut(BaseModel):
    id: int
    branch_id: int
    inventory_date: date
    inventory_type: Optional[str] = "daily"
    status: InventoryStatus
    notes: Optional[str] = None
    submitted_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    # H8: quick counts so list rows can flag surplus inventories at a glance
    line_count: int = 0
    surplus_lines_count: int = 0
    model_config = {"from_attributes": True}


class InventoryListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[InventorySummaryOut]


class RejectInventoryRequest(BaseModel):
    reason: str


class InventoryLinePartialUpdate(BaseModel):
    """PATCH a single inventory line — only the fields provided are updated."""
    counted_qty: Optional[Decimal] = None
    variance_reason_id: Optional[int] = None
    notes: Optional[str] = None

    @field_validator("counted_qty")
    @classmethod
    def validate_counted_qty(cls, v):
        if v is not None and v < 0:
            raise ValueError("counted_qty must be >= 0")
        return v


class TodayInventoryStatusOut(BaseModel):
    branch_id: int
    branch_name: str
    inventory_id: Optional[int] = None
    status: Optional[str] = None          # None means not started
    submitted_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    lines_count: int = 0
    items_below_min: int = 0
    items_out_of_stock: int = 0


# ─── Replenishment Orders ─────────────────────
class OrderLineUpdate(BaseModel):
    item_id: int
    branch_requested_qty: Optional[Decimal] = None
    wh_approved_qty: Optional[Decimal] = None
    rejection_reason: Optional[str] = None


class BranchReviewLineUpdate(BaseModel):
    line_id: int
    branch_requested_qty: Optional[Decimal] = None


class BranchReviewRequest(BaseModel):
    lines: List[BranchReviewLineUpdate] = []


class WarehouseReviewLineUpdate(BaseModel):
    line_id: int
    wh_approved_qty: Optional[Decimal] = None
    rejection_reason: Optional[str] = None


class WarehouseReviewRequest(BaseModel):
    lines: List[WarehouseReviewLineUpdate] = []


class OrderLineOut(BaseModel):
    id: int
    item_id: int
    item: Optional[ItemOut] = None
    suggested_qty: Decimal
    branch_requested_qty: Decimal
    wh_approved_qty: Decimal
    picked_qty: Decimal
    dispatched_qty: Decimal
    received_qty: Decimal
    damaged_qty: Decimal
    missing_qty: Decimal
    shortage_flag: bool
    shortage_reason: Optional[str]
    rejection_reason: Optional[str]
    line_status: str
    notes: Optional[str]
    model_config = {"from_attributes": True}


class OrderOut(BaseModel):
    id: int
    order_no: str
    branch_id: int
    warehouse_id: int
    order_type: OrderType
    status: OrderStatus
    order_date: date
    notes: Optional[str]
    rejection_reason: Optional[str] = None
    dispatch_note_no: Optional[str]
    created_at: datetime
    lines: List[OrderLineOut] = []
    model_config = {"from_attributes": True}


class ExceptionalOrderLineCreate(BaseModel):
    item_id: int
    qty: Decimal = Decimal("0")           # alias used in router payload
    branch_requested_qty: Optional[Decimal] = None   # alternative field name
    notes: Optional[str] = None

    @property
    def resolved_qty(self) -> Decimal:
        """Return branch_requested_qty if set, else qty."""
        if self.branch_requested_qty is not None:
            return self.branch_requested_qty
        return self.qty


class ExceptionalOrderCreate(BaseModel):
    branch_id: int
    items: List[ExceptionalOrderLineCreate]
    notes: Optional[str] = None


# ─── Inter-branch transfer workflow ────────────────────────────
# branch_manager يعمل طلب تحويل → area_manager يوافق أو يرفض → المخزون يتحرّك عند الموافقة فقط
class InterBranchLineCreate(BaseModel):
    item_id: int
    qty: Decimal

    @field_validator("qty")
    @classmethod
    def _qty_positive(cls, v: Decimal) -> Decimal:
        if v is None or v <= 0:
            raise ValueError("qty must be > 0")
        return v


class InterBranchOrderCreate(BaseModel):
    # branch_id (source) يُستنتج من المستخدم إن لم يُحدَّد صراحة
    source_branch_id: Optional[int] = None
    destination_branch_id: int
    items: List[InterBranchLineCreate]
    reason: str = Field(..., min_length=3, max_length=500)
    reference_no: Optional[str] = Field(default=None, max_length=50)
    notes: Optional[str] = None

    @model_validator(mode="after")
    def _source_destination_differ(self):
        if self.source_branch_id is not None and self.source_branch_id == self.destination_branch_id:
            raise ValueError("source_branch_id و destination_branch_id لا يمكن أن يكونا نفس الفرع")
        if not self.items:
            raise ValueError("يجب إضافة صنف واحد على الأقل")
        return self


class InterBranchApproveRequest(BaseModel):
    notes: Optional[str] = None


class InterBranchRejectRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


class InterBranchOrderLineOut(BaseModel):
    id: int
    item_id: int
    item_code: Optional[str] = None
    item_name_ar: Optional[str] = None
    qty: Decimal
    line_status: str


class InterBranchOrderOut(BaseModel):
    id: int
    order_no: str
    source_branch_id: int
    source_branch_name: Optional[str] = None
    destination_branch_id: int
    destination_branch_name: Optional[str] = None
    status: str
    reason: Optional[str] = None
    reference_no: Optional[str] = None
    notes: Optional[str] = None
    rejection_reason: Optional[str] = None
    order_date: str
    created_at: datetime
    created_by: Optional[int] = None
    lines: List[InterBranchOrderLineOut] = []


class RejectOrderRequest(BaseModel):
    reason: str


class CancelOrderRequest(BaseModel):
    reason: str


class DispatchLineCreate(BaseModel):
    line_id: int
    dispatched_qty: Optional[Decimal] = None
    shortage_reason: Optional[str] = None


class DispatchOrderRequest(BaseModel):
    lines: List[DispatchLineCreate] = []
    dispatch_note_no: Optional[str] = None


class ReceivingLineCreate(BaseModel):
    line_id: int
    received_qty: Optional[Decimal] = None
    damaged_qty: Optional[Decimal] = Decimal("0")
    missing_qty: Optional[Decimal] = Decimal("0")
    receiving_variance_reason_id: Optional[int] = None
    notes: Optional[str] = None


class ReceivingConfirmCreate(BaseModel):
    lines: List[ReceivingLineCreate]
    notes: Optional[str] = None


class IdempotencyReplayOut(BaseModel):
    replayed: bool
    operation_name: Optional[str] = None
    response_reference_type: Optional[str] = None
    response_reference_id: Optional[str] = None


class OrderActionResponse(BaseModel):
    message: str
    order_id: Optional[int] = None
    status: Optional[str] = None
    dispatch_note_no: Optional[str] = None
    idempotency: Optional[IdempotencyReplayOut] = Field(default=None, alias="_idempotency")

    model_config = {"populate_by_name": True}


class InventoryActionResponse(BaseModel):
    message: str
    inventory: InventoryOut
    idempotency: Optional[IdempotencyReplayOut] = Field(default=None, alias="_idempotency")

    model_config = {"populate_by_name": True}


class InventoryApprovalResponse(BaseModel):
    message: str
    inventory: InventoryOut
    replenishment_order: Optional[OrderOut] = None
    idempotency: Optional[IdempotencyReplayOut] = Field(default=None, alias="_idempotency")

    model_config = {"populate_by_name": True}


class OrderLineSummaryOut(BaseModel):
    id: int
    item_id: int
    item_code: Optional[str] = None
    item_name_ar: Optional[str] = None
    item_name_en: Optional[str] = None
    unit: Optional[str] = None
    suggested_qty: float
    branch_requested_qty: float
    wh_approved_qty: float
    picked_qty: float
    dispatched_qty: float
    received_qty: float
    damaged_qty: float
    missing_qty: float
    shortage_flag: bool
    shortage_reason: Optional[str] = None
    rejection_reason: Optional[str] = None
    line_status: str
    notes: Optional[str] = None


class OrderSummaryOut(BaseModel):
    id: int
    order_no: str
    branch_id: int
    branch_name: Optional[str] = None
    branch_name_ar: Optional[str] = None
    warehouse_id: int
    order_type: OrderType
    status: OrderStatus
    order_date: date
    notes: Optional[str] = None
    dispatch_note_no: Optional[str] = None
    created_at: datetime
    lines: List[OrderLineSummaryOut] = []


class OrderListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[OrderSummaryOut]


class PickListLineOut(BaseModel):
    item_code: Optional[str] = None
    item_name_ar: Optional[str] = None
    item_name_en: Optional[str] = None
    unit: str
    qty_to_pick: float
    picked: float


class PickListOut(BaseModel):
    order_no: str
    order_date: str
    branch_id: int
    lines: List[PickListLineOut]


# ─── Stock ────────────────────────────────────
class BranchStockOut(BaseModel):
    id: int
    branch_id: int
    item_id: int
    item: Optional[ItemOut] = None
    current_qty: Decimal
    reserved_qty: Decimal
    in_transit_qty: Decimal
    model_config = {"from_attributes": True}


class WarehouseStockOut(BaseModel):
    id: int
    warehouse_id: int
    item_id: int
    item: Optional[ItemOut] = None
    current_qty: Decimal
    reserved_qty: Decimal
    model_config = {"from_attributes": True}


# ─── Reports / Dashboard ──────────────────────
class BranchDashboardOut(BaseModel):
    branch_id: int
    branch_name: str
    today_inventory_status: Optional[str]
    items_below_min: int
    items_out_of_stock: int
    open_orders: int
    pending_receiving: int


class WarehouseDashboardOut(BaseModel):
    warehouse_id: int
    warehouse_name: str
    pending_orders: int
    approved_orders: int
    orders_in_picking: int
    orders_dispatched_today: int
    stock_shortage_items: int


class VarianceReasonOut(BaseModel):
    id: int
    reason_ar: str
    reason_en: str
    active: bool = True
    model_config = {"from_attributes": True}


# ─── Category (update) ────────────────────────
class CategoryUpdate(BaseModel):
    name_ar: Optional[str] = None
    name_en: Optional[str] = None
    active: Optional[bool] = None


# ─── Unit (update) ────────────────────────────
class UnitUpdate(BaseModel):
    name_ar: Optional[str] = None
    name_en: Optional[str] = None
    active: Optional[bool] = None


# ─── Variance Reasons (create/update) ─────────
class VarianceReasonCreate(BaseModel):
    reason_ar: str
    reason_en: str
    active: bool = True


class VarianceReasonUpdate(BaseModel):
    reason_ar: Optional[str] = None
    reason_en: Optional[str] = None
    active: Optional[bool] = None


# ─── Stock Initialization ─────────────────────
class StockInitRequest(BaseModel):
    opening_qty: Decimal = Decimal("0")
    notes: Optional[str] = None

    @field_validator("opening_qty")
    @classmethod
    def validate_qty(cls, v):
        if v < 0:
            raise ValueError("opening_qty must be >= 0")
        return v


class StockInitResponse(BaseModel):
    message: str
    item_id: int
    entity_type: str
    entity_id: int
    current_qty: Decimal


# ─── Stock List Responses ─────────────────────
class BranchStockListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[BranchStockOut]


class WarehouseStockListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[WarehouseStockOut]


# ─── Quality Visit ────────────────────────────
class QualityVisitItemOut(BaseModel):
    id: int
    section_id: int
    text_ar: str
    text_en: Optional[str] = None
    benchmark_ar: Optional[str] = None
    benchmark_en: Optional[str] = None
    response_type: str = "yes_no"
    numeric_unit: Optional[str] = None
    order: int
    is_active: bool
    model_config = {"from_attributes": True}


class QualityVisitSectionOut(BaseModel):
    id: int
    brand_key: Optional[str] = None
    name_ar: str
    name_en: Optional[str] = None
    order: int
    weight: float
    is_active: bool
    items: List[QualityVisitItemOut] = []
    model_config = {"from_attributes": True}


class QualityVisitResponseCreate(BaseModel):
    item_id: int
    status: Optional[QualityResponseStatus] = None  # optional for numeric/text items
    numeric_value: Optional[Decimal] = None
    text_value: Optional[str] = None
    notes: Optional[str] = None
    corrective_action: Optional[str] = None
    action_owner: Optional[str] = None
    due_date: Optional[date] = None


class QualityVisitCreate(BaseModel):
    branch_id: int
    brand_key: Optional[str] = None
    visitor_id: int
    branch_in_charge: Optional[int] = None
    visit_date: date
    shift: Optional[str] = None
    summary_notes: Optional[str] = None
    responses: List[QualityVisitResponseCreate] = []


class QualityVisitAttachmentOut(BaseModel):
    id: int
    response_id: Optional[int] = None   # null for visit-level attachments
    visit_id: Optional[int] = None       # null for response-level attachments
    file_path: str
    original_name: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    kind: str = "photo"
    uploaded_by: Optional[int] = None
    uploaded_at: datetime
    model_config = {"from_attributes": True}


class QualityVisitResponseOut(BaseModel):
    id: int
    visit_id: int
    item_id: int
    item: Optional[QualityVisitItemOut] = None
    status: Optional[QualityResponseStatus] = None
    numeric_value: Optional[Decimal] = None
    text_value: Optional[str] = None
    notes: Optional[str] = None
    corrective_action: Optional[str] = None
    action_owner: Optional[str] = None
    due_date: Optional[date] = None
    is_resolved: bool
    resolved_by: Optional[int] = None
    resolved_at: Optional[datetime] = None
    attachments: List[QualityVisitAttachmentOut] = []
    model_config = {"from_attributes": True}


class QualityVisitOut(BaseModel):
    id: int
    branch_id: int
    brand_key: Optional[str] = None
    visitor_id: int
    branch_in_charge: Optional[int] = None
    visit_date: date
    shift: Optional[str] = None
    status: QualityVisitStatus
    compliance_pct: Optional[float] = None
    summary_notes: Optional[str] = None
    follow_up_date: Optional[date] = None
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    # E8 — signatures
    visitor_signature: Optional[str] = None
    visitor_signed_at: Optional[datetime] = None
    branch_mgr_signature: Optional[str] = None
    branch_mgr_signed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    # I1 — display names (populated by service via joined models)
    branch_name: Optional[str] = None
    branch_name_ar: Optional[str] = None
    branch_name_en: Optional[str] = None
    brand_name: Optional[str] = None
    visitor_name: Optional[str] = None
    branch_in_charge_name: Optional[str] = None
    reviewed_by_name: Optional[str] = None
    # I3 — attachments on the visit itself (not just per response)
    visit_attachments: List["QualityVisitAttachmentOut"] = []
    responses: List[QualityVisitResponseOut] = []
    model_config = {"from_attributes": True}


class QualityVisitSignRequest(BaseModel):
    """توقيع زيارة — نوع التوقيع (visitor|branch_manager) والاسم/البيانات"""
    role: str = Field(..., pattern="^(visitor|branch_manager)$")
    signature: str = Field(..., min_length=2, max_length=200)


class QualityVisitSummaryOut(BaseModel):
    id: int
    branch_id: int
    visitor_id: int
    visit_date: date
    shift: Optional[str] = None
    status: QualityVisitStatus
    compliance_pct: Optional[float] = None
    follow_up_date: Optional[date] = None
    created_at: datetime
    # I1 — display names for the list view
    branch_name: Optional[str] = None
    branch_name_ar: Optional[str] = None
    branch_name_en: Optional[str] = None
    visitor_name: Optional[str] = None
    model_config = {"from_attributes": True}


class QualityVisitListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[QualityVisitSummaryOut]


class QualityVisitReviewRequest(BaseModel):
    summary_notes: Optional[str] = None
    follow_up_date: Optional[date] = None


class QualityVisitResponseUpdate(BaseModel):
    """تحديث جزئي لرد واحد — للمراجع أو صاحب الإجراء"""
    status: Optional[QualityResponseStatus] = None
    numeric_value: Optional[Decimal] = None
    text_value: Optional[str] = None
    notes: Optional[str] = None
    corrective_action: Optional[str] = None
    action_owner: Optional[str] = None
    due_date: Optional[date] = None
    is_resolved: Optional[bool] = None


class QualityOpenActionOut(BaseModel):
    """إجراء تصحيحي مفتوح — يضم سياق الزيارة"""
    id: int
    visit_id: int
    branch_id: int
    visit_date: date
    item_id: int
    item: Optional[QualityVisitItemOut] = None
    corrective_action: Optional[str] = None
    action_owner: Optional[str] = None
    due_date: Optional[date] = None
    is_overdue: bool = False
    notes: Optional[str] = None
    model_config = {"from_attributes": True}


class BulkResolveRequest(BaseModel):
    response_ids: List[int] = Field(..., min_length=1, max_length=200)
    notes: Optional[str] = None


class BulkResolveResult(BaseModel):
    resolved: int
    skipped: int
    failed: List[int] = []


class SectionComplianceOut(BaseModel):
    """توزيع متوسط الالتزام حسب المحور (section)"""
    section_id: int
    section_name_ar: Optional[str] = None
    section_name_en: Optional[str] = None
    avg_compliance: float
    responses_count: int
    no_count: int


class ComplianceTrendPoint(BaseModel):
    month: str
    branch_id: int
    avg_compliance: float
    visits_count: int


class VerdictDistributionPoint(BaseModel):
    month: str
    verdict: str
    count: int


# ─── Training Assessment ──────────────────────
class TrainingTemplateItemOut(BaseModel):
    id: int
    section_id: int
    text_ar: str
    text_en: Optional[str] = None
    benchmark_ar: Optional[str] = None
    benchmark_en: Optional[str] = None
    order: int
    is_active: bool
    model_config = {"from_attributes": True}


class TrainingTemplateSectionOut(BaseModel):
    id: int
    template_id: int
    name_ar: str
    name_en: Optional[str] = None
    order: int
    weight: float
    items: List[TrainingTemplateItemOut] = []
    model_config = {"from_attributes": True}


class TrainingTemplateOut(BaseModel):
    id: int
    role_type: TrainingRoleType
    name_ar: str
    name_en: Optional[str] = None
    version: str
    is_active: bool
    created_at: datetime
    sections: List[TrainingTemplateSectionOut] = []
    model_config = {"from_attributes": True}


class TrainingTemplateSummaryOut(BaseModel):
    id: int
    role_type: TrainingRoleType
    name_ar: str
    name_en: Optional[str] = None
    version: str
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class TrainingAssessmentItemCreate(BaseModel):
    item_id: int
    score: int = Field(ge=1, le=5)
    notes: Optional[str] = None


class TrainingAssessmentCreate(BaseModel):
    template_id: int
    trainee_id: int
    trainer_id: int
    branch_id: int
    assessment_date: date
    items: List[TrainingAssessmentItemCreate] = []

    @field_validator("assessment_date")
    @classmethod
    def validate_date(cls, v):
        from datetime import date as date_type
        if v > date_type.today():
            raise ValueError("assessment_date cannot be in the future")
        return v


class TrainingAssessmentItemOut(BaseModel):
    id: int
    assessment_id: int
    item_id: int
    item: Optional[TrainingTemplateItemOut] = None
    score: int
    notes: Optional[str] = None
    model_config = {"from_attributes": True}


class TrainingDevelopmentPlanCreate(BaseModel):
    strengths: Optional[str] = None
    areas_for_improvement: Optional[str] = None
    required_actions: Optional[str] = None
    re_evaluation_date: Optional[date] = None


class TrainingDevelopmentPlanOut(BaseModel):
    id: int
    assessment_id: int
    strengths: Optional[str] = None
    areas_for_improvement: Optional[str] = None
    required_actions: Optional[str] = None
    re_evaluation_date: Optional[date] = None
    model_config = {"from_attributes": True}


class TrainingAssessmentOut(BaseModel):
    id: int
    template_id: int
    trainee_id: int
    trainer_id: int
    branch_id: int
    assessment_date: date
    status: AssessmentStatus
    overall_score: Optional[float] = None
    verdict: Optional[AssessmentVerdict] = None
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    re_eval_date: Optional[date] = None
    rejection_reason: Optional[str] = None
    # E8 — signatures
    evaluator_signature: Optional[str] = None
    evaluator_signed_at: Optional[datetime] = None
    approver_signature: Optional[str] = None
    approver_signed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    # H12: display fields (اسم الموظف والمقيّم والفرع والنوع)
    trainee_name: Optional[str] = None
    trainee_employee_no: Optional[str] = None
    trainer_name: Optional[str] = None
    branch_name: Optional[str] = None
    role_type: Optional[str] = None
    approver_name: Optional[str] = None
    template: Optional[TrainingTemplateSummaryOut] = None
    items: List[TrainingAssessmentItemOut] = []
    dev_plan: Optional[TrainingDevelopmentPlanOut] = None
    model_config = {"from_attributes": True}


class TrainingAssessmentSignRequest(BaseModel):
    """توقيع تقييم — evaluator (قبل الرفع) أو approver (عند الاعتماد)"""
    role: str = Field(..., pattern="^(evaluator|approver)$")
    signature: str = Field(..., min_length=2, max_length=200)


class TrainingAssessmentSummaryOut(BaseModel):
    id: int
    template_id: int
    trainee_id: int
    trainer_id: int
    branch_id: int
    assessment_date: date
    status: AssessmentStatus
    overall_score: Optional[float] = None
    verdict: Optional[AssessmentVerdict] = None
    re_eval_date: Optional[date] = None
    created_at: datetime
    # H12: enriched display fields — اسم الموظف والمدرب والفرع والدور
    trainee_name: Optional[str] = None
    trainee_employee_no: Optional[str] = None   # username يلعب دور الرقم الوظيفي
    trainer_name: Optional[str] = None
    branch_name: Optional[str] = None
    role_type: Optional[str] = None             # نوع الموظف (barista/cashier…)
    template_name: Optional[str] = None
    model_config = {"from_attributes": True}


class TrainingAssessmentListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[TrainingAssessmentSummaryOut]


class TrainingAssessmentApproveRequest(BaseModel):
    # إذا لم يُحدَّد، يُستنتج تلقائياً من الدرجة: ≥80 passed، 60-79 conditional، <60 failed
    verdict: Optional[AssessmentVerdict] = None
    re_eval_date: Optional[date] = None
    dev_plan: Optional[TrainingDevelopmentPlanCreate] = None


class TrainingAssessmentRejectRequest(BaseModel):
    reason: str


# --- Delivery Analytics ---
class DeliveryDashboardTotalsOut(BaseModel):
    total_revenue: float
    total_orders: int
    average_order_value: float
    active_branches: int
    active_apps: int


class DeliveryAppSummaryOut(BaseModel):
    delivery_app: str
    total_revenue: float
    total_orders: int
    average_order_value: float


class DeliveryBrandSummaryOut(BaseModel):
    brand_name: str
    total_revenue: float
    total_orders: int
    average_order_value: float


class DeliveryBranchSummaryOut(BaseModel):
    branch_id: int
    branch_name: str
    brand_name: str
    total_revenue: float
    total_orders: int
    average_order_value: float
    regular_hours: Optional[str] = None


class DeliveryTrendPointOut(BaseModel):
    label: str
    total_revenue: float
    total_orders: int
    average_order_value: float


class DeliveryDashboardOut(BaseModel):
    totals: DeliveryDashboardTotalsOut
    app_comparison: List[DeliveryAppSummaryOut]
    brand_performance: List[DeliveryBrandSummaryOut]
    top_branches: List[DeliveryBranchSummaryOut]
    monthly_trend: List[DeliveryTrendPointOut]


class DeliveryBranchProfileOut(BaseModel):
    id: int
    brand_name: str
    branch_name: str
    region: Optional[str] = None
    city: Optional[str] = None
    google_maps_url: Optional[str] = None
    regular_open_time: Optional[str] = None
    regular_close_time: Optional[str] = None
    weekend_open_time: Optional[str] = None
    weekend_close_time: Optional[str] = None
    hours_notes: Optional[str] = None
    is_active: bool
    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════════
# DELIVERY ANALYTICS SCHEMAS — قسم تحليل تطبيقات التوصيل
# ═══════════════════════════════════════════════════════════════

class DeliveryBrandOut(BaseModel):
    id: int
    name: str
    name_ar: Optional[str] = None
    is_active: bool
    model_config = {"from_attributes": True}


class DeliveryBranchAliasOut(BaseModel):
    id: int
    alias: str
    model_config = {"from_attributes": True}


class DeliveryBranchOut(BaseModel):
    id: int
    brand_id: int
    brand: Optional[DeliveryBrandOut] = None
    name: str
    region: Optional[str] = None
    regular_hours: Optional[str] = None
    weekend_hours: Optional[str] = None
    hours_notes: Optional[str] = None
    google_maps_url: Optional[str] = None
    is_active: bool
    aliases: List[DeliveryBranchAliasOut] = []
    model_config = {"from_attributes": True}


class DeliveryBranchCreate(BaseModel):
    brand_id: int
    name: str
    region: Optional[str] = None
    regular_hours: Optional[str] = None
    weekend_hours: Optional[str] = None
    hours_notes: Optional[str] = None
    google_maps_url: Optional[str] = None


class DeliveryBranchUpdate(BaseModel):
    name: Optional[str] = None
    region: Optional[str] = None
    regular_hours: Optional[str] = None
    weekend_hours: Optional[str] = None
    hours_notes: Optional[str] = None
    google_maps_url: Optional[str] = None
    is_active: Optional[bool] = None


class DeliveryAppOut(BaseModel):
    id: int
    name: str
    name_ar: Optional[str] = None
    is_active: bool
    model_config = {"from_attributes": True}


class DeliveryRecordImportRow(BaseModel):
    year:        int
    month:       int            # 1-12
    brand_name:  str
    branch_name: Optional[str] = ""   # قد يكون فارغاً
    app_name:    str
    orders:      int
    revenue:     float
    aov:         Optional[float] = None  # اختياري — يُحسب في الـ service

    @field_validator("month")
    @classmethod
    def validate_month(cls, v):
        if not 1 <= v <= 12:
            raise ValueError("month must be 1-12")
        return v

    @field_validator("orders")
    @classmethod
    def validate_orders(cls, v):
        if v < 0:
            raise ValueError("orders must be >= 0")
        return v

    @field_validator("revenue")
    @classmethod
    def validate_revenue(cls, v):
        if v < 0:
            raise ValueError("revenue must be >= 0")
        return v


class DeliveryImportRequest(BaseModel):
    batch_name: Optional[str] = None
    rows: List[DeliveryRecordImportRow]


class DeliveryImportResult(BaseModel):
    imported:   int
    skipped:    int
    unmatched:  int
    batch_id:   Optional[str] = None


class DeliveryRecordOut(BaseModel):
    id:              int
    year:            int
    month:           int
    brand_id:        int
    branch_id:       Optional[int] = None
    app_id:          int
    orders:          int
    revenue:         float
    aov:             Optional[float] = None
    raw_branch_name: Optional[str] = None
    raw_brand_name:  Optional[str] = None
    is_outlier:      bool
    import_batch:    Optional[str] = None
    model_config = {"from_attributes": True}


class DeliveryAliasCreate(BaseModel):
    alias: str


# ─── Analytics Schemas ────────────────────────────────────────────────────────

class DeliveryKPI(BaseModel):
    total_orders:    int
    total_revenue:   float
    avg_aov:         Optional[float]
    top_app:         Optional[str]
    top_app_orders:  Optional[int]
    top_brand:       Optional[str]
    top_branch:      Optional[str]


class DeliveryAppStat(BaseModel):
    app_id:    int
    app_name:  str
    orders:    int
    revenue:   float
    avg_aov:   Optional[float]
    share_pct: Optional[float]


class DeliveryBrandStat(BaseModel):
    brand_id:  int
    brand_name:str
    orders:    int
    revenue:   float
    avg_aov:   Optional[float]
    share_pct: Optional[float]


class DeliveryBranchStat(BaseModel):
    branch_id:       Optional[int]
    branch_name:     Optional[str]
    brand_name:      Optional[str]
    orders:          int
    revenue:         float
    avg_aov:         Optional[float]
    google_maps_url: Optional[str]


class DeliveryMonthlyTrend(BaseModel):
    year:    int
    month:   int
    orders:  int
    revenue: float


class DeliveryAppBranchEntry(BaseModel):
    branch_id:   Optional[int]
    branch_name: Optional[str]
    orders:      int
    revenue:     float


class DeliveryAppBranchMatrix(BaseModel):
    app_id:   int
    app_name: str
    branches: List[DeliveryAppBranchEntry]


class DeliveryUnmatchedBranch(BaseModel):
    raw_name: str
    count:    int


# ─── Documents (Phase F3) ─────────────────────────────────
class DocumentCreate(BaseModel):
    owner_type: DocumentOwnerType
    branch_id: Optional[int] = None
    user_id: Optional[int] = None
    doc_type: DocumentType
    title: str = Field(..., min_length=1, max_length=200)
    issuer: Optional[str] = Field(None, max_length=150)
    doc_number: Optional[str] = Field(None, max_length=100)
    issue_date: Optional[date] = None
    expiry_date: date
    reminder_days: int = Field(default=30, ge=1, le=365)
    notes: Optional[str] = None

    @model_validator(mode="after")
    def _owner_ref_matches_type(self):
        if self.owner_type == DocumentOwnerType.branch:
            if not self.branch_id or self.user_id:
                raise ValueError("branch documents must set branch_id and leave user_id null")
        elif self.owner_type == DocumentOwnerType.employee:
            if not self.user_id or self.branch_id:
                raise ValueError("employee documents must set user_id and leave branch_id null")
        return self

    @model_validator(mode="after")
    def _dates_sane(self):
        if self.issue_date and self.expiry_date and self.issue_date > self.expiry_date:
            raise ValueError("issue_date cannot be after expiry_date")
        return self


class DocumentUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    issuer: Optional[str] = Field(None, max_length=150)
    doc_number: Optional[str] = Field(None, max_length=100)
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    reminder_days: Optional[int] = Field(None, ge=1, le=365)
    notes: Optional[str] = None


class DocumentRenew(BaseModel):
    """تجديد الوثيقة: ننشئ وثيقة جديدة بنفس الخصائص + تواريخ جديدة، ونرشف القديمة."""
    new_issue_date: Optional[date] = None
    new_expiry_date: date
    new_doc_number: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None


class DocumentOut(BaseModel):
    id: int
    owner_type: DocumentOwnerType
    branch_id: Optional[int] = None
    user_id: Optional[int] = None
    doc_type: DocumentType
    title: str
    issuer: Optional[str] = None
    doc_number: Optional[str] = None
    issue_date: Optional[date] = None
    expiry_date: date
    reminder_days: int
    file_path: Optional[str] = None
    file_name: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    notes: Optional[str] = None
    is_archived: bool
    renewed_from_id: Optional[int] = None
    last_reminder_at: Optional[datetime] = None
    uploaded_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    # denormalized helpers for the UI
    days_until_expiry: Optional[int] = None
    status: Optional[str] = None   # valid | due_soon | expired | archived
    branch_name: Optional[str] = None
    user_full_name: Optional[str] = None

    model_config = {"from_attributes": True}


class DocumentExpirySummary(BaseModel):
    total: int
    expired: int
    due_soon: int      # within reminder window
    valid: int


# ─── System Settings ──────────────────────────
class SystemSettingOut(BaseModel):
    id: int
    key: str
    value: str
    description: Optional[str] = None
    updated_at: datetime
    updated_by: Optional[int] = None
    updated_by_name: Optional[str] = None

    model_config = {"from_attributes": True}


class SystemSettingUpdate(BaseModel):
    value: str


class SystemSettingsBulkUpdate(BaseModel):
    # { "days_of_cover_target": "3", ... } — values may be JSON strings or numbers (coerced to str by the router)
    settings: dict


# ─── Shift Operations ────────────────────────────────────────────────────────
class ShiftOpenPayload(BaseModel):
    branch_id: Optional[int] = None
    shift_date: date
    shift_number: int = Field(..., ge=1, le=3)
    override: bool = False
    override_reason: Optional[str] = Field(None, max_length=300)


class ShiftReopenPayload(BaseModel):
    target: str = Field(..., pattern="^(count|cash|both)$")
    reason: str = Field(..., min_length=5, max_length=300)
    admin_override: bool = False


class ShiftCloseNoActivityPayload(BaseModel):
    exception_type: str = Field(..., pattern="^(branch_closed|manual_gap)$")
    reason: str = Field(..., min_length=5, max_length=300)


class ShiftCountLinePatch(BaseModel):
    item_id: int
    received_qty: Optional[float] = None
    returned_qty: Optional[float] = None
    damaged_qty: Optional[float] = None
    closing_balance: Optional[float] = None
    movement_exception_reason: Optional[str] = Field(None, max_length=300)
    item_notes: Optional[str] = None


class ShiftCountLinesPatchPayload(BaseModel):
    lines: list[ShiftCountLinePatch]


class ShiftOpsCashSavePayload(BaseModel):
    total_sale: Optional[float] = None
    bill_count: Optional[int] = None
    mada_sales: Optional[float] = None
    cash_sales: Optional[float] = None
    app_sales: Optional[float] = None
    refund_bill: Optional[float] = None
    exchange_amount: Optional[float] = None
    expiry_amount: Optional[float] = None
    cash_expense: Optional[float] = None
    cash_float_carried_forward: Optional[float] = None
    cash_deposited: Optional[float] = None
    expense_type: Optional[str] = None
    expense_details: Optional[str] = Field(None, max_length=300)
    shift_notes: Optional[str] = None
    cash_variance_reason: Optional[str] = Field(None, max_length=300)

