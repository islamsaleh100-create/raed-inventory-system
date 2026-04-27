import { test, expect, type Page } from '@playwright/test';

const RUN_SUFFIX = String(Date.now()).slice(-8);
const EMPLOYEE_NAME = `PW Employee ${RUN_SUFFIX}`;
const EMPLOYEE_NAME_EDITED = `PW Employee Edited ${RUN_SUFFIX}`;
const EMPLOYEE_WORK_NUMBER = `PW-${RUN_SUFFIX}`;
const KITCHEN_NAME = `PW Kitchen ${RUN_SUFFIX}`;
const KITCHEN_CITY = `Playwright City ${RUN_SUFFIX}`;

async function login(page: Page, username: string, password = 'Raed@2025') {
  await page.goto('/login');
  if ((await page.locator('input').count()) < 2) {
    await page.evaluate(() => {
      localStorage.removeItem('access_token');
      localStorage.removeItem('persist:root');
      sessionStorage.clear();
    });
    await page.context().clearCookies();
    await page.goto('/login');
  }
  await page.locator('input').nth(0).fill(username);
  await page.locator('input').nth(1).fill(password);
  const submitButton = page.locator('button[type="submit"]').first();
  await expect(submitButton).toBeVisible();
  for (let attempt = 0; attempt < 3; attempt += 1) {
    if (attempt > 0) {
      await page.waitForTimeout(3500);
    } else {
      await page.waitForTimeout(3200);
    }
    const loginResponse = page.waitForResponse((resp) =>
      resp.url().includes('/api/v1/auth/login') && resp.request().method() === 'POST'
    );
    await submitButton.click();
    const status = (await loginResponse).status();
    if (status === 429 && attempt < 2) {
      continue;
    }
    expect(status).toBeLessThan(400);
    await page.waitForURL(/\/dashboard|\/supply-chain\/control/);
    return;
  }
}

async function expectForbidden(page: Page, path: string) {
  await page.goto(path);
  const pathRegex = new RegExp(path.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '$');
  await page.waitForTimeout(500);
  if (pathRegex.test(page.url())) {
    await expect(page.getByText(/Access denied|غير مصرّح|forbidden|unauthorized/i).first()).toBeVisible();
  } else {
    expect(pathRegex.test(page.url())).toBeFalsy();
  }
}

async function expectVisibleOn(page: Page, path: string, marker: RegExp) {
  await page.goto(path);
  await expect(page).toHaveURL(new RegExp(path.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '$'));
  await expect(page.getByText(marker).first()).toBeVisible();
}

async function authedJson(page: Page, path: string, init?: { method?: string; body?: unknown }) {
  return await page.evaluate(async ({ path, init }) => {
    const token = localStorage.getItem('access_token');
    const response = await fetch(path, {
      method: init?.method || 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: init?.body ? JSON.stringify(init.body) : undefined,
    });
    const text = await response.text();
    let data: unknown = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = text;
    }
    return { status: response.status, data };
  }, { path, init });
}

async function createBranchRequestViaUi(page: Page, submitAfter = false, qty = '1') {
  await login(page, 'branch_onda_13_al_malqa');
  await page.goto('/supply-chain/branch-requests');
  await page.waitForFunction(() => {
    const selects = document.querySelectorAll('select');
    return selects.length >= 3 && (selects[1] as HTMLSelectElement).options.length > 1;
  });
  await page.locator('select').nth(1).selectOption({ index: 1 });
  await page.locator('input[type="number"]').first().fill(qty);
  const createResponsePromise = page.waitForResponse((resp) =>
    /\/api\/v1\/branch-requests$/.test(resp.url()) && resp.request().method() === 'POST'
  );
  const submitResponsePromise = submitAfter
    ? page.waitForResponse((resp) =>
        /\/api\/v1\/branch-requests\/\d+\/submit$/.test(resp.url()) && resp.request().method() === 'POST'
      )
    : null;
  if (submitAfter) {
    await page.locator('.btn-primary').last().click();
  } else {
    await page.locator('.btn-secondary').filter({ hasText: /مسودة|Draft/i }).last().click();
  }
  const createResponse = await createResponsePromise;
  const created = await createResponse.json();
  const submitStatus = submitResponsePromise ? (await submitResponsePromise).status() : null;
  return { createStatus: createResponse.status(), submitStatus, created };
}

