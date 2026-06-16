# LAN Opening Stock Fix Report

**Executed:** 2026-06-16  
**Database:** `raed_lan_trial`  
**Warehouse:** `WH-DM-1` — Dammam Central Warehouse  
**Scope:** Opening warehouse stock only — no workflows, RBAC, item master, requests, production, delivery, or simulation changes

---

## Missing Items Before Fix

Validation (`validate_lan_opening_stock.py`) reported **NO-GO** with **28 missing** `warehouse_stock` rows at `WH-DM-1` for requestable trial-branch items.

| item_id | item_code | item_name | brand | category | source_type |
|--------:|-----------|-----------|-------|----------|-------------|
| 25 | SUP-GENER-FE5F26F7F1 | كولا لايت COLA LIGHT | Onda\|Ronaldos\|Shawarma\|Griddle | drinks | WAREHOUSE |
| 13 | SUP-GENER-42D331319B | 7UP سفن اب | Onda\|Ronaldos\|Shawarma\|Griddle | drinks | WAREHOUSE |
| 76 | SUP-ONDA-96021AEE92 | ايسكريم افوجاتو Ice Cream Affogato | Onda | ICE CREAM | WAREHOUSE |
| 72 | SUP-ONDA-14D00B9A16 | طقم ترشيح Filter Set | Onda | EQUIPMENT | WAREHOUSE |
| 22 | SUP-GENER-14C6AE4CB5 | كولا COLA CAN | Onda\|Ronaldos\|Shawarma\|Griddle | drinks | WAREHOUSE |
| 14 | SUP-GENER-68348E677D | بيبسي | Onda\|Ronaldos\|Shawarma\|Griddle | drinks | WAREHOUSE |
| 73 | SUP-ONDA-6865068F43 | كوب سيراميك 320 مل ceramic cup | Onda | EQUIPMENT | WAREHOUSE |
| 20 | SUP-GENER-36594BD68C | فانتا حمضياتFanta Citruse | Onda\|Ronaldos\|Shawarma\|Griddle | drinks | WAREHOUSE |
| 74 | SUP-ONDA-FA92A55BA4 | كوب سيراميك 420 ceramic cup | Onda | EQUIPMENT | WAREHOUSE |
| 26 | SUP-GENER-A23DA96E3E | ماء water | Onda\|Ronaldos\|Shawarma\|Griddle | drinks | WAREHOUSE |
| 17 | SUP-GENER-0C00F4B291 | سبرايت SPRITE | Onda\|Ronaldos\|Shawarma\|Griddle | drinks | WAREHOUSE |
| 70 | SUP-ONDA-631A530325 | PLASTIC CUP 12 OZ | Onda | EQUIPMENT | WAREHOUSE |
| 77 | SUP-ONDA-D28EA8EFD8 | ايسكريم تشيز كيك Ice Cream Cheesecake | Onda | ICE CREAM | WAREHOUSE |
| 21 | SUP-GENER-8EAAB1D5E9 | فانتا فراولةFanta Strawberry | Onda\|Ronaldos\|Shawarma\|Griddle | drinks | WAREHOUSE |
| 71 | SUP-ONDA-E29B33499E | V 60 FILTER | Onda | EQUIPMENT | WAREHOUSE |
| 27 | SUP-GENER-2757A137E1 | ميرندا برتقال | Onda\|Ronaldos\|Shawarma\|Griddle | drinks | WAREHOUSE |
| 15 | SUP-GENER-4A1FC2F6D4 | بيبسي دايت | Onda\|Ronaldos\|Shawarma\|Griddle | drinks | WAREHOUSE |
| 28 | SUP-GENER-1BCBC825B5 | ميرندا حمضيات | Onda\|Ronaldos\|Shawarma\|Griddle | drinks | WAREHOUSE |
| 24 | SUP-GENER-5022522082 | كولا قزاز Cola Glass | Onda\|Ronaldos\|Shawarma\|Griddle | drinks | WAREHOUSE |
| 23 | SUP-GENER-1F03C693AD | كولا زيرو Cola Zero | Onda\|Ronaldos\|Shawarma\|Griddle | drinks | WAREHOUSE |
| 16 | SUP-GENER-0FCD37A462 | ديو DEW | Onda\|Ronaldos\|Shawarma\|Griddle | drinks | WAREHOUSE |
| 19 | SUP-GENER-AD169B69CB | فانتا برتقالFanta Orange | Onda\|Ronaldos\|Shawarma\|Griddle | drinks | WAREHOUSE |
| 18 | SUP-GENER-3854B532CA | سفن اب دايت | Onda\|Ronaldos\|Shawarma\|Griddle | drinks | WAREHOUSE |
| 148 | SUP-SHARE-E4084AEC8C | فرايز FRENCH FRIES | Ronaldos\|Shawarma\|Griddle | snack | WAREHOUSE |
| 142 | SUP-SHARE-77A7E59B10 | اضافة جبنة 2 | Ronaldos\|Shawarma\|Griddle | snack | WAREHOUSE |
| 144 | SUP-SHARE-2EEDB2F8BD | علبة جبنة | Ronaldos\|Shawarma\|Griddle | snack | WAREHOUSE |
| 141 | SUP-SHARE-9EA7485D85 | اضافة جبنة | Ronaldos\|Shawarma\|Griddle | snack | WAREHOUSE |
| 123 | SUP-SHAWA-4DA437B5F7 | CHESSE - جبن | Shawarma | shawarma sauce | WAREHOUSE |

Full review file: `LAN_OPENING_STOCK_MISSING_ITEMS_REVIEW.csv`

---

## Stock Rows Created

**28** new `warehouse_stock` rows inserted at `WH-DM-1` via:

```powershell
python seed_lan_opening_stock.py `
  --input LAN_OPENING_STOCK_MISSING_ITEMS_REVIEW.csv `
  --warehouse WH-DM-1 `
  --i-understand-this-is-lan-trial-stock
```

All 28 target items verified with `current_qty > 0` after seed.

---

## Stock Rows Skipped

**0** on initial seed run.

Re-running the seed script without `--force` would skip all 28 rows (existing non-zero stock).

---

## Quantities Used

Conservative LAN trial placeholders (not production counts):

| Rule | Qty | Items |
|------|----:|------:|
| Beverages / water / soft drinks | 100 | 16 |
| Packaging / cups / filters / consumables | 500 | 5 |
| Finished kitchen / snack / sauce | 50 | 7 |
| **Total** | | **28** |

**Important:** These quantities are for LAN trial operation only. Production stock must be loaded later from a real warehouse count.

---

## Validation Result After Fix

```text
python validate_lan_opening_stock.py --write-report
```

| Check | Result |
|-------|--------|
| Verdict | **GO** |
| Trial branches | 3 |
| Missing stock rows | 0 |
| Zero stock items | 0 |
| Below reorder point | 0 |

Updated report: `raed_inventory/LAN_OPENING_STOCK_VALIDATION_REPORT.md`

---

## Remaining Issues

None blocking opening stock for LAN trial.

- Placeholder quantities are not reconciled to physical inventory.
- Other warehouses (`WH-RY-1`) were not modified.
- Overall LAN trial verdict can move from `LAN_DB_READY_WITH_CONDITIONS` to **`LAN_DB_READY`** once operators confirm placeholder stock is acceptable for trial start.

---

## Final Verdict

### **OPENING_STOCK_READY**

All 28 previously missing items now have opening stock at `WH-DM-1`. Opening stock validation passes **GO**.

---

*LAN trial stock setup only — not production, accounting, or inventory reconciliation.*
