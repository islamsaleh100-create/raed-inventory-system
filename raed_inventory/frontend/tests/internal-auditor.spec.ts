import { test, expect, type Page } from '@playwright/test'

async function login(page: Page, username: string, password = 'Raed@2025') {
  await page.goto('/login')
  await page.evaluate(() => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('user')
    localStorage.removeItem('persist:root')
    sessionStorage.clear()
  })
  await page.context().clearCookies()
  await page.goto('/login')
  await page.waitForURL(/\/login/, { timeout: 15000 })
  await expect(page.locator('input').nth(0)).toBeVisible({ timeout: 15000 })
  await expect(page.locator('input').nth(1)).toBeVisible({ timeout: 15000 })
  await page.locator('input').nth(0).fill(username)
  await page.locator('input').nth(1).fill(password)
  const submitButton = page.locator('button[type="submit"]').first()
  await expect(submitButton).toBeVisible()
  for (let attempt = 0; attempt < 3; attempt += 1) {
    if (attempt > 0) await page.waitForTimeout(3500)
    else await page.waitForTimeout(3200)
    const loginResponse = page.waitForResponse((resp) =>
      resp.url().includes('/api/v1/auth/login') && resp.request().method() === 'POST'
    )
    await submitButton.click()
    const status = (await loginResponse).status()
    if (status === 429 && attempt < 2) continue
    expect(status).toBeLessThan(400)
    await page.waitForURL(/\/audit\/dashboard/)
    return
  }
}

async function authedJson(page: Page, path: string, init?: { method?: string; body?: unknown }) {
  return await page.evaluate(async ({ path, init }) => {
    const token = localStorage.getItem('access_token')
    const response = await fetch(path, {
      method: init?.method || 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: init?.body ? JSON.stringify(init.body) : undefined,
    })
    const text = await response.text()
    let data: unknown = null
    try {
      data = text ? JSON.parse(text) : null
    } catch {
      data = text
    }
    return { status: response.status, data }
  }, { path, init })
}

