# Prototype V1 Approval

## Approval Status

- Sales Screen V1.0: Frozen
- Inventory Screen V1.0: Approved
- Prototype Phase: Complete

## Approved Screens

- Branch Sales Screen
- Branch Shift Inventory Screen

## Supported Brands

- ONDA
- RONALDOS
- SHAWARMA

## Approved Inventory Lists

### ONDA

Source:

`Coffee_Consumption_Tracker_1.xlsx`

Scope:

- Coffee Beans: 4 items, unit `كيس`
- Cups: 8 items, unit `قطعة`
- Desserts: 11 items, unit `قطعة`

Total:

23 items

The exact item names are preserved from the approved Excel source.

### RONALDOS

- العجين — كجم
- الدجاج — كجم
- شرمب — كجم

Total:

3 items

### SHAWARMA

- سيخ دجاج — سيخ
- سيخ لحم — سيخ

Total:

2 items

Brand inventory lists are isolated and must never be mixed.

## Inventory Business Rules

- Item and unit are read-only.
- Opening balance is read-only.
- Opening balance represents the previous shift closing balance.
- Received is entered manually.
- Returned is entered manually.
- Damaged is entered manually.
- Closing balance is entered manually.
- Item notes are optional.
- Consumption is calculated per item only.
- Consumption formula:

  ```text
  Opening
  + Received
  - Returned
  - Damaged
  - Closing
  ```

- Consumption is not calculated until the row is complete.
- Blank is not equal to zero.
- Zero is a valid reviewed value.
- Negative values are invalid.
- Negative consumption is invalid.
- Draft saving is allowed with incomplete data.
- Submission is blocked for incomplete or invalid rows.
- Submission locks all editable fields.
- Mixed-unit consumption totals are forbidden.

## Sales Business Rules

- Total Sale is a financial value.
- Bill Count is the total number of invoices.
- Mada is a financial value.
- Cash is a financial value.
- App Sales is a financial value.
- Mada + Cash + App Sales must equal Total Sale.
- Refund Bill is a financial value.
- Exchange is a financial value.
- Expiry is a financial value.
- Cash Sales - Cash Expense must equal Cash Deposited.
- Expense type and details become required when Cash Expense is greater than zero.
- Draft saving is allowed.
- Submission is blocked when validation fails.
- Submitted sales become locked.

## Workflow

### Sales

Shift
→ Enter Sales
→ Save Draft
→ Submit Sales
→ Locked

### Inventory

Shift
→ Count Approved Brand Items
→ Save Draft
→ Submit Inventory
→ Locked

## Roles in Prototype Scope

### Branch User

Can:

- Enter sales.
- Enter inventory.
- Save drafts.
- Submit shifts.

Cannot:

- Edit after submission.
- Switch to another branch dataset through the visible interface.

URL brand switching exists for prototype QA only and is not a production user control.

## Design Approval

- RTL approved.
- Desktop layout approved.
- 1366×768 approved.
- 1600×900 approved.
- 1920×1080 approved.
- No vertical page scroll.
- Internal inventory table scrolling approved.
- Sales and Inventory use one consistent design system.

## Approved Prototype Files

- `prototype/index.html`
- `prototype/sales.html`
- `prototype/inventory.html`
- `prototype/css/style.css`
- `prototype/js/app.js`
- `prototype/assets/logo-placeholder.svg`
- `prototype/PROTOTYPE_V1_APPROVAL.md`

## Verification Results

Final QA was performed against the local HTML prototype through `localhost` without modifying the protected artifacts.

### Sales

- Screen loaded successfully.
- Payment validation detected a payment-method difference and blocked submission.
- Draft save changed the prototype state to `محفوظة` without locking the form.
- Submit displayed a confirmation dialog.
- Confirmed submission changed the state to `مغلق` and disabled editable controls.
- No Console errors or warnings were reported.
- No vertical page scroll at 1366×768, 1600×900, or 1920×1080.

### Inventory

- ONDA loaded exactly 23 approved items.
- RONALDOS loaded exactly 3 items: العجين، الدجاج، شرمب; all use `كجم`.
- SHAWARMA loaded exactly 2 items: سيخ دجاج، سيخ لحم; both use `سيخ`.
- An unknown brand value safely fell back to ONDA with 23 items.
- No cross-brand items were present in the tested datasets.
- Opening balances were read-only.
- Received, returned, damaged, and closing balances were editable and initially blank.
- Consumption outputs were calculated and read-only.
- Blank rows remained incomplete while explicit zero values were accepted.
- A negative input was marked invalid and submission was blocked.
- A negative calculated consumption was marked invalid and displayed as `—`.
- Formula verification passed: `32 + 2 - 1 - 0 - 30 = 3.00`.
- Draft save remained available with invalid or incomplete data and did not lock the form.
- Incomplete and invalid rows blocked submission.
- Complete valid rows enabled confirmation and confirmed submission locked all editable controls.
- No mixed-unit consumption aggregate appeared in the UI.
- No Console errors or warnings were reported.
- No vertical page scroll at 1366×768, 1600×900, or 1920×1080.

### Command Checks

- `node --check prototype/js/app.js`: passed with exit code `0`.
- `git diff --check`: passed with exit code `0`.
- `git status --short`: executed; the repository contains pre-existing tracked and untracked changes, including the currently untracked `prototype/` directory.

## Protected Artifacts

Sales Screen V1.0 is frozen.

Inventory Screen V1.0 is approved.

Future modifications require a new approved Task Gate.

## Known Limitations

- HTML prototype only.
- No backend.
- No Google Sheets data layer.
- No Google Apps Script.
- No authentication integration.
- No persistent storage.
- No production Item Master integration.
- No manager review screens.
- No reports.
- No production deployment.

## Future Production Data Rule

The approved future production direction is to load inventory items filtered by:

- Current brand.
- `Shift Count Item = Yes`.

This is a future design direction only. It is not implemented functionality, and this document does not state that the field currently exists in the database.

## Git Baseline Recommendation

```bash
git add prototype/
git add .ai-workflow/TASK_GATE.md
git commit -m "Prototype v1 approved: sales and inventory"
```

These commands were recommended only and were not executed.

## Next Phase

Google Sheets Data Layer

Then:

Google Apps Script Backend

Prototype Phase Complete — Ready for Google Sheets Phase.
