# RAED INVENTORY SYSTEM — PAGE SPECIFICATION INDEX

## Document Control

| Field | Value |
|---|---|
| Parent plan | `RAED_INVENTORY_MASTER_PLAN.md` |
| Date created | 2026-07-13 |
| Purpose | Live tracker for PAGE 01–80 review and approval |
| Status | ACTIVE |
| Code implementation | **NOT AUTHORIZED** |
| Authorized database | `localhost:5432/raed_inventory` only |
| Current page | PAGE 01 — **APPROVED** |

> Before creating or changing test data, Preflight must confirm the effective Backend connection is exactly `localhost:5432/raed_inventory`. If any other database is detected, including `raed_lan_trial`, stop and request explicit approval.

---

## Status Lifecycle

```text
NOT_STARTED
→ IN_REVIEW
→ DISCUSSION_REQUIRED
→ APPROVED
→ TECHNICAL_DEPENDENCY
→ READY_FOR_IMPLEMENTATION_PLANNING
```

## Review Values

```text
PENDING
PASS
FAIL
PARTIAL
NOT_APPLICABLE
```

---

## Group A — Core Supply Chain

| Page ID | Page Name | Route | Group | Current Status | Browser Review | Code Review | Security Review | Target Design | Open Questions | Decision | Dependencies | Specification File | Approval Date |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PAGE 01 | قائمة طلبات التوريد | `/supply-chain/branch-requests` | A — Core Supply Chain | **APPROVED** | PASS | PASS | PASS | APPROVED | — | APPROVED | Role Matrix; PD-01/02/03 | `PAGE_SPEC_01_supply_chain_branch_requests.md` | 2026-07-13 |
| PAGE 02 | إنشاء طلب توريد | `/supply-chain/branch-requests/new` or approved in-page action | A — Core Supply Chain | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | OQ-01 | PENDING | PAGE 01; PD-01/02/03 | `PAGE_SPEC_02_create_supply_request.md` | — |
| PAGE 03 | تفاصيل الطلب والـTimeline | Detail route to confirm | A — Core Supply Chain | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | OQ-01 | PENDING | PAGE 01–02; State Machine | `PAGE_SPEC_03_supply_request_details.md` | — |
| PAGE 04 | قائمة اعتماد طلبات الفروع | `/supply-chain/approvals` | A — Core Supply Chain | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | OQ-01; OQ-03 | PENDING | PAGE 01–03 | `PAGE_SPEC_04_area_approval_list.md` | — |
| PAGE 05 | تفاصيل الاعتماد والرفض | Detail/action route to confirm | A — Core Supply Chain | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | OQ-01; OQ-03 | PENDING | PAGE 04 | `PAGE_SPEC_05_area_approval_details.md` | — |
| PAGE 06 | قائمة أوامر الإنتاج | `/supply-chain/kitchen` | A — Core Supply Chain | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | Auto Split; KITCHEN-RUNTIME-01 | `PAGE_SPEC_06_kitchen_orders.md` | — |
| PAGE 07 | تفاصيل أمر الإنتاج | Detail route to confirm | A — Core Supply Chain | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | PAGE 06; KITCHEN-RUNTIME-01 | `PAGE_SPEC_07_kitchen_order_details.md` | — |
| PAGE 08 | قائمة تنفيذ المستودع | `/supply-chain/warehouse` | A — Core Supply Chain | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | PAGE 06–07; FIX-WH-01 | `PAGE_SPEC_08_warehouse_execution.md` | — |
| PAGE 09 | تفاصيل التجهيز والصرف | Detail route to confirm | A — Core Supply Chain | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | PAGE 08; WH-SEC-01 | `PAGE_SPEC_09_warehouse_execution_details.md` | — |
| PAGE 10 | قائمة أوامر التوصيل | `/supply-chain/delivery` | A — Core Supply Chain | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | PAGE 08–09; PD-04/05/06 | `PAGE_SPEC_10_delivery_orders.md` | — |
| PAGE 11 | Claim وتفاصيل التسليم | Detail route to confirm | A — Core Supply Chain | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | PAGE 10; PD-04/05/06 | `PAGE_SPEC_11_delivery_claim_and_details.md` | — |
| PAGE 12 | متابعة سلسلة الإمداد | `/supply-chain/control` | A — Core Supply Chain | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | OQ-02 | PENDING | Pages 01–11; New Component | `PAGE_SPEC_12_supply_chain_control.md` | — |
| PAGE 13 | لوحة العمليات | `/operations` | A — Core Supply Chain | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | Operations Role Scope | `PAGE_SPEC_13_operations_dashboard.md` | — |
| PAGE 14 | لوحة التحكم الرئيسية | `/dashboard` | A — Core Supply Chain | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | Role Dashboards | `PAGE_SPEC_14_dashboard.md` | — |
| PAGE 15 | الإشعارات | `/notifications` | A — Core Supply Chain | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | OQ-02 | PENDING | Notification Schema; SLA | `PAGE_SPEC_15_notifications.md` | — |

