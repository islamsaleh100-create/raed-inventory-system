import { test, expect, type Page } from '@playwright/test';

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

async function expectPath(page: Page, path: string) {
  await page.goto(path);
  await expect(page).toHaveURL(new RegExp(path.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '$'));
}

test.describe('Raed secondary surfaces browser review', () => {
  test.describe.configure({ mode: 'serial' });

  test('01 super admin can open users admin page', async ({ page }) => {
    await login(page, 'super.admin');
    await expectPath(page, '/admin/users');
    await expect(page.locator('table, form, input').first()).toBeVisible();
  });

  test('02 super admin can open branches admin page', async ({ page }) => {
    await login(page, 'super.admin');
    await expectPath(page, '/admin/branches');
    await expect(page.locator('table, form, input, select').first()).toBeVisible();
  });

  test('03 super admin can open warehouses admin page', async ({ page }) => {
    await login(page, 'super.admin');
    await expectPath(page, '/admin/warehouses');
    await expect(page.locator('table, form, input').first()).toBeVisible();
  });

  test('04 super admin can open items admin page', async ({ page }) => {
    await login(page, 'super.admin');
    await expectPath(page, '/admin/items');
    await expect(page.locator('table, form, input, select').first()).toBeVisible();
  });

  test('05 super admin can open settings page', async ({ page }) => {
    await login(page, 'super.admin');
    await expectPath(page, '/admin/settings');
    await expect(page.locator('main button, main input, main select, main textarea').first()).toBeVisible();
  });

  test('06 super admin can open quality analytics', async ({ page }) => {
    await login(page, 'super.admin');
    await expectPath(page, '/quality/analytics');
    await expect(page.locator('main h1').first()).toBeVisible();
  });

  test('07 super admin can open training assessments list', async ({ page }) => {
    await login(page, 'super.admin');
    await expectPath(page, '/training');
    await expect(page.locator('main h1').first()).toBeVisible();
  });

  test('08 super admin can open training analytics', async ({ page }) => {
    await login(page, 'super.admin');
    await expectPath(page, '/training/analytics');
    await expect(page.locator('main h1').first()).toBeVisible();
  });

  test('09 super admin can open documents list', async ({ page }) => {
    await login(page, 'super.admin');
    await expectPath(page, '/documents');
    await expect(page.locator('main h1').first()).toBeVisible();
  });

  test('10 warehouse manager can open analytics pages allowed to warehouse role', async ({ page }) => {
    await login(page, 'warehouse_riyadh_manager');
    await expectPath(page, '/analytics/consumption-trend');
    await expect(page.locator('main h1').first()).toBeVisible();
    await expectPath(page, '/analytics/order-delay');
    await expect(page.locator('main h1').first()).toBeVisible();
  });
});
