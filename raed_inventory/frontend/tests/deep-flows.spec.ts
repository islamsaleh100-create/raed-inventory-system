import { test, expect, type Page } from '@playwright/test';

const RUN_SUFFIX = String(Date.now()).slice(-8);
const FLOW_EMPLOYEE_NAME = `Flow Employee ${RUN_SUFFIX}`;
const FLOW_EMPLOYEE_NAME_EDITED = `Flow Employee Edited ${RUN_SUFFIX}`;
const FLOW_EMPLOYEE_WORK_NUMBER = `FLOW-${RUN_SUFFIX}`;
const FLOW_KITCHEN_NAME = `Flow Kitchen ${RUN_SUFFIX}`;
const FLOW_KITCHEN_CITY = `Flow City ${RUN_SUFFIX}`;

async function login(page: Page, username: string, password = 'Raed@2025') {
  await page.goto('/login');
  await page.evaluate(() => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('persist:root');
    sessionStorage.clear();
  });
  await page.context().clearCookies();
  await page.goto('/login');
  await page.locator('input').nth(0).fill(username);
  await page.locator('input').nth(1).fill(password);
  const submitButton = page.locator('button[type="submit"]').first();
  await expect(submitButton).toBeVisible();
  for (let attempt = 0; attempt < 3; attempt += 1) {
    if (attempt > 0) await page.waitForTimeout(3500);
    else await page.waitForTimeout(3200);
    const loginResponse = page.waitForResponse((resp) =>
      resp.url().includes('/api/v1/auth/login') && resp.request().method() === 'POST'
    );
    await submitButton.click();
    const status = (await loginResponse).status();
    if (status === 429 && attempt < 2) continue;
    expect(status).toBeLessThan(400);
    await page.waitForURL(/\/dashboard|\/supply-chain\/control/);
    return;
  }
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