---

## Group B — Inventory and Transfers

| Page ID | Page Name | Route | Group | Current Status | Browser Review | Code Review | Security Review | Target Design | Open Questions | Decision | Dependencies | Specification File | Approval Date |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PAGE 16 | سجل الجرد اليومي | `/inventory` | B — Inventory and Transfers | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | Branch Scope | `PAGE_SPEC_16_daily_inventory_records.md` | — |
| PAGE 17 | إدخال جرد اليوم | `/inventory/new` | B — Inventory and Transfers | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | PAGE 16 | `PAGE_SPEC_17_daily_inventory_entry.md` | — |
| PAGE 18 | تفاصيل وتعديل الجرد | `/inventory/:id` | B — Inventory and Transfers | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | PAGE 16–17 | `PAGE_SPEC_18_inventory_details.md` | — |
| PAGE 19 | مراجعة الجرد اليومي | `/reports/inventory` | B — Inventory and Transfers | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | Component Rebuild Required | `PAGE_SPEC_19_inventory_review.md` | — |
| PAGE 20 | أرصدة الفروع | `/branch-stock` | B — Inventory and Transfers | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | Branch/Area Scope | `PAGE_SPEC_20_branch_balances.md` | — |
| PAGE 21 | أرصدة المستودعات | `/warehouse/stock` | B — Inventory and Transfers | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | FIX-WH-02/03; WH-SEC-01 | `PAGE_SPEC_21_warehouse_balances.md` | — |
| PAGE 22 | حركات المخزون | New module/route | B — Inventory and Transfers | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | Data Model; Ledger | `PAGE_SPEC_22_stock_movements.md` | — |
| PAGE 23 | جلسات الجرد الفعلي | New module/route | B — Inventory and Transfers | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | Physical Inventory Models | `PAGE_SPEC_23_physical_inventory_sessions.md` | — |
| PAGE 24 | إنشاء وتنفيذ جلسة جرد | New action/route | B — Inventory and Transfers | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | PAGE 23 | `PAGE_SPEC_24_physical_inventory_execution.md` | — |
| PAGE 25 | مراجعة الفروقات واعتماد التسوية | New workflow/route | B — Inventory and Transfers | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | PAGE 23–24; Adjustment Workflow | `PAGE_SPEC_25_inventory_adjustment_review.md` | — |
| PAGE 26 | قائمة تحويلات الفروع | `/stock/inter-branch-transfer` | B — Inventory and Transfers | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | Transfer Workflow | `PAGE_SPEC_26_inter_branch_transfers.md` | — |
| PAGE 27 | إنشاء طلب تحويل | In-page action/route to confirm | B — Inventory and Transfers | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | PAGE 26 | `PAGE_SPEC_27_create_transfer_request.md` | — |
| PAGE 28 | اعتماد التحويل | `/operations/inter-branch-approvals` | B — Inventory and Transfers | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | PAGE 26–27 | `PAGE_SPEC_28_transfer_approval.md` | — |
| PAGE 29 | تنفيذ التحويل والاستلام | Workflow/route to confirm | B — Inventory and Transfers | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | PAGE 28; WH-XFER-01 | `PAGE_SPEC_29_transfer_execution.md` | — |

---

## Group C — Internal Audit

