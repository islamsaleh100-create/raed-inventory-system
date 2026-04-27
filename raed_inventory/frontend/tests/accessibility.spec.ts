import { test, expect, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

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
    if (status === 429 && attempt < 2) continue;
    expect(status).toBeLessThan(400);
    await page.waitForURL(/\/dashboard|\/supply-chain\/control/);
    return;
  }
}

async function expectNoA11yViolations(page: Page, name: string) {
  await page.waitForLoadState('networkidle');
  const results = await new AxeBuilder({ page }).analyze();
  const summary = results.violations.map((v) => `${v.id}: ${v.impact}`).join('\n');
  expect(results.violations, `${name} accessibility violations:\n${summary}`).toEqual([]);
}

test.describe('Accessibility audit', () => {
  test.describe.configure({ mode: 'serial' });

  test('login page has no axe violations', async ({ page }) => {
    await page.goto('/login');
    await expect(page).toHaveURL(/\/login$/);
    await expectNoA11yViolations(page, 'login');
  });

  test('control center has no axe violations for super admin', async ({ page }) => {
    await login(page, 'super.admin');
    await page.goto('/supply-chain/control');
    await expect(page).toHaveURL(/\/supply-chain\/control$/);
    await expectNoA11yViolations(page, 'control center');
  });

  test('branch requests page has no axe violations for branch user', async ({ page }) => {
    await login(page, 'branch_onda_13_al_malqa');
    await page.goto('/supply-chain/branch-requests');
    await page.waitForFunction(() => {
      const selects = document.querySelectorAll('select');
      return selects.length >= 3 && (selects[1] as HTMLSelectElement).options.length > 1;
    });
    await page.locator('select').nth(1).selectOption({ index: 1 });
    await page.locator('input[type="number"]').first().fill('1');
    await expectNoA11yViolations(page, 'branch requests');
  });

  test('daily order page has no axe violations after branch load', async ({ page }) => {
    await login(page, 'super.admin');
    await page.goto('/orders/daily');
    await page.locator('select').first().selectOption('11');
    await page.waitForFunction(() => document.querySelectorAll('tbody tr').length > 1);
    await expectNoA11yViolations(page, 'daily order');
  });

  test('warehouse page has no axe violations for warehouse user', async ({ page }) => {
    await login(page, 'warehouse_dammam_user');
    await page.goto('/supply-chain/warehouse');
    await expect(page).toHaveURL(/\/supply-chain\/warehouse$/);
    await expectNoA11yViolations(page, 'warehouse');
  });

  test('delivery page has no axe violations for delivery user', async ({ page }) => {
    await login(page, 'delivery_dammam');
    await page.goto('/supply-chain/delivery');
    await expect(page).toHaveURL(/\/supply-chain\/delivery$/);
    await expectNoA11yViolations(page, 'delivery');
  });

  test('branch employees page has no axe violations for branch manager', async ({ page }) => {
    await login(page, 'branch_onda_13_al_malqa');
    await page.goto('/branch-employees');
    await expect(page).toHaveURL(/\/branch-employees$/);
    await expectNoA11yViolations(page, 'branch employees');
  });

  test('admin kitchens page has no axe violations for super admin', async ({ page }) => {
    await login(page, 'super.admin');
    await page.goto('/admin/kitchens');
    await expect(page).toHaveURL(/\/admin\/kitchens$/);
    await expectNoA11yViolations(page, 'admin kitchens');
  });
});