async function createBranchRequestViaUi(page: Page, submitAfter = true, qty = '1') {
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

test.describe('Raed deep browser flows', () => {
  test.describe.configure({ mode: 'serial' });

  test('01 branch submit to area approve completes across roles', async ({ page }) => {
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

  test('02 branch submit to area modify-and-approve updates approved quantity', async ({ page }) => {
    const { createStatus, submitStatus, created } = await createBranchRequestViaUi(page, true, '2');
    expect([200, 201]).toContain(createStatus);
    expect(submitStatus).toBeLessThan(400);

    await openApprovalRequest(page, created.request_no);
    await page.locator('tbody tr input[type="number"]').first().fill('1');
    await page.locator('textarea').first().fill(`Deep flow modify ${RUN_SUFFIX}`);
    const modifyResponse = page.waitForResponse((resp) =>
      resp.url().includes(`/branch-requests/${created.id}/modify-and-approve`) && resp.request().method() === 'POST'
    );
    await page.getByRole('button', { name: 'تعديل واعتماد', exact: true }).click();
    expect((await modifyResponse).status()).toBeLessThan(400);

    const requestState = await authedJson(page, `/api/v1/branch-requests/${created.id}`);
    expect(requestState.status).toBe(200);
    const lines = ((requestState.data as { lines?: Array<{ qty_approved?: number | string }> })?.lines || []);
    expect(lines.length).toBeGreaterThan(0);
    expect(Number(lines[0]?.qty_approved || 0)).toBe(1);
  });

  test('03 branch submit to area reject ends in rejected status', async ({ page }) => {
    const { createStatus, submitStatus, created } = await createBranchRequestViaUi(page, true, '1');
    expect([200, 201]).toContain(createStatus);
    expect(submitStatus).toBeLessThan(400);

    await openApprovalRequest(page, created.request_no);
    await page.locator('textarea').nth(1).fill(`Deep flow reject ${RUN_SUFFIX}`);
    const rejectResponse = page.waitForResponse((resp) =>
      resp.url().includes(`/branch-requests/${created.id}/reject`) && resp.request().method() === 'POST'
    );
    await page.getByRole('button', { name: 'رفض', exact: true }).click();
    expect((await rejectResponse).status()).toBeLessThan(400);

    const requestState = await authedJson(page, `/api/v1/branch-requests/${created.id}`);
    expect(requestState.status).toBe(200);
    expect((requestState.data as { status?: string })?.status).toBe('AREA_REJECTED');
  });

  test('04 branch employee lifecycle create edit deactivate completes', async ({ page }) => {
    await login(page, 'branch_onda_13_al_malqa');
    await page.goto('/branch-employees');

    await page.getByRole('button', { name: /إضافة موظف|Add employee/i }).first().click();
    const inputs = page.locator('input');
    await inputs.nth(0).fill(FLOW_EMPLOYEE_NAME);
    await inputs.nth(1).fill('Store Crew');
    await inputs.nth(2).fill(FLOW_EMPLOYEE_WORK_NUMBER);
    await inputs.nth(3).fill('0500000000');
    await page.getByRole('button', { name: /إضافة موظف|Add employee|save|حفظ/i }).last().click();
    let row = page.locator('tbody tr', { hasText: FLOW_EMPLOYEE_WORK_NUMBER }).first();
    await expect(row).toBeVisible();
    await expect(row.getByText(FLOW_EMPLOYEE_NAME)).toBeVisible();

    await row.locator('button').nth(0).click();
    await page.locator('input').nth(0).fill(FLOW_EMPLOYEE_NAME_EDITED);
    await page.locator('input').nth(1).fill('Shift Lead');
    await page.locator('.btn-primary').last().click();
    row = page.locator('tbody tr', { hasText: FLOW_EMPLOYEE_WORK_NUMBER }).first();
    await expect(row).toBeVisible();
    await expect(row.getByText(FLOW_EMPLOYEE_NAME_EDITED)).toBeVisible();
    await expect(row.getByText('Shift Lead')).toBeVisible();

    await row.locator('button').nth(1).click();
    await expect(row.getByText(/غير نشط|Inactive/i)).toBeVisible();
  });

  test('05 kitchen admin create then duplicate block completes', async ({ page }) => {
    await login(page, 'super.admin');
    await page.goto('/admin/kitchens');
    const inputs = page.locator('input');
    await inputs.nth(0).fill(FLOW_KITCHEN_NAME);
    await inputs.nth(1).fill(FLOW_KITCHEN_CITY);
    const createResponse = page.waitForResponse((resp) =>
      resp.url().includes('/master/kitchens') && resp.request().method() === 'POST'
    );
    await page.locator('form').evaluate((form: HTMLFormElement) => form.requestSubmit());
    expect((await createResponse).status()).toBe(201);
    await expect(page.locator('tbody tr', { hasText: FLOW_KITCHEN_NAME }).first()).toBeVisible();

    await inputs.nth(0).fill(FLOW_KITCHEN_NAME);
    await inputs.nth(1).fill(FLOW_KITCHEN_CITY);
    const duplicateResponse = page.waitForResponse((resp) =>
      resp.url().includes('/master/kitchens') && resp.request().method() === 'POST'
    );
    await page.locator('form').evaluate((form: HTMLFormElement) => form.requestSubmit());
    expect((await duplicateResponse).status()).toBe(400);
  });

  test('06 warehouse can receive a pending branch-request line when candidate exists', async ({ page }) => {
    await login(page, 'warehouse_dammam_user');
    const linesState = await authedJson(page, '/api/v1/warehouse-lines');
    const lines = Array.isArray(linesState.data) ? linesState.data : [];
    const candidate = lines.find((line: { source_type?: string; status?: string }) =>
      line?.source_type === 'BRANCH_REQUEST' && line?.status === 'PENDING'
    );
    await page.goto('/supply-chain/warehouse');
    if (!candidate) {
      const rows = page.locator('tbody tr');
      if (await rows.count()) await expect(rows.first()).toBeVisible();
      else await expect(page.getByText(/لا توجد بيانات|empty/i).first()).toBeVisible();
      return;
    }
    const row = page.locator('tbody tr', { hasText: `WL-${candidate.id}` }).first();
    await expect(row).toBeVisible();
    const receiveResponse = page.waitForResponse((resp) =>
      resp.url().includes(`/warehouse-lines/${candidate.id}/receive`) && resp.request().method() === 'POST'
    );
    await row.getByRole('button', { name: /استلام/i }).click();
    expect((await receiveResponse).status()).toBeLessThan(400);
  });

  test('07 warehouse can create delivery order and delivery user can move it to delivered', async ({ page }) => {
    await login(page, 'warehouse_dammam_user');
    const beforeOrdersState = await authedJson(page, '/api/v1/delivery-orders');
    const beforeOrders = Array.isArray(beforeOrdersState.data) ? beforeOrdersState.data : [];
    await page.goto('/supply-chain/warehouse');

    const rows = page.locator('tbody tr');
    if (!(await rows.count())) {
      await expect(page.getByText(/لا توجد بيانات|empty/i).first()).toBeVisible();
      return;
    }

    const createButtons = page.getByRole('button', { name: /إنشاء أمر تسليم/i });
    if (!(await createButtons.count())) {
      await expect(rows.first()).toBeVisible();
      return;
    }

    const createDeliveryResponse = page.waitForResponse((resp) =>
      resp.url().includes('/delivery-orders') && resp.request().method() === 'POST'
    );
    await createButtons.first().click();
    expect((await createDeliveryResponse).status()).toBeLessThan(400);

    const afterOrdersState = await authedJson(page, '/api/v1/delivery-orders');
    const afterOrders = Array.isArray(afterOrdersState.data) ? afterOrdersState.data : [];
    const createdOrder = afterOrders.find((order: { id?: number }) =>
      !beforeOrders.some((prev: { id?: number }) => prev?.id === order?.id)
    ) || afterOrders[0];
    expect(createdOrder?.id).toBeTruthy();

    await login(page, 'delivery_dammam');
    await page.goto('/supply-chain/delivery');
    const orderRow = page.locator('tbody tr', { hasText: `DO-${createdOrder.id}` }).first();
    await expect(orderRow).toBeVisible();

    const outResponse = page.waitForResponse((resp) =>
      resp.url().includes(`/delivery-orders/${createdOrder.id}/out`) && resp.request().method() === 'POST'
    );
    await orderRow.getByRole('button', { name: /خرج للتسليم/i }).click();
    expect((await outResponse).status()).toBeLessThan(400);

    await orderRow.locator('input').nth(0).fill(`Receiver ${RUN_SUFFIX}`);
    await orderRow.locator('input').nth(1).fill(`Delivered by flow ${RUN_SUFFIX}`);
    const deliveredResponse = page.waitForResponse((resp) =>
      resp.url().includes(`/delivery-orders/${createdOrder.id}/deliver`) && resp.request().method() === 'POST'
    );
    await orderRow.getByRole('button', { name: /تم التسليم/i }).click();
    expect((await deliveredResponse).status()).toBeLessThan(400);

    const deliveredState = await authedJson(page, `/api/v1/delivery-orders/${createdOrder.id}`);
    if (deliveredState.status === 200) {
      expect((deliveredState.data as { status?: string })?.status).toBe('DELIVERED');
    }
  });

  test('08 warehouse can full-issue an available line when candidate exists', async ({ page }) => {
    await login(page, 'warehouse_dammam_user');
    const linesState = await authedJson(page, '/api/v1/warehouse-lines');
    const lines = Array.isArray(linesState.data) ? linesState.data : [];
    const candidate = lines.find((line: { status?: string; pending_qty?: number | string }) =>
      line?.status === 'AVAILABLE' && Number(line?.pending_qty || 0) > 0
    );
    await page.goto('/supply-chain/warehouse');
    if (!candidate) {
      const rows = page.locator('tbody tr');
      if (await rows.count()) await expect(rows.first()).toBeVisible();
      else await expect(page.getByText(/لا توجد بيانات|empty/i).first()).toBeVisible();
      return;
    }
    const row = page.locator('tbody tr', { hasText: `WL-${candidate.id}` }).first();
    await expect(row).toBeVisible();
    const issueResponse = page.waitForResponse((resp) =>
      resp.url().includes(`/warehouse-lines/${candidate.id}/issue`) && resp.request().method() === 'POST'
    );
    await row.getByRole('button', { name: /صرف كامل/i }).click();
    expect((await issueResponse).status()).toBeLessThan(400);
  });

  test('09 warehouse can partial-issue a line when candidate exists', async ({ page }) => {
    await login(page, 'warehouse_dammam_user');
    const linesState = await authedJson(page, '/api/v1/warehouse-lines');
    const lines = Array.isArray(linesState.data) ? linesState.data : [];
    const candidate = lines.find((line: { status?: string; pending_qty?: number | string }) =>
      ['AVAILABLE', 'PENDING'].includes(line?.status || '') && Number(line?.pending_qty || 0) > 1
    );
    await page.goto('/supply-chain/warehouse');
    if (!candidate) {
      const rows = page.locator('tbody tr');
      if (await rows.count()) await expect(rows.first()).toBeVisible();
      else await expect(page.getByText(/لا توجد بيانات|empty/i).first()).toBeVisible();
      return;
    }
    const row = page.locator('tbody tr', { hasText: `WL-${candidate.id}` }).first();
    await expect(row).toBeVisible();
    await row.locator('input[type="number"]').fill('1');
    const partialResponse = page.waitForResponse((resp) =>
      resp.url().includes(`/warehouse-lines/${candidate.id}/partial-issue`) && resp.request().method() === 'POST'
    );
    await row.getByRole('button', { name: /صرف جزئي/i }).click();
    expect((await partialResponse).status()).toBeLessThan(400);
  });

  test('10 warehouse can save delay reason when candidate exists', async ({ page }) => {
    await login(page, 'warehouse_dammam_user');
    const linesState = await authedJson(page, '/api/v1/warehouse-lines');
    const lines = Array.isArray(linesState.data) ? linesState.data : [];
    const candidate = lines.find((line: { status?: string }) =>
      ['AVAILABLE', 'PENDING', 'BACKORDER'].includes(line?.status || '')
    );
    await page.goto('/supply-chain/warehouse');
    if (!candidate) {
      const rows = page.locator('tbody tr');
      if (await rows.count()) await expect(rows.first()).toBeVisible();
      else await expect(page.getByText(/لا توجد بيانات|empty/i).first()).toBeVisible();
      return;
    }
    const row = page.locator('tbody tr', { hasText: `WL-${candidate.id}` }).first();
    await expect(row).toBeVisible();
    await row.locator('input[type="text"]').last().fill(`Flow delay ${RUN_SUFFIX}`);
    const delayResponse = page.waitForResponse((resp) =>
      resp.url().includes(`/warehouse-lines/${candidate.id}/delay-reason`) && resp.request().method() === 'POST'
    );
    await row.getByRole('button', { name: /تسجيل تأخير/i }).click();
    expect((await delayResponse).status()).toBeLessThan(400);
  });
});