| Page ID | Page Name | Route | Group | Current Status | Browser Review | Code Review | Security Review | Target Design | Open Questions | Decision | Dependencies | Specification File | Approval Date |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PAGE 30 | لوحة المراجعة | `/audit/dashboard` | C — Internal Audit | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | Audit Read Scope | `PAGE_SPEC_30_audit_dashboard.md` | — |
| PAGE 31 | مراجعة الطلبيات: اليوم والسجل | `/audit/orders?tab=today|history` target | C — Internal Audit | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | Redirects from old audit routes | `PAGE_SPEC_31_audit_order_review.md` | — |
| PAGE 32 | مراجعة مخزون المستودعات | `/audit/warehouse-stock` | C — Internal Audit | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | Read-only Backend | `PAGE_SPEC_32_audit_warehouse_stock.md` | — |
| PAGE 33 | طلبات تغيير الأصناف | `/audit/item-change-requests` | C — Internal Audit | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | Audit Workflow | `PAGE_SPEC_33_audit_item_change_requests.md` | — |
| PAGE 34 | ملاحظات التدقيق | `/audit/findings` | C — Internal Audit | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | ADM-03; Findings Workflow | `PAGE_SPEC_34_audit_findings.md` | — |
| PAGE 35 | سجل العمليات | `/audit/trail` | C — Internal Audit | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | Append-only Trail | `PAGE_SPEC_35_audit_trail.md` | — |
| PAGE 36 | مراجعة حركات المخزون | New with PAGE 22 | C — Internal Audit | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | PAGE 22 | `PAGE_SPEC_36_audit_stock_movements.md` | — |
| PAGE 37 | مراجعة الجرد والتسويات | New with PAGE 23–25 | C — Internal Audit | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | PAGE 23–25 | `PAGE_SPEC_37_audit_physical_inventory.md` | — |

---

## Group D — Sales Channels

| Page ID | Page Name | Route | Group | Current Status | Browser Review | Code Review | Security Review | Target Design | Open Questions | Decision | Dependencies | Specification File | Approval Date |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PAGE 38 | لوحة قنوات المبيعات | `/delivery` | D — Sales Channels | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | Sales Scope | `PAGE_SPEC_38_sales_channels_dashboard.md` | — |
| PAGE 39 | الإدخالات اليومية | `/delivery/daily-entry` | D — Sales Channels | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | SM-01 | `PAGE_SPEC_39_sales_daily_entries.md` | — |
| PAGE 40 | كشوف الحسابات | `/delivery/statements` | D — Sales Channels | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | Statement Workflow | `PAGE_SPEC_40_sales_statements.md` | — |
| PAGE 41 | التسوية | `/delivery/reconciliation` | D — Sales Channels | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | Read-only Auditor Access | `PAGE_SPEC_41_sales_reconciliation.md` | — |
| PAGE 42 | المعاملات غير المطابقة | `/delivery/unmatched` | D — Sales Channels | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | SM-02 | `PAGE_SPEC_42_unmatched_transactions.md` | — |
| PAGE 43 | الإغلاقات | `/delivery/closures` | D — Sales Channels | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | Close/Reopen Audit | `PAGE_SPEC_43_sales_closures.md` | — |
| PAGE 44 | الالتزام | `/delivery/compliance` | D — Sales Channels | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | Auditor Read Access | `PAGE_SPEC_44_sales_compliance.md` | — |
| PAGE 45 | أداء الفروع | `/delivery/branch-stats` | D — Sales Channels | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | Global/Area Scope | `PAGE_SPEC_45_sales_branch_performance.md` | — |
| PAGE 46 | أداء البراندات | `/delivery/brands` | D — Sales Channels | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | Global/Area Scope | `PAGE_SPEC_46_sales_brand_performance.md` | — |
| PAGE 47 | استيراد البيانات | `/delivery/import` | D — Sales Channels | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | Import Validation | `PAGE_SPEC_47_sales_import.md` | — |
| PAGE 48 | إدارة فروع التوصيل | `/delivery/branches` | D — Sales Channels | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | Sales Manager CRUD | `PAGE_SPEC_48_delivery_branch_management.md` | — |
| PAGE 49 | إعدادات القنوات والعمولات | `/admin/sales-channels` | D — Sales Channels | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | SM-03 | `PAGE_SPEC_49_sales_channel_settings.md` | — |

