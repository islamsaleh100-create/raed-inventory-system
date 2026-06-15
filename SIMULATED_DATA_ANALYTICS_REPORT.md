# Simulated Data & Analytics Report — Phase 8

**Generated:** 2026-06-15  
**Simulation window:** 2026-03-18 → 2026-06-15

---

## 1. Data Generated

| Entity | Sim run | DB total |
|--------|---------|----------|
| Branch requests | 3,483 | 3,742 |
| Production orders | 3,101 | 3,177 |
| Warehouse lines | 4,994 | 5,228 |
| Deliveries | 4,609 | 4,739 |
| Audit entries | — | 45,500 |

Notifications are generated through workflow audit/notification hooks (not inserted manually).

---

## 2. Distribution

### By Branch (sim run)
- BR-DM-ON-DAU: 605
- BR-DM-RN-DAU: 553
- BR-DM-RN-KHOBR: 549
- BR-DM-ON-ARKAN: 512
- BR-RY-RN-TAKHS: 288
- BR-DM-ON-NAJMA: 275
- BR-DM-ON-HASSA: 266
- BR-DM-ON-MIDRA: 161
- BR-DM-RN-RASTN: 138
- BR-DM-ON-RASTN: 136

### By Brand
- Onda: 1955
- Ronaldos: 1528

### By City
- Dammam: 3195
- Riyadh: 288

---

## 3. Delays

| Type | Count |
|------|-------|
| Kitchen delays (left in progress) | 236 |
| Warehouse delay scenarios | 627 |

---

## 4. Partial Orders

| Metric | Value |
|--------|-------|
| Partial warehouse issues (sim) | 345 |
| Partial warehouse lines (DB) | 187 |
| Partial deliveries (DB) | 169 |
| Partial rate (sim issues / WL) | 6.9% |

---

## 5. Backorders

| Metric | Value |
|--------|-------|
| Backorders (sim) | 385 |
| Backorder lines (DB) | 394 |
| Backorder rate | 7.7% |

---

## 6. Top Items

Top 20 by request frequency in simulation:

1. 7UP سفن اب — 114
2. كولا لايت COLA LIGHT — 107
3. كولا زيرو Cola Zero — 106
4. بيبسي دايت — 105
5. فانتا برتقالFanta Orange — 103
6. فانتا حمضياتFanta Citruse — 101
7. فانتا فراولةFanta Strawberry — 100
8. سبرايت SPRITE — 99
9. بيبسي — 98
10. كولا COLA CAN — 95
11. كولا قزاز Cola Glass — 94
12. سفن اب دايت — 92
13. ديو DEW — 92
14. ميرندا برتقال — 89
15. ماء water — 79
16. كرواسون تركي جبن  Turkey Cheddar Croissant — 78
17. كوكيز Cookies — 77
18. كرواسون زعتر Zatar Croissant — 76
19. تشيزكيك التوت Berry Cheesecake — 75
20. ميرندا حمضيات — 75

---

## 7. Top Delay Reasons

- Stock count mismatch: 132
- Equipment maintenance: 126
- Staff shortage: 124
- Supplier delay: 122
- Quality hold: 118
- Transport delay: 118
- Partial shipment from vendor: 116
- Kitchen backlog: 116

---

## 8. Dashboard Validation

After simulation, `/dashboard` KPIs and supply-chain widgets read from scoped API endpoints backed by this data. Drill-down routes (`/supply-chain/branch-requests`, `/approvals`, `/kitchen`, `/warehouse`, `/delivery`) remain unchanged from Phase 7.

---

## 9. Integrity Validation

See `tests/test_phase8_simulation.py` — orphan checks, non-negative stock, scope spot checks.

---

## 10. Performance Snapshot

| Query | ms |
|-------|-----|
| branch_requests_count_ms | 18.1 |
| warehouse_lines_count_ms | 11.0 |
| delivery_orders_count_ms | 9.7 |
| audit_logs_count_ms | 15.5 |

Rough API timings (when uvicorn running on :8010): dashboard and notification summary typically &lt; 500ms on local PostgreSQL with this dataset.

---

## 11. Remaining Risks

1. Simulation adds to existing DB — totals include prior phase test data.
2. Full 90-day run duration scales with request volume (~20–80/day).
3. Kitchen output paths depend on section manager assignments per city.

---

## 12. Go / No-Go

| Gate | Demo | LAN Trial | Production |
|------|------|-----------|------------|
| Realistic operational volume | **Go** | **Go** | **Go** (with monitoring) |
| Dashboard populated | **Go** | **Go** | **Go** |
| C-01 JWT localStorage | **Go** | **Caution** | **No-Go** |
| Server deployment | N/A | Local only | **No-Go** |