test.describe('Internal auditor browser coverage', () => {
  test.describe.configure({ mode: 'serial' })

  test('01 auditor lands on audit dashboard and sees audit nav', async ({ page }) => {
    await login(page, 'audit.officer')
    await expect(page).toHaveURL(/\/audit\/dashboard/)
    await expect(page.getByRole('heading', { name: /لوحة المراجع|Auditor dashboard/i })).toBeVisible()
    await expect(page.getByText(/ملاحظات المراجعة|Audit findings/i)).toBeVisible()
    await expect(page.getByText(/سجل العمليات|Audit trail/i)).toBeVisible()
  })

  test('02 auditor can create finding but cannot perform operational write', async ({ page }) => {
    await login(page, 'audit.officer')

    await page.goto('/audit/findings')
    await expect(page.getByRole('heading', { name: /ملاحظات المراجعة|Audit findings/i }).first()).toBeVisible()
    const findingForm = page.locator('form').first()
    await findingForm.locator('input').nth(0).fill('branch_request')
    await findingForm.locator('input').nth(1).fill('1')
    await findingForm.locator('select').first().selectOption('warning')
    await findingForm.locator('input').nth(2).fill('مخالفة تجريبية للمراجعة')
    await findingForm.locator('textarea').fill('هذه ملاحظة مراجعة تجريبية للتأكد من صلاحية الإنشاء للمراجع الداخلي.')
    const findingResponse = page.waitForResponse((resp) =>
      /\/api\/v1\/audit\/findings$/.test(resp.url()) && resp.request().method() === 'POST'
    )
    await findingForm.getByRole('button', { name: /إضافة ملاحظة|Create finding/i }).click()
    expect((await findingResponse).status()).toBeLessThan(400)

    const blocked = await authedJson(page, '/api/v1/branch-requests/1/approve', {
      method: 'POST',
      body: { approval_note: 'should be blocked' },
    })
    expect(blocked.status).toBe(403)
  })

  test('03 auditor sees read-only branch approvals without action buttons', async ({ page }) => {
    await login(page, 'audit.officer')
    await page.goto('/supply-chain/approvals')
    await expect(page.getByText(/قراءة فقط|المراجع الداخلي يستطيع مراجعة الطلبات/i).first()).toBeVisible()
    await expect(page.getByRole('button', { name: 'اعتماد', exact: true })).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'تعديل واعتماد', exact: true })).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'رفض', exact: true })).toHaveCount(0)
  })

  test('04 auditor sees read-only warehouse and delivery screens', async ({ page }) => {
    await login(page, 'audit.officer')

    await page.goto('/supply-chain/warehouse')
    await expect(page.getByText(/قراءة فقط|المراجع الداخلي يرى خطوط المستودع/i).first()).toBeVisible()
    await expect(page.getByRole('button', { name: 'استلام', exact: true })).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'صرف كامل', exact: true })).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'إنشاء أمر تسليم', exact: true })).toHaveCount(0)

    await page.goto('/supply-chain/delivery')
    await expect(page.getByText(/قراءة فقط|المراجع الداخلي يرى أوامر التوصيل/i).first()).toBeVisible()
    await expect(page.getByRole('button', { name: 'خرج للتسليم', exact: true })).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'تم التسليم', exact: true })).toHaveCount(0)
  })

  test('05 auditor can inspect quality and training in read-only mode', async ({ page }) => {
    await login(page, 'audit.officer')

    await page.goto('/quality')
    await expect(page.getByText(/قراءة فقط|read-only/i).first()).toBeVisible()
    await expect(page.getByRole('link', { name: /زيارة جديدة|new visit/i })).toHaveCount(0)

    const qualityList = await authedJson(page, '/api/v1/quality/?page=1&page_size=1')
    const qualityData: any = qualityList.data
    const qualityItems = Array.isArray(qualityData?.items) ? qualityData.items : Array.isArray(qualityData) ? qualityData : []
    if (qualityItems.length) {
      await page.goto(`/quality/${qualityItems[0].id}`)
      await expect(page.getByText(/ملاحظات المراجعة|Audit findings/i).first()).toBeVisible()
      await expect(page.getByRole('button', { name: /submit|review|close|delete|إرسال|مراجعة|إغلاق|حذف/i })).toHaveCount(0)
    }

    await page.goto('/training')
    await expect(page.getByText(/قراءة فقط|read-only/i).first()).toBeVisible()
    await expect(page.getByRole('link', { name: /تقييم جديد|new assessment/i })).toHaveCount(0)

    const trainingList = await authedJson(page, '/api/v1/training/?page=1&page_size=1')
    const trainingData: any = trainingList.data
    const trainingItems = Array.isArray(trainingData?.items) ? trainingData.items : Array.isArray(trainingData) ? trainingData : []
    if (trainingItems.length) {
      await page.goto(`/training/${trainingItems[0].id}`)
      await expect(page.getByText(/ملاحظات المراجعة|Audit findings/i).first()).toBeVisible()
      await expect(page.getByRole('button', { name: /approve|reject|submit|اعتماد|رفض|إرسال/i })).toHaveCount(0)
    }
  })

  test('06 auditor can inspect documents in read-only mode', async ({ page }) => {
    await login(page, 'audit.officer')

    await page.goto('/documents')
    await expect(page.getByText(/قراءة فقط|read-only/i).first()).toBeVisible()
    await expect(page.getByRole('button', { name: /وثيقة جديدة|new/i })).toHaveCount(0)

    const docsList = await authedJson(page, '/api/v1/documents/?owner_type=branch')
    const docsData: any = docsList.data
    const docsItems = Array.isArray(docsData) ? docsData : []
    if (docsItems.length) {
      await page.goto(`/documents/${docsItems[0].id}`)
      await expect(page.getByText(/ملاحظات المراجعة|Audit findings/i).first()).toBeVisible()
      await expect(page.getByRole('button', { name: /renew|delete|upload|تجديد|حذف|رفع/i })).toHaveCount(0)
      await expect(page.locator('input, textarea, select').first()).toBeDisabled()
    }
  })

  test('07 dashboard open findings cards drill into filtered findings', async ({ page }) => {
    await login(page, 'audit.officer')
    await page.goto('/audit/dashboard')
    await page.locator('button').filter({ hasText: /إجمالي الملاحظات المفتوحة|Open findings/i }).first().click()
    await expect(page).toHaveURL(/\/audit\/findings\?status=open/)
    await expect(page.locator('select').nth(1)).toHaveValue('open')
  })

  test('08 dashboard operational cards drill into approvals and warehouse', async ({ page }) => {
    await login(page, 'audit.officer')
    await page.goto('/audit/dashboard')

    await page.locator('button').filter({ hasText: /متوسط زمن الاعتماد|Average approval time/i }).first().click()
    await expect(page).toHaveURL(/\/supply-chain\/approvals/)
    await expect(page.getByRole('button', { name: 'اعتماد', exact: true })).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'تعديل واعتماد', exact: true })).toHaveCount(0)

    await page.goto('/audit/dashboard')
    await page.locator('button').filter({ hasText: /تأخيرات بدون سبب|Delays without reason/i }).first().click()
    await expect(page).toHaveURL(/\/supply-chain\/warehouse/)
    await expect(page.getByText(/قراءة فقط|read-only/i).first()).toBeVisible()
  })

  test('09 dashboard backlog tiles drill into supply chain pages', async ({ page }) => {
    await login(page, 'audit.officer')
    await page.goto('/audit/dashboard')

    await page.locator('button').filter({ hasText: /طلبات الفروع المرسلة|branch requests submitted/i }).first().click()
    await expect(page).toHaveURL(/\/supply-chain\/branch-requests/)

    await page.goto('/audit/dashboard')
    await page.locator('button').filter({ hasText: /أوامر الإنتاج المفتوحة|production open/i }).first().click()
    await expect(page).toHaveURL(/\/supply-chain\/kitchen/)
  })

  test('10 auditor can inspect audit trail details', async ({ page }) => {
    await login(page, 'audit.officer')
    await page.goto('/audit/trail')
    await expect(page.getByRole('heading', { name: /سجل العمليات|Audit trail/i }).first()).toBeVisible()
    const viewButtons = page.getByRole('button', { name: /عرض|view/i })
    const buttonCount = await viewButtons.count()
    if (buttonCount > 0) {
      await viewButtons.first().click()
      await expect(page.getByText(/Old values|القيم السابقة/i).first()).toBeVisible()
      await page.keyboard.press('Escape')
    }
  })

  test('11 auditor cannot access write creation routes', async ({ page }) => {
    await login(page, 'audit.officer')

    await page.goto('/training/new')
    await expect(page.getByText(/غير مصرّح|Access denied/i).first()).toBeVisible()

    await page.goto('/documents/new')
    await expect(page.getByText(/غير مصرّح|Access denied/i).first()).toBeVisible()
  })

  test('12 findings query params prefill filters and exports are reachable', async ({ page }) => {
    await login(page, 'audit.officer')
    await page.goto('/audit/findings?status=open&severity=warning')
    await expect(page.locator('select').nth(0)).toHaveValue('warning')
    await expect(page.locator('select').nth(1)).toHaveValue('open')

    const exportStatus = await page.evaluate(async () => {
      const token = localStorage.getItem('access_token')
      const resp = await fetch('/api/v1/audit/findings/export.csv?status=open', {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      return resp.status
    })
    expect(exportStatus).toBe(200)
  })

  test('13 audit findings and trail pages do not expose raw ui keys', async ({ page }) => {
    await login(page, 'audit.officer')

    await page.goto('/audit/findings')
    await expect(page.getByText('common.view')).toHaveCount(0)
    await expect(page.getByPlaceholder(/entity_type/i)).toHaveCount(0)
    await expect(page.getByPlaceholder(/entity_id/i)).toHaveCount(0)
    await expect(page.getByPlaceholder(/created_by/i)).toHaveCount(0)

    await page.goto('/audit/trail')
    await expect(page.getByText('common.view')).toHaveCount(0)
    await expect(page.getByPlaceholder(/entity_type/i)).toHaveCount(0)
    await expect(page.getByPlaceholder(/entity_id/i)).toHaveCount(0)
    await expect(page.getByPlaceholder(/user_id/i)).toHaveCount(0)

    const trailViewButtons = page.getByRole('button', { name: /عرض|details/i })
    if (await trailViewButtons.count()) {
      await trailViewButtons.first().click()
      await expect(page.getByText(/القيم السابقة|Old values/i)).toBeVisible()
      await expect(page.getByText(/القيم الجديدة|New values/i)).toBeVisible()
      await expect(page.getByText(/branch_employees|branch_employee_created/)).toHaveCount(0)
      await page.keyboard.press('Escape')
    }
  })
})