---

## Group E — Quality and Training

| Page ID | Page Name | Route | Group | Current Status | Browser Review | Code Review | Security Review | Target Design | Open Questions | Decision | Dependencies | Specification File | Approval Date |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PAGE 50 | قائمة زيارات الجودة | `/quality` | E — Quality and Training | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | QV-03/04; Inspector Assignments | `PAGE_SPEC_50_quality_visits.md` | — |
| PAGE 51 | إنشاء زيارة جودة | `/quality/new` | E — Quality and Training | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | PD-07; FIX-QV-04 | `PAGE_SPEC_51_create_quality_visit.md` | — |
| PAGE 52 | تفاصيل ومراجعة الزيارة | `/quality/:id` | E — Quality and Training | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | FIX-QV-02/03 | `PAGE_SPEC_52_quality_visit_details.md` | — |
| PAGE 53 | الإجراءات التصحيحية المفتوحة | `/quality/open-actions` | E — Quality and Training | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | QV-01; Scope | `PAGE_SPEC_53_quality_open_actions.md` | — |
| PAGE 54 | تحليلات الجودة | `/quality/analytics` | E — Quality and Training | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | QM-01; OP-QA-01 | `PAGE_SPEC_54_quality_analytics.md` | — |
| PAGE 55 | التقييمات التدريبية وإنشاء تقييم | `/training`, `/training/new` | E — Quality and Training | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | Training Scope | `PAGE_SPEC_55_training_evaluations.md` | — |
| PAGE 56 | تحليلات التدريب | `/training/analytics` | E — Quality and Training | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | Auditor Read-only | `PAGE_SPEC_56_training_analytics.md` | — |

---

## Group F — Documents and Analytics

| Page ID | Page Name | Route | Group | Current Status | Browser Review | Code Review | Security Review | Target Design | Open Questions | Decision | Dependencies | Specification File | Approval Date |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PAGE 57 | قائمة الوثائق | `/documents` | F — Documents and Analytics | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | Role Scope | `PAGE_SPEC_57_documents.md` | — |
| PAGE 58 | إنشاء وتفاصيل الوثيقة | `/documents/new` and detail route | F — Documents and Analytics | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | PAGE 57 | `PAGE_SPEC_58_document_form_and_details.md` | — |
| PAGE 59 | الوثائق المقاربة للانتهاء | `/documents/expiring` | F — Documents and Analytics | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | Role Scope | `PAGE_SPEC_59_expiring_documents.md` | — |
| PAGE 60 | تقارير الطلبيات | `/reports/orders` | F — Documents and Analytics | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | Operations Scope | `PAGE_SPEC_60_order_reports.md` | — |
| PAGE 61 | اتجاه الاستهلاك | `/analytics/consumption-trend` | F — Documents and Analytics | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | Analytics Scope | `PAGE_SPEC_61_consumption_trend.md` | — |
| PAGE 62 | تأخر الطلبات | `/analytics/order-delay` | F — Documents and Analytics | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | Analytics Scope | `PAGE_SPEC_62_order_delay.md` | — |
| PAGE 63 | الإجراءات التصحيحية للفروع | `/analytics/branches-open-actions` | F — Documents and Analytics | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | Quality Scope | `PAGE_SPEC_63_branch_corrective_actions.md` | — |

---

## Group G — Administration

