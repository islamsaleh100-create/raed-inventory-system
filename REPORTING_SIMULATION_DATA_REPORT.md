# Reporting Simulation Data Report

**Generated:** 2026-06-16T10:57:15 UTC  
**Database:** `raed_inventory` (dev/simulation only)  
**Date range:** 2026-01-01 → 2026-06-16  
**Seed:** 20260616

---

## 1. Safety Checks

| Check | Result |
|-------|--------|
| `--i-understand-this-is-simulation` | Required and confirmed |
| PostgreSQL only | PASS |
| Forbidden DB names blocked | PASS |
| Service-layer workflow (no HTTP bulk) | PASS |
| Timestamp backdating | SQL in script only |

---

## 2. Date Range

```text
2026-01-01 to 2026-06-16
```

---

## 3. Seed Used

```text
20260616
```

---

## 4. Branches Covered

Official active branches (BR-%): **23** (total seeded: **31**)  
Branch profiles with users: **24** (multi-brand branches may have >1 profile)  
Unique branches with activity: **24** / **23**

Note: Griddle-only branches (`BR-*-GRI-*`) have no dedicated branch login; Griddle items are simulated via multi-brand branch **Shawarma Olaya** (`BR-RY-SH-OLAYA`).

Name mapping (spec → DB):

- Onda 1 - ARKAN → Onda Arkan (BR-DM-ON-ARKAN)
- Pizza 1 - AlKHOBAR → Ronaldos Al Khobar (BR-DM-RN-KHOBR)
- ONDA DAU University → Onda DAU University (BR-DM-ON-DAU)
- Ronaldos DAU University → Ronaldos DAU University (BR-DM-RN-DAU)
- Onda 14 - HASSA → Onda Hassa (BR-DM-ON-HASSA)
- Onda 16 - Najmah → Onda Najmah (BR-DM-ON-NAJMA)
- Pizza 4 - Riyadh Takhasosy → Ronaldos Riyadh Takhasosy (BR-RY-RN-TAKHS)
- Pizza 6 - Riyadh Nada → Ronaldos Riyadh Nada (BR-RY-RN-NADA)
- Onda 18 - Al Midra Gym → Onda Al Midra Gym (BR-DM-ON-MIDRA)
- Onda 9 - Ras Tanura → Onda Ras Tanura (BR-DM-ON-RASTN)
- Pizza 15 - Ras Tanura → Ronaldos Ras Tanura (BR-DM-RN-RASTN)

---

## 5. Items Covered

Requestable items in master: **135**  
Items appearing in this run: **135**  
Simulated opening stock rows touched: **60**

---

## 6. Total Requests Generated

| Metric | This run | DB total |
|--------|----------|----------|
| Branch requests | 5,288 | 5,288 |
| Rejections | 33 | 33 |

---

## 7. Requests By Month

- 2026-01: 443
- 2026-02: 188
- 2026-03: 729
- 2026-04: 1,543
- 2026-05: 1,307
- 2026-06: 1,078

---

## 8. Requests By Branch

- BR-DM-ON-ARKAN: 973
- BR-DM-ON-DAU: 709
- BR-DM-RN-DAU: 668
- BR-DM-RN-KHOBR: 657
- BR-RY-RN-TAKHS: 350
- BR-DM-ON-HASSA: 328
- BR-DM-ON-NAJMA: 319
- BR-DM-ON-MIDRA: 184
- BR-DM-RN-RASTN: 164
- BR-DM-ON-RASTN: 157
- BR-DM-RN-ARAMC: 124
- BR-DM-SH-ARKAN: 100
- BR-RY-ON-MALQA: 94
- BR-DM-SH-KHOBR: 62
- BR-DM-ON-HOQAI: 58
- BR-RY-SH-OLAYA: 56
- BR-DM-RN-MAZAR: 47
- BR-DM-ON-MUOWA: 45
- BR-RY-RN-NADA: 44
- BR-RY-RN-ULAYA: 42
- BR-DM-RN-AZIZI: 38
- BR-RY-ON-SEFAR: 35
- BR-DM-RN-ARKAN: 33
- BR-RY-RON-1: 1

---

## 9. Requests By Brand

- Onda: 2,902
- Ronaldos: 2,168
- Shawarma: 201
- Griddle: 17

---

## 10. Requests By City

- Dammam: 4,666
- Riyadh: 622

---

## 11. Status Distribution

### Branch requests
- BranchRequestStatus.DRAFT: 15
- BranchRequestStatus.SUBMITTED: 61
- BranchRequestStatus.AREA_REJECTED: 33
- BranchRequestStatus.SPLIT: 700
- BranchRequestStatus.IN_EXECUTION: 660
- BranchRequestStatus.DELIVERED: 3,819

