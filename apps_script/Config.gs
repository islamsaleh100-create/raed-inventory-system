/** Authentication-only configuration. No production spreadsheet ID is stored in source. */
var AUTH_CONFIG = Object.freeze({
  VERSION: '2.0.0',
  SPREADSHEET_ID_PROPERTY: 'RAED_OPERATIONS_SPREADSHEET_ID',
  SESSION_TTL_SECONDS: 1800,
  PASSWORD_MIN_LENGTH: 12,
  HASH_VERSION: 'v1',
  HASH_ITERATIONS: 120000,
  SESSION_CACHE_PREFIX: 'raed_auth_session_',
  SESSION_VERSION: 1,
  TIME_ZONE: 'Asia/Riyadh',
  LOCK_TIMEOUT_MS: 10000,
  SHIFT_STATUSES: Object.freeze(['DRAFT', 'SUBMITTED', 'LOCKED']),
  INVENTORY_STATUSES: Object.freeze(['DRAFT', 'SUBMITTED', 'LOCKED']),
  INVENTORY_LINE_STATUSES: Object.freeze(['INCOMPLETE', 'VALID', 'INVALID', 'LOCKED']),
  EXPENSE_TYPES: Object.freeze(['INVOICES', 'ADVANCE', 'HANDED_TO_PERSON', 'OPERATIONAL', 'OTHER']),
  ALLOWED_ROLES: Object.freeze([
    'BRANCH_USER',
    'BRAND_MANAGER',
    'OPERATIONS_MANAGER',
    'ADMIN'
  ]),
  SHEETS: Object.freeze({
    USERS: 'Users',
    BRANCHES: 'Branches',
    BRANDS: 'Brands',
    USER_SCOPES: 'User_Scopes',
    SHIFT_CONFIG: 'Shift_Config',
    SHIFTS: 'Shifts',
    SALES: 'Sales',
    BRAND_ITEMS: 'Brand_Items',
    INVENTORY: 'Inventory',
    INVENTORY_LINES: 'Inventory_Lines'
  }),
  REQUIRED_COLUMNS: Object.freeze({
    Users: Object.freeze([
      'user_id', 'username', 'display_name', 'role_code', 'branch_id',
      'is_active', 'password_hash', 'must_change_password', 'created_at',
      'updated_at', 'notes'
    ]),
    Branches: Object.freeze([
      'branch_id', 'branch_name_ar', 'branch_name_en', 'brand_code',
      'city_code', 'city_name_ar', 'region_code', 'is_active',
      'shifts_per_day', 'source_name', 'source_sheet', 'source_row',
      'source_brand_value', 'notes'
    ]),
    Brands: Object.freeze([
      'brand_id', 'brand_code', 'brand_name_ar', 'brand_name_en',
      'is_active', 'notes'
    ]),
    User_Scopes: Object.freeze([
      'scope_id', 'user_id', 'manager_source_name', 'display_name',
      'city_code', 'brand_code', 'is_active', 'effective_from',
      'effective_to', 'source_name', 'source_sheet', 'source_row', 'notes'
    ]),
    Shift_Config: Object.freeze([
      'shift_config_id', 'branch_id', 'shift_number', 'shift_name_ar',
      'is_active', 'start_time', 'end_time', 'submission_deadline',
      'source_confirmed', 'notes'
    ]),
    Shifts: Object.freeze([
      'shift_id', 'branch_id', 'shift_date', 'shift_number', 'status',
      'opened_by', 'opened_at', 'submitted_by', 'submitted_at',
      'reopened_by', 'reopened_at', 'locked_at', 'notes'
    ]),
    Sales: Object.freeze([
      'sales_id', 'shift_id', 'status', 'total_sale', 'bill_count',
      'mada_sales', 'cash_sales', 'app_sales', 'refund_bill',
      'exchange_amount', 'expiry_amount', 'cash_expense', 'cash_deposited',
      'expense_type', 'expense_details', 'shift_notes', 'created_by',
      'updated_by', 'submitted_by', 'created_at', 'updated_at', 'submitted_at'
    ]),
    Brand_Items: Object.freeze([
      'item_id', 'brand_id', 'item_name', 'unit', 'shift_count_enabled',
      'display_order', 'is_active', 'created_at', 'updated_at'
    ]),
    Inventory: Object.freeze([
      'inventory_id', 'shift_id', 'status', 'general_notes', 'created_by',
      'updated_by', 'submitted_by', 'created_at', 'updated_at', 'submitted_at'
    ]),
    Inventory_Lines: Object.freeze([
      'inventory_line_id', 'inventory_id', 'brand_item_id', 'opening_balance',
      'received_qty', 'returned_qty', 'damaged_qty', 'closing_balance',
      'consumption_qty', 'item_notes', 'row_status', 'created_at', 'updated_at'
    ])
  })
});

function getSpreadsheetId() {
  var value = PropertiesService.getScriptProperties()
    .getProperty(AUTH_CONFIG.SPREADSHEET_ID_PROPERTY);
  value = value ? String(value).trim() : '';
  if (!value) {
    throw createInternalError_('SYSTEM_CONFIGURATION_ERROR');
  }
  return value;
}