| Page ID | Page Name | Route | Group | Current Status | Browser Review | Code Review | Security Review | Target Design | Open Questions | Decision | Dependencies | Specification File | Approval Date |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PAGE 64 | المستخدمون والصلاحيات | `/admin/users` | G — Administration | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | ADM-06 | `PAGE_SPEC_64_users_and_permissions.md` | — |
| PAGE 65 | الفروع | `/admin/branches` | G — Administration | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | Global Admin | `PAGE_SPEC_65_admin_branches.md` | — |
| PAGE 66 | موظفو الفروع | `/branch-employees` | G — Administration | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | Branch/Admin Scope | `PAGE_SPEC_66_branch_employees.md` | — |
| PAGE 67 | المستودعات | `/admin/warehouses` | G — Administration | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | Global Admin | `PAGE_SPEC_67_admin_warehouses.md` | — |
| PAGE 68 | المطابخ وأقسام الإنتاج | `/admin/kitchens` | G — Administration | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | Kitchen Assignments | `PAGE_SPEC_68_admin_kitchens.md` | — |
| PAGE 69 | الأصناف | `/admin/items` | G — Administration | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | Item Types; Routing | `PAGE_SPEC_69_admin_items.md` | — |
| PAGE 70 | ربط الأصناف بالفروع | `/operations/branch-items` | G — Administration | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | Branch Item Scope | `PAGE_SPEC_70_branch_item_mapping.md` | — |
| PAGE 71 | اقتراحات المساعد | `/admin/suggestions` | G — Administration | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | Stability-first Rule | `PAGE_SPEC_71_assistant_suggestions.md` | — |
| PAGE 72 | إعدادات النظام | `/admin/settings` | G — Administration | NOT_STARTED | PENDING | PENDING | PENDING | PENDING | — | PENDING | Global Settings | `PAGE_SPEC_72_system_settings.md` | — |

---

## Group H — Previous System — Functional Review Only

| Page ID | Page Name | Route | Group | Current Status | Browser Review | Code Review | Security Review | Target Design | Open Questions | Decision | Dependencies | Specification File | Approval Date |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PAGE 73 | طلبات الفروع القديمة | `/orders` | H — Previous System | NOT_STARTED | PENDING | PENDING | PENDING | FROZEN | — | PENDING | ADM-04 | `PAGE_SPEC_73_legacy_branch_orders.md` | — |
| PAGE 74 | الطلبية اليومية القديمة | `/orders/daily` | H — Previous System | NOT_STARTED | PENDING | PENDING | PENDING | FROZEN | — | PENDING | ADM-04 | `PAGE_SPEC_74_legacy_daily_order.md` | — |
| PAGE 75 | الطلب الاستثنائي القديم | `/orders/exceptional` | H — Previous System | NOT_STARTED | PENDING | PENDING | PENDING | FROZEN | — | PENDING | ADM-04 | `PAGE_SPEC_75_legacy_exceptional_order.md` | — |
| PAGE 76 | الاستلامات القديمة | `/receiving` | H — Previous System | NOT_STARTED | PENDING | PENDING | PENDING | FROZEN | — | PENDING | ADM-04 | `PAGE_SPEC_76_legacy_receiving.md` | — |
| PAGE 77 | طلبيات المستودع القديمة | `/warehouse/orders` | H — Previous System | NOT_STARTED | PENDING | PENDING | PENDING | FROZEN | — | PENDING | ADM-04 | `PAGE_SPEC_77_legacy_warehouse_orders.md` | — |
| PAGE 78 | التجهيز القديم | `/warehouse/picking` | H — Previous System | NOT_STARTED | PENDING | PENDING | PENDING | FROZEN | — | PENDING | ADM-04 | `PAGE_SPEC_78_legacy_warehouse_picking.md` | — |
| PAGE 79 | الصرف القديم | `/warehouse/dispatch` | H — Previous System | NOT_STARTED | PENDING | PENDING | PENDING | FROZEN | — | PENDING | ADM-04 | `PAGE_SPEC_79_legacy_warehouse_dispatch.md` | — |
| PAGE 80 | تقارير المستودع القديمة | `/warehouse/reports` | H — Previous System | NOT_STARTED | PENDING | PENDING | PENDING | FROZEN | — | PENDING | ADM-04 | `PAGE_SPEC_80_legacy_warehouse_reports.md` | — |

---

## Summary

| Metric | Count |
|---|---:|
| Total tracked pages | 80 |
| IN_REVIEW | 0 |
| NOT_STARTED | 79 |
| APPROVED | 1 |
| READY_FOR_IMPLEMENTATION_PLANNING | 0 |

## Current Authorization

```text
PAGE 01 REVIEW: COMPLETED
PAGE 02 REVIEW: NOT YET AUTHORIZED
APPLICATION CODE CHANGES: NOT AUTHORIZED
SCHEMA/MIGRATION/SEED CHANGES: NOT AUTHORIZED
```

## Immediate Next Output

```text
PAGE_SPEC_01_supply_chain_branch_requests.md
```