### Production orders
- ProductionOrderStatus.PENDING: 18
- ProductionOrderStatus.IN_PROGRESS: 475
- ProductionOrderStatus.SENT_TO_WAREHOUSE: 3,914

### Warehouse lines
- WarehouseLineStatus.PENDING: 75
- WarehouseLineStatus.AVAILABLE: 96
- WarehouseLineStatus.PARTIAL: 267
- WarehouseLineStatus.BACKORDER: 453
- WarehouseLineStatus.READY_FOR_DISPATCH: 104
- WarehouseLineStatus.DELIVERED: 6,036

### Delivery orders
- DeliveryOrderStatus.DELIVERED: 6,035
- DeliveryOrderStatus.OUT_FOR_DELIVERY: 25
- DeliveryOrderStatus.READY: 60
- DeliveryOrderStatus.PARTIAL_DELIVERED: 207

### Sim run outcome tags


---

## 12. Production Orders Generated

This run: **0** | DB total: **4,407** | IN_PROGRESS: **475**

---

## 13. Warehouse Lines Generated

This run: **0** | DB total: **7,031**

---

## 14. Deliveries Generated

This run: **0** | DB total: **6,327**

---

## 15. Partial Fulfillment Count

Sim partial issues: **0** | DB PARTIAL lines: **267**

---

## 16. Backorder Count

Sim backorders: **0** | DB BACKORDER lines: **453**

---

## 17. Delivery Shortage Count

Sim shortages: **0** | DB PARTIAL_DELIVERED orders: **207**

---

## 18. Delay Reasons Summary



---

## 19. Top 20 Items

1. 7UP سفن اب — 461
2. كولا زيرو Cola Zero — 153
3. سبرايت SPRITE — 147
4. فانتا حمضياتFanta Citruse — 138
5. بيبسي دايت — 138
6. بيبسي — 136
7. كولا قزاز Cola Glass — 135
8. كولا لايت COLA LIGHT — 134
9. فانتا برتقالFanta Orange — 130
10. فانتا فراولةFanta Strawberry — 127
11. ديو DEW — 126
12. كولا COLA CAN — 123
13. سفن اب دايت — 120
14. ماء water — 119
15. ميرندا برتقال — 119
16. double chocolate cake دبل شوكلت كيك — 114
17. كوكيز Cookies — 103
18. ميرندا حمضيات — 101
19. كرواسون تركي جبن  Turkey Cheddar Croissant — 98
20. ماريتوزي Maritozzo — 93

---

## 20. Audit Events

DB total audit logs: **59,704**

---

## 21. Notifications

Notifications are computed live from workflow state via `GET /api/v1/notifications/summary` (no separate notification table). Supply-chain sections populate when pending approvals, warehouse lines, and deliveries exist.

---

## 22. Integrity Validation Results

```text
pytest tests/test_reporting_simulation_data.py -v
REPORTING_SIM_SKIP=1 REPORTING_SIM_START=2026-01-01 REPORTING_SIM_END=2026-06-16
RATE_LIMIT_ENABLED=false
→ 10 passed
```

Checks: no orphan lines/orders, no negative stock, all official branches active, all requestable items represented, audit events present, dashboard endpoints non-empty.

---

## 23. Performance Snapshot

| Endpoint / query | ms |
|------------------|-----|
| db_count_branch_requests_ms | 0.6 |
| db_count_warehouse_lines_ms | 3.9 |
| db_count_delivery_orders_ms | 3.1 |
| db_count_audit_logs_ms | 6.9 |
| supply_chain_dashboard_ms | 49.2 |
| dashboard_global_ms | 21.2 |
| warehouse_lines_ms | 2084.4 |
| branch_requests_ms | 37.7 |
| delivery_orders_ms | 2489.1 |
| notifications_summary_ms | 64.2 |

---

## 24. Remaining Data Gaps

- Inactive branch `BR-RY-RON-1` retains legacy requests from an earlier simulation run (24 distinct branch IDs vs 23 active official branches).
- Griddle dedicated branches (`BR-RY-GRI-1`, `BR-DM-GRI-1`) have no branch login users; Griddle demand is routed through **Shawarma Olaya** multi-brand profile.
- Warehouse/delivery list endpoints are slow (~2–3s) on full dataset; documented only, not optimized.

---

## 25. Report Readiness Verdict

**REPORTS_READY**

Local dev database `raed_inventory` now contains Jan–Jun 2026 backdated operational history suitable for dashboard and report review. **Do not use this database for LAN trial or production.**