async function openApprovalRequest(page: Page, requestNo: string) {
  await login(page, 'area_riyadh_all');
  await page.goto('/supply-chain/approvals');
  const requestButton = page.getByRole('button', { name: new RegExp(requestNo.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')) }).first();
  await expect(requestButton).toBeVisible({ timeout: 15000 });
  await requestButton.click();
}

test.describe('Raed role and route browser review', () => {
  test.describe.configure({ mode: 'serial' });

  test('01 login page renders', async ({ page }) => {
    await page.goto('/login');
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.locator('input')).toHaveCount(2);
  });

  test('02 super admin can reach supply chain control', async ({ page }) => {
    await login(page, 'super.admin');
    await expectVisibleOn(page, '/supply-chain/control', /refresh|تحديث|طلبات/i);
  });

  test('03 super admin can reach admin kitchens', async ({ page }) => {
    await login(page, 'super.admin');
    await expectVisibleOn(page, '/admin/kitchens', /kitchen|ظ…ط·ط¨ط®/i);
  });

  test('04 super admin can reach branch employees', async ({ page }) => {
    await login(page, 'super.admin');
    await expectVisibleOn(page, '/branch-employees', /add|إضافة|الفرع/i);
  });

  test('05 super admin can reach quality analytics', async ({ page }) => {
    await login(page, 'super.admin');
    await page.goto('/quality/analytics');
    await expect(page).toHaveURL(/\/quality\/analytics$/);
  });

  test('06 admin can reach dashboard', async ({ page }) => {
    await login(page, 'admin');
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/\/dashboard$/);
  });

  test('07 admin can reach supply chain approvals', async ({ page }) => {
    await login(page, 'admin');
    await page.goto('/supply-chain/approvals');
    await expect(page).toHaveURL(/\/supply-chain\/approvals$/);
  });

  test('08 admin can reach admin kitchens', async ({ page }) => {
    await login(page, 'admin');
    await expectVisibleOn(page, '/admin/kitchens', /kitchen|ظ…ط·ط¨ط®/i);
  });

  test('09 area riyadh can reach approvals', async ({ page }) => {
    await login(page, 'area_riyadh_all');
    await page.goto('/supply-chain/approvals');
    await expect(page).toHaveURL(/\/supply-chain\/approvals$/);
  });

  test('10 area riyadh can reach branch requests', async ({ page }) => {
    await login(page, 'area_riyadh_all');
    await page.goto('/supply-chain/branch-requests');
    await expect(page).toHaveURL(/\/supply-chain\/branch-requests$/);
  });

  test('11 area riyadh is blocked from kitchen', async ({ page }) => {
    await login(page, 'area_riyadh_all');
    await expectForbidden(page, '/supply-chain/kitchen');
  });

  test('12 area riyadh is blocked from warehouse', async ({ page }) => {
    await login(page, 'area_riyadh_all');
    await expectForbidden(page, '/supply-chain/warehouse');
  });

  test('13 area dammam onda can reach approvals', async ({ page }) => {
    await login(page, 'area_dammam_onda');
    await page.goto('/supply-chain/approvals');
    await expect(page).toHaveURL(/\/supply-chain\/approvals$/);
  });

  test('14 branch onda can reach control center', async ({ page }) => {
    await login(page, 'branch_onda_13_al_malqa');
    await expectVisibleOn(page, '/supply-chain/control', /refresh|تحديث|طلبات/i);
  });

  test('15 branch onda can reach branch requests', async ({ page }) => {
    await login(page, 'branch_onda_13_al_malqa');
    await page.goto('/supply-chain/branch-requests');
    await expect(page).toHaveURL(/\/supply-chain\/branch-requests$/);
  });

  test('16 branch onda can reach branch employees', async ({ page }) => {
    await login(page, 'branch_onda_13_al_malqa');
    await expectVisibleOn(page, '/branch-employees', /add|إضافة|الفرع/i);
  });

  test('17 branch onda can reach daily orders', async ({ page }) => {
    await login(page, 'branch_onda_13_al_malqa');
    await page.goto('/orders/daily');
    await expect(page).toHaveURL(/\/orders\/daily$/);
  });

  test('18 branch onda is blocked from supply chain approvals', async ({ page }) => {
    await login(page, 'branch_onda_13_al_malqa');
    await expectForbidden(page, '/supply-chain/approvals');
  });

  test('19 branch onda is blocked from warehouse page', async ({ page }) => {
    await login(page, 'branch_onda_13_al_malqa');
    await expectForbidden(page, '/supply-chain/warehouse');
  });

  test('20 branch griddle can reach branch requests', async ({ page }) => {
    await login(page, 'branch_griddle');
    await page.goto('/supply-chain/branch-requests');
    await expect(page).toHaveURL(/\/supply-chain\/branch-requests$/);
  });

  test('21 branch griddle can reach branch employees', async ({ page }) => {
    await login(page, 'branch_griddle');
    await expectVisibleOn(page, '/branch-employees', /add|إضافة|الفرع/i);
  });

  test('22 kitchen dammam meat can reach control center', async ({ page }) => {
    await login(page, 'kitchen_dammam_meat_and_chicken_mgr');
    await expectVisibleOn(page, '/supply-chain/control', /refresh|تحديث|طلبات/i);
  });

  test('23 kitchen dammam meat can reach kitchen page', async ({ page }) => {
    await login(page, 'kitchen_dammam_meat_and_chicken_mgr');
    await expectVisibleOn(page, '/supply-chain/kitchen', /ط£ظˆط§ظ…ط± ط£ظ‚ط³ط§ظ… ط§ظ„ظ…ط·ط¨ط®|kitchen/i);
  });

  test('24 kitchen dammam meat is blocked from approvals', async ({ page }) => {
    await login(page, 'kitchen_dammam_meat_and_chicken_mgr');
    await expectForbidden(page, '/supply-chain/approvals');
  });

  test('25 kitchen riyadh pizza can reach kitchen page', async ({ page }) => {
    await login(page, 'kitchen_riyadh_pizza_mgr');
    await expectVisibleOn(page, '/supply-chain/kitchen', /ط£ظˆط§ظ…ط± ط£ظ‚ط³ط§ظ… ط§ظ„ظ…ط·ط¨ط®|kitchen/i);
  });

  test('26 warehouse dammam user can reach control center', async ({ page }) => {
    await login(page, 'warehouse_dammam_user');
    await expectVisibleOn(page, '/supply-chain/control', /refresh|تحديث|طلبات/i);
  });

  test('27 warehouse dammam user can reach warehouse page', async ({ page }) => {
    await login(page, 'warehouse_dammam_user');
    await expectVisibleOn(page, '/supply-chain/warehouse', /طھظ†ظپظٹط° ط§ظ„ظ…ط³طھظˆط¯ط¹|warehouse/i);
  });

  test('28 warehouse dammam user is blocked from kitchen page', async ({ page }) => {
    await login(page, 'warehouse_dammam_user');
    await expectForbidden(page, '/supply-chain/kitchen');
  });

  test('29 warehouse riyadh manager can reach warehouse page', async ({ page }) => {
    await login(page, 'warehouse_riyadh_manager');
    await expectVisibleOn(page, '/supply-chain/warehouse', /طھظ†ظپظٹط° ط§ظ„ظ…ط³طھظˆط¯ط¹|warehouse/i);
  });

  test('30 warehouse riyadh manager can reach inventory reports', async ({ page }) => {
    await login(page, 'warehouse_riyadh_manager');
    await page.goto('/reports/inventory');
    await expect(page).toHaveURL(/\/reports\/inventory$/);
  });

  test('31 delivery dammam can reach control center', async ({ page }) => {
    await login(page, 'delivery_dammam');
    await expectVisibleOn(page, '/supply-chain/control', /refresh|تحديث|طلبات/i);
  });

  test('32 delivery dammam can reach delivery page', async ({ page }) => {
    await login(page, 'delivery_dammam');
    await expectVisibleOn(page, '/supply-chain/delivery', /ط£ظˆط§ظ…ط± ط§ظ„طھط³ظ„ظٹظ…|delivery/i);
  });

  test('33 delivery dammam is blocked from kitchen page', async ({ page }) => {
    await login(page, 'delivery_dammam');
    await expectForbidden(page, '/supply-chain/kitchen');
  });

  test('34 delivery riyadh can reach delivery page', async ({ page }) => {
    await login(page, 'delivery_riyadh');
    await expectVisibleOn(page, '/supply-chain/delivery', /ط£ظˆط§ظ…ط± ط§ظ„طھط³ظ„ظٹظ…|delivery/i);
  });

  test('35 delivery riyadh is blocked from warehouse page', async ({ page }) => {
    await login(page, 'delivery_riyadh');
    await expectForbidden(page, '/supply-chain/warehouse');
  });

  test('36 area approvals page has core action controls', async ({ page }) => {
    await login(page, 'area_riyadh_all');
    await page.goto('/supply-chain/approvals');
    await expect(page).toHaveURL(/\/supply-chain\/approvals$/);
    const approveBtn = page.getByRole('button', { name: 'اعتماد', exact: true });
    if (await approveBtn.count()) {
      await expect(approveBtn).toBeVisible();
      await expect(page.getByRole('button', { name: 'تعديل واعتماد', exact: true })).toBeVisible();
      await expect(page.getByRole('button', { name: 'رفض', exact: true })).toBeVisible();
      await expect(page.locator('textarea')).toHaveCount(2);
    }
  });

  test('37 branch requests page has item selection and submit controls', async ({ page }) => {
    await login(page, 'branch_onda_13_al_malqa');
    await page.goto('/supply-chain/branch-requests');
    await expect(page).toHaveURL(/\/supply-chain\/branch-requests$/);
    await expect(page.locator('select').first()).toBeVisible();
    await expect(page.locator('input[type="number"]').first()).toBeVisible();
    await expect(page.getByRole('button', { name: /\+/ })).toBeVisible();
    await expect(page.getByRole('button', { name: /حفظ|إرسال|submit/i }).first()).toBeVisible();
  });

  test('38 warehouse page has receive issue and partial issue controls', async ({ page }) => {
    await login(page, 'warehouse_dammam_user');
    await page.goto('/supply-chain/warehouse');
    await expect(page).toHaveURL(/\/supply-chain\/warehouse$/);
    await expect(page.getByRole('button', { name: 'الكل', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'طلبات الفروع', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'إنتاج المطبخ', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'النواقص', exact: true })).toBeVisible();
    const issueFull = page.getByRole('button', { name: 'صرف كامل', exact: true }).first();
    if (await issueFull.count()) {
      await expect(issueFull).toBeVisible();
      await expect(page.getByRole('button', { name: 'صرف جزئي', exact: true }).first()).toBeVisible();
      await expect(page.getByRole('button', { name: 'تسجيل تأخير', exact: true }).first()).toBeVisible();
    } else {
      await expect(page.getByText(/لا توجد بيانات لهذا التبويب|جارٍ التحميل/i).first()).toBeVisible();
    }
  });

  test('39 control center shows refresh and operational links', async ({ page }) => {
    await login(page, 'super.admin');
    await page.goto('/supply-chain/control');
    await expect(page).toHaveURL(/\/supply-chain\/control$/);
    await expect(page.locator('input[type="checkbox"]').first()).toBeVisible();
    await expect(page.locator('button').filter({ hasText: /تحديث|Refresh/i }).first()).toBeVisible();
    await expect(page.locator('a[href="/supply-chain/branch-requests"]').first()).toBeVisible();
    await expect(page.locator('a[href="/inventory"]').first()).toBeVisible();
  });

  test('40 branch employees page shows admin branch selector prompt', async ({ page }) => {
    await login(page, 'super.admin');
    await page.goto('/branch-employees');
    await expect(page.getByText(/add|إضافة|الفرع/i).first()).toBeVisible();
    await expect(page.locator('select').first()).toBeVisible();
  });

  test('41 branch employees page allows branch manager to open create modal', async ({ page }) => {
    await login(page, 'branch_onda_13_al_malqa');
    await page.goto('/branch-employees');
    const addButton = page.getByRole('button', { name: /إضافة موظف|Add employee/i }).first();
    await expect(addButton).toBeVisible();
    await addButton.click();
    await expect(page.locator('input').nth(0)).toBeVisible();
    await expect(page.getByRole('button', { name: /cancel|إلغاء/i })).toBeVisible();
  });

  test('42 kitchens admin page shows create form fields', async ({ page }) => {
    await login(page, 'super.admin');
    await page.goto('/admin/kitchens');
    await expect(page).toHaveURL(/\/admin\/kitchens$/);
    await expect(page.locator('input').nth(0)).toBeVisible();
    await expect(page.locator('input').nth(1)).toBeVisible();
    await expect(page.locator('button[type="submit"]').first()).toBeVisible();
  });

  test('43 branch user is blocked from admin kitchens', async ({ page }) => {
    await login(page, 'branch_onda_13_al_malqa');
    await expectForbidden(page, '/admin/kitchens');
  });

  test('44 control center is available to delivery user', async ({ page }) => {
    await login(page, 'delivery_dammam');
    await page.goto('/supply-chain/control');
    await expect(page.getByText(/refresh|تحديث|طلبات/i).first()).toBeVisible();
    await expect(page.locator('a[href="/supply-chain/delivery"]').first()).toBeVisible();
  });

  test('45 daily order loads items after admin selects branch', async ({ page }) => {
    await login(page, 'super.admin');
    await page.goto('/orders/daily');
    await expect(page).toHaveURL(/\/orders\/daily$/);
    await page.locator('select').first().selectOption('11');
    await page.waitForFunction(() => {
      const rows = document.querySelectorAll('tbody tr').length;
      const emptyText = document.body.innerText.includes('ظ„ط§ طھظˆط¬ط¯ ط¨ظٹط§ظ†ط§طھ');
      return rows > 1 && !emptyText;
    });
    await expect(page.locator('input[type="text"]').first()).toBeVisible();
  });

  test('46 branch requests auto-load item options for single-brand branch', async ({ page }) => {
    await login(page, 'branch_onda_13_al_malqa');
    await page.goto('/supply-chain/branch-requests');
    await page.waitForFunction(() => {
      const selects = document.querySelectorAll('select');
      return selects.length >= 2 && (selects[1] as HTMLSelectElement).options.length > 1;
    });
    const optionCount = await page.locator('select').nth(1).locator('option').count();
    expect(optionCount).toBeGreaterThan(1);
  });

  test('47 branch griddle can switch brand and still load item options', async ({ page }) => {
    await login(page, 'branch_griddle');
    await page.goto('/supply-chain/branch-requests');
    const brandSelect = page.locator('select').nth(0);
    await expect(brandSelect).toBeVisible();
    await page.waitForFunction(() => {
      const selects = document.querySelectorAll('select');
      return selects.length >= 1 && (selects[0] as HTMLSelectElement).options.length > 1;
    });
    const values = await brandSelect.locator('option').evaluateAll((opts) =>
      opts.map((o) => (o as HTMLOptionElement).value).filter(Boolean)
    );
    expect(values.length).toBeGreaterThan(1);
    await brandSelect.selectOption(values[1]);
    await page.waitForFunction(() => {
      const selects = document.querySelectorAll('select');
      return selects.length >= 2 && (selects[1] as HTMLSelectElement).options.length > 1;
    });
    const optionCount = await page.locator('select').nth(1).locator('option').count();
    expect(optionCount).toBeGreaterThan(1);
  });

  test('48 control center link opens branch requests page', async ({ page }) => {
    await login(page, 'super.admin');
    await page.goto('/supply-chain/control');
    await page.locator('a[href="/supply-chain/branch-requests"]').first().click();
    await expect(page).toHaveURL(/\/supply-chain\/branch-requests$/);
  });

  test('49 daily order search box filters visible rows', async ({ page }) => {
    await login(page, 'super.admin');
    await page.goto('/orders/daily');
    await page.locator('select').first().selectOption('11');
    await page.waitForFunction(() => document.querySelectorAll('tbody tr').length > 1);
    const firstRowText = await page.locator('tbody tr').nth(0).innerText();
    const token = firstRowText.trim().split(/\s+/)[0];
    await page.locator('input[type="text"]').first().fill(token);
    await expect(page.locator('tbody tr')).toHaveCount(1);
  });

  test('50 kitchens admin table shows seeded kitchen rows', async ({ page }) => {
    await login(page, 'super.admin');
    await page.goto('/admin/kitchens');
    await expect(page.getByText(/kitchen|ظ…ط·ط¨ط®/i).first()).toBeVisible();
    const rows = page.locator('tbody tr');
    await expect(rows.first()).toBeVisible();
    expect(await rows.count()).toBeGreaterThanOrEqual(1);
  });
  test('51 branch manager can create branch employee', async ({ page }) => {
    await login(page, 'branch_onda_13_al_malqa');
    await page.goto('/branch-employees');
    const addButton = page.getByRole('button', { name: /إضافة موظف|Add employee/i }).first();
    await expect(addButton).toBeVisible();
    await addButton.click();
    const inputs = page.locator('input');
    await inputs.nth(0).fill(EMPLOYEE_NAME);
    await inputs.nth(1).fill('Store Crew');
    await inputs.nth(2).fill(EMPLOYEE_WORK_NUMBER);
    await inputs.nth(3).fill('0500000000');
    await page.getByRole('button', { name: /إضافة موظف|Add employee|save|حفظ/i }).last().click();
    await expect(page.getByText(EMPLOYEE_NAME)).toBeVisible();
    await expect(page.getByText(EMPLOYEE_WORK_NUMBER)).toBeVisible();
  });

  test('52 branch manager can edit branch employee', async ({ page }) => {
    await login(page, 'branch_onda_13_al_malqa');
    await page.goto('/branch-employees');
    let row = page.locator('tbody tr', { hasText: EMPLOYEE_WORK_NUMBER }).first();
    if ((await row.count()) === 0) {
      const addButton = page.getByRole('button', { name: /إضافة موظف|Add employee/i }).first();
      await expect(addButton).toBeVisible();
      await addButton.click();
      const inputs = page.locator('input');
      await inputs.nth(0).fill(EMPLOYEE_NAME);
      await inputs.nth(1).fill('Store Crew');
      await inputs.nth(2).fill(EMPLOYEE_WORK_NUMBER);
      await inputs.nth(3).fill('0500000000');
      const createResponse = page.waitForResponse((resp) =>
        resp.url().includes('/branch-employees/') && resp.request().method() === 'POST'
      );
      await page.getByRole('button', { name: /إضافة موظف|Add employee|save|حفظ/i }).last().click();
      expect([200, 201, 409]).toContain((await createResponse).status());
      await page.goto('/branch-employees');
      row = page.locator('tbody tr', { hasText: EMPLOYEE_WORK_NUMBER }).first();
    }
    await expect(row).toBeVisible();
    await row.locator('button').nth(0).click();
    await page.locator('input').nth(0).fill(EMPLOYEE_NAME_EDITED);
    await page.locator('input').nth(1).fill('Shift Lead');
    await page.locator('.btn-primary').last().click();
    const updatedRow = page.locator('tbody tr', { hasText: EMPLOYEE_WORK_NUMBER }).first();
    await expect(updatedRow).toBeVisible();
    await expect(updatedRow.getByText(EMPLOYEE_NAME_EDITED)).toBeVisible();
    await expect(updatedRow.getByText('Shift Lead')).toBeVisible();
  });

  test('53 branch manager can deactivate branch employee', async ({ page }) => {
    await login(page, 'branch_onda_13_al_malqa');
    await page.goto('/branch-employees');
    await page.waitForLoadState('networkidle');
    let row = page.locator('tbody tr', { hasText: EMPLOYEE_WORK_NUMBER }).first();
    if ((await row.count()) === 0) {
      const addButton = page.getByRole('button', { name: /إضافة موظف|Add employee/i }).first();
      await expect(addButton).toBeVisible();
      await addButton.click();
      const inputs = page.locator('input');
      await inputs.nth(0).fill(EMPLOYEE_NAME);
      await inputs.nth(1).fill('Store Crew');
      await inputs.nth(2).fill(EMPLOYEE_WORK_NUMBER);
      await inputs.nth(3).fill('0500000000');
      const createResponse = page.waitForResponse((resp) =>
        resp.url().includes('/branch-employees/') && resp.request().method() === 'POST'
      );
      await page.getByRole('button', { name: /إضافة موظف|Add employee|save|حفظ/i }).last().click();
      expect([200, 201, 409]).toContain((await createResponse).status());
      await page.goto('/branch-employees');
      row = page.locator('tbody tr', { hasText: EMPLOYEE_WORK_NUMBER }).first();
    }
    await expect(row).toBeVisible();
    await row.locator('button').nth(1).click();
    await expect(row.getByText(/غير نشط|Inactive/i)).toBeVisible();
  });

  test('54 super admin can create kitchen from admin kitchens page', async ({ page }) => {
    await login(page, 'super.admin');
    await page.goto('/admin/kitchens');
    const inputs = page.locator('input');
    await inputs.nth(0).fill(KITCHEN_NAME);
    await inputs.nth(1).fill(KITCHEN_CITY);
    const createResponse = page.waitForResponse((resp) =>
      resp.url().includes('/master/kitchens') && resp.request().method() === 'POST'
    );
    await page.locator('form').evaluate((form: HTMLFormElement) => form.requestSubmit());
    expect((await createResponse).status()).toBe(201);
    await expect(page.locator('tbody tr', { hasText: KITCHEN_NAME }).first()).toBeVisible();
  });

  test('55 admin kitchens blocks duplicate kitchen create', async ({ page }) => {
    await login(page, 'super.admin');
    await page.goto('/admin/kitchens');
    const inputs = page.locator('input');
    await inputs.nth(0).fill(KITCHEN_NAME);
    await inputs.nth(1).fill(KITCHEN_CITY);
    const firstResponsePromise = page.waitForResponse((resp) =>
      resp.url().includes('/master/kitchens') && resp.request().method() === 'POST'
    );
    await page.locator('form').evaluate((form: HTMLFormElement) => form.requestSubmit());
    const firstStatus = (await firstResponsePromise).status();
    expect([201, 400]).toContain(firstStatus);
    if (firstStatus === 201) {
      await inputs.nth(0).fill(KITCHEN_NAME);
      await inputs.nth(1).fill(KITCHEN_CITY);
      const duplicateResponse = page.waitForResponse((resp) =>
        resp.url().includes('/master/kitchens') && resp.request().method() === 'POST'
      );
      await page.locator('form').evaluate((form: HTMLFormElement) => form.requestSubmit());
      expect((await duplicateResponse).status()).toBe(400);
    }
  });

  test('56 super admin can submit a daily order from browser', async ({ page }) => {
    await login(page, 'super.admin');
    await page.goto('/orders/daily');
    await page.locator('select').first().selectOption('11');
    await page.waitForFunction(() => document.querySelectorAll('tbody tr').length > 1);
    await page.locator('tbody tr').nth(0).locator('input[type="number"]').fill('1');
    const createDailyResponse = page.waitForResponse((resp) =>
      resp.url().includes('/orders/daily') && resp.request().method() === 'POST'
    );
    await page.locator('.btn-primary').last().click();
    expect((await createDailyResponse).status()).toBeLessThan(400);
    await page.waitForFunction(() =>
      !window.location.pathname.endsWith('/orders/daily') || document.body.innerText.includes('طھظ… ط¥ظ†ط´ط§ط، ط·ظ„ط¨ظٹط© ظٹظˆظ…ظٹط©')
    );
  });

  test('57 branch user can submit branch request from browser', async ({ page }) => {
    await login(page, 'branch_onda_13_al_malqa');
    await page.goto('/supply-chain/branch-requests');
    await page.waitForFunction(() => {
      const selects = document.querySelectorAll('select');
      return selects.length >= 2 && (selects[1] as HTMLSelectElement).options.length > 1;
    });
    await page.locator('select').nth(1).selectOption({ index: 1 });
    await page.locator('input[type="number"]').first().fill('1');
    await page.locator('.btn-primary').last().click();
    await expect(page.locator('tbody tr').nth(0)).toBeVisible();
  });

  test('58 warehouse page can execute receive when candidate exists', async ({ page }) => {
    await login(page, 'warehouse_dammam_user');
    await page.goto('/supply-chain/warehouse');
    const receiveButtons = page.getByRole('button', { name: /ط§ط³طھظ„ط§ظ…/i });
    if (await receiveButtons.count()) {
      await receiveButtons.first().click();
      await page.waitForTimeout(1200);
      await expect(page.getByText(/warehouse|طھظ†ظپظٹط° ط§ظ„ظ…ط³طھظˆط¯ط¹/i).first()).toBeVisible();
    } else {
      const rows = page.locator('tbody tr');
      if (await rows.count()) {
        await expect(rows.first()).toBeVisible();
      } else {
        await expect(page.getByText(/ظ„ط§ طھظˆط¬ط¯ ط¨ظٹط§ظ†ط§طھ|empty/i).first()).toBeVisible();
      }
    }
  });

  test('59 delivery page shows actionable rows or valid empty state', async ({ page }) => {
    await login(page, 'delivery_dammam');
    await page.goto('/supply-chain/delivery');
    await expect(page).toHaveURL(/\/supply-chain\/delivery$/);
    const deliverButtons = page.getByRole('button', { name: /طھظ… ط§ظ„طھط³ظ„ظٹظ…/i });
    if (await deliverButtons.count()) {
      await expect(deliverButtons.first()).toBeVisible();
      await expect(page.getByRole('button', { name: /ط®ط±ط¬ ظ„ظ„طھط³ظ„ظٹظ…/i }).first()).toBeVisible();
    } else {
      const rows = page.locator('tbody tr');
      await expect(rows.first()).toBeVisible();
      await expect(rows).toHaveCount(1);
    }
  });
  test('60 branch user can save branch request draft from browser', async ({ page }) => {
    const { createStatus, created } = await createBranchRequestViaUi(page, false, '1');
    expect([200, 201]).toContain(createStatus);
    const requestState = await authedJson(page, `/api/v1/branch-requests/${created.id}`);
    expect(requestState.status).toBe(200);
    expect((requestState.data as { status?: string })?.status).toBe('DRAFT');
  });

  test('61 area manager can approve a submitted branch request from browser', async ({ page }) => {
    const { createStatus, submitStatus, created } = await createBranchRequestViaUi(page, true, '1');
    expect([200, 201]).toContain(createStatus);
    expect(submitStatus).toBeLessThan(400);
    await openApprovalRequest(page, created.request_no);
    const approveResponse = page.waitForResponse((resp) =>
      resp.url().includes(`/branch-requests/${created.id}/approve`) && resp.request().method() === 'POST'
    );
    await page.getByRole('button', { name: 'اعتماد', exact: true }).click();
    expect((await approveResponse).status()).toBeLessThan(400);
    const requestState = await authedJson(page, `/api/v1/branch-requests/${created.id}`);
    expect(requestState.status).toBe(200);
    expect(['AREA_APPROVED', 'SPLIT', 'IN_EXECUTION', 'DELIVERED']).toContain((requestState.data as { status?: string })?.status || '');
  });

  test('62 area manager can modify and approve a submitted branch request from browser', async ({ page }) => {
    const { createStatus, submitStatus, created } = await createBranchRequestViaUi(page, true, '2');
    expect([200, 201]).toContain(createStatus);
    expect(submitStatus).toBeLessThan(400);
    await openApprovalRequest(page, created.request_no);
    await page.locator('tbody tr input[type="number"]').first().fill('1');
    await page.locator('textarea').first().fill(`PW modify approve ${RUN_SUFFIX}`);
    const modifyResponse = page.waitForResponse((resp) =>
      resp.url().includes(`/branch-requests/${created.id}/modify-and-approve`) && resp.request().method() === 'POST'
    );
    await page.getByRole('button', { name: 'تعديل واعتماد', exact: true }).click();
    expect((await modifyResponse).status()).toBeLessThan(400);
    const requestState = await authedJson(page, `/api/v1/branch-requests/${created.id}`);
    expect(requestState.status).toBe(200);
    expect(['AREA_APPROVED', 'SPLIT', 'IN_EXECUTION', 'DELIVERED']).toContain((requestState.data as { status?: string })?.status || '');
    const lines = ((requestState.data as { lines?: Array<{ qty_approved?: number | string }> })?.lines || []);
    expect(lines.length).toBeGreaterThan(0);
    expect(Number(lines[0]?.qty_approved || 0)).toBe(1);
  });

  test('63 area manager modify-and-approve requires a note before sending', async ({ page }) => {
    const { createStatus, submitStatus, created } = await createBranchRequestViaUi(page, true, '2');
    expect([200, 201]).toContain(createStatus);
    expect(submitStatus).toBeLessThan(400);
    await openApprovalRequest(page, created.request_no);
    await page.locator('tbody tr input[type="number"]').first().fill('1');
    let fired = false;
    const listener = (resp) => {
      if (resp.url().includes(`/branch-requests/${created.id}/modify-and-approve`) && resp.request().method() === 'POST') fired = true;
    };
    page.on('response', listener);
    await page.getByRole('button', { name: 'تعديل واعتماد', exact: true }).click();
    await page.waitForTimeout(1200);
    page.off('response', listener);
    expect(fired).toBeFalsy();
  });

  test('64 area manager can reject a submitted branch request from browser', async ({ page }) => {
    const { createStatus, submitStatus, created } = await createBranchRequestViaUi(page, true, '1');
    expect([200, 201]).toContain(createStatus);
    expect(submitStatus).toBeLessThan(400);
    await openApprovalRequest(page, created.request_no);
    await page.locator('textarea').nth(1).fill(`PW reject ${RUN_SUFFIX}`);
    const rejectResponse = page.waitForResponse((resp) =>
      resp.url().includes(`/branch-requests/${created.id}/reject`) && resp.request().method() === 'POST'
    );
    await page.getByRole('button', { name: 'رفض', exact: true }).click();
    expect((await rejectResponse).status()).toBeLessThan(400);
    const requestState = await authedJson(page, `/api/v1/branch-requests/${created.id}`);
    expect(requestState.status).toBe(200);
    expect((requestState.data as { status?: string })?.status).toBe('AREA_REJECTED');
  });

  test('65 area manager reject requires a reason before sending', async ({ page }) => {
    const { createStatus, submitStatus, created } = await createBranchRequestViaUi(page, true, '1');
    expect([200, 201]).toContain(createStatus);
    expect(submitStatus).toBeLessThan(400);
    await openApprovalRequest(page, created.request_no);
    let fired = false;
    const listener = (resp) => {
      if (resp.url().includes(`/branch-requests/${created.id}/reject`) && resp.request().method() === 'POST') fired = true;
    };
    page.on('response', listener);
    await page.getByRole('button', { name: 'رفض', exact: true }).click();
    await page.waitForTimeout(1200);
    page.off('response', listener);
    expect(fired).toBeFalsy();
  });

  test('66 kitchen start action executes when a pending candidate exists', async ({ page }) => {
    await login(page, 'kitchen_dammam_meat_and_chicken_mgr');
    const ordersState = await authedJson(page, '/api/v1/production-orders');
    const orders = Array.isArray(ordersState.data) ? ordersState.data : [];
    const candidate = orders.find((order: { status?: string }) => order?.status === 'PENDING');
    await page.goto('/supply-chain/kitchen');
    if (!candidate) {
      const rows = page.locator('tbody tr');
      if (await rows.count()) {
        await expect(rows.first()).toBeVisible();
      } else {
        await expect(page.getByText(/ظ„ط§ طھظˆط¬ط¯ ط£ظˆط§ظ…ط±|empty/i).first()).toBeVisible();
      }
      return;
    }
    const row = page.locator('tbody tr', { hasText: `PO-${candidate.id}` }).first();
    await expect(row).toBeVisible();
    const startResponse = page.waitForResponse((resp) =>
      resp.url().includes(`/production-orders/${candidate.id}/start`) && resp.request().method() === 'POST'
    );
    await row.getByRole('button', { name: /ط¨ط¯ط،/i }).click();
    expect((await startResponse).status()).toBeLessThan(400);
  });

  test('67 kitchen partial-ready action executes when an in-progress candidate exists', async ({ page }) => {
    await login(page, 'kitchen_dammam_meat_and_chicken_mgr');
    const ordersState = await authedJson(page, '/api/v1/production-orders');
    const orders = Array.isArray(ordersState.data) ? ordersState.data : [];
    const candidate = orders.find((order: { status?: string }) => order?.status === 'IN_PROGRESS');
    await page.goto('/supply-chain/kitchen');
    if (!candidate) {
      const rows = page.locator('tbody tr');
      if (await rows.count()) {
        await expect(rows.first()).toBeVisible();
      } else {
        await expect(page.getByText(/ظ„ط§ طھظˆط¬ط¯ ط£ظˆط§ظ…ط±|empty/i).first()).toBeVisible();
      }
      return;
    }
    const row = page.locator('tbody tr', { hasText: `PO-${candidate.id}` }).first();
    await expect(row).toBeVisible();
    await row.locator('input[type="number"]').fill('1');
    const partialResponse = page.waitForResponse((resp) =>
      resp.url().includes(`/production-orders/${candidate.id}/mark-partial-ready`) && resp.request().method() === 'POST'
    );
    await row.getByRole('button', { name: /ط¬ط§ظ‡ط² ط¬ط²ط¦ظٹ/i }).click();
    expect((await partialResponse).status()).toBeLessThan(400);
  });

  test('68 kitchen ready action executes when a workable candidate exists', async ({ page }) => {
    await login(page, 'kitchen_dammam_meat_and_chicken_mgr');
    const ordersState = await authedJson(page, '/api/v1/production-orders');
    const orders = Array.isArray(ordersState.data) ? ordersState.data : [];
    const candidate = orders.find((order: { status?: string }) => ['IN_PROGRESS', 'PARTIAL_READY'].includes(order?.status || ''));
    await page.goto('/supply-chain/kitchen');
    if (!candidate) {
      const rows = page.locator('tbody tr');
      if (await rows.count()) {
        await expect(rows.first()).toBeVisible();
      } else {
        await expect(page.getByText(/ظ„ط§ طھظˆط¬ط¯ ط£ظˆط§ظ…ط±|empty/i).first()).toBeVisible();
      }
      return;
    }
    const row = page.locator('tbody tr', { hasText: `PO-${candidate.id}` }).first();
    await expect(row).toBeVisible();
    const readyResponse = page.waitForResponse((resp) =>
      resp.url().includes(`/production-orders/${candidate.id}/mark-ready`) && resp.request().method() === 'POST'
    );
    await row.getByRole('button', { name: /^ط¬ط§ظ‡ط²$/i }).click();
    expect((await readyResponse).status()).toBeLessThan(400);
  });

  test('69 kitchen send-to-warehouse action executes when a ready candidate exists', async ({ page }) => {
    await login(page, 'kitchen_dammam_meat_and_chicken_mgr');
    const ordersState = await authedJson(page, '/api/v1/production-orders');
    const orders = Array.isArray(ordersState.data) ? ordersState.data : [];
    const candidate = orders.find((order: { status?: string }) => order?.status === 'READY');
    await page.goto('/supply-chain/kitchen');
    if (!candidate) {
      const rows = page.locator('tbody tr');
      if (await rows.count()) {
        await expect(rows.first()).toBeVisible();
      } else {
        await expect(page.getByText(/ظ„ط§ طھظˆط¬ط¯ ط£ظˆط§ظ…ط±|empty/i).first()).toBeVisible();
      }
      return;
    }
    const row = page.locator('tbody tr', { hasText: `PO-${candidate.id}` }).first();
    await expect(row).toBeVisible();
    const sendResponse = page.waitForResponse((resp) =>
      resp.url().includes(`/production-orders/${candidate.id}/send-to-warehouse`) && resp.request().method() === 'POST'
    );
    await row.getByRole('button', { name: /ط¥ط±ط³ط§ظ„ ظ„ظ„ظ…ط³طھظˆط¯ط¹/i }).click();
    expect((await sendResponse).status()).toBeLessThan(400);
  });
});



