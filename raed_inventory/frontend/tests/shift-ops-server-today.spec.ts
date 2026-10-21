/**
 * Server business date UI (U3b fix) — LOCAL stack only.
 * Env: BASE_URL, SHOTS_DIR, API_URL (optional, default BASE_URL proxy),
 *      ST_BM_USER, ST_BM_PASS, ST_ADMIN_USER, ST_ADMIN_PASS (no credentials in repo).
 */
import { test, expect } from '@playwright/test'
import fs from 'fs'
import path from 'path'
import { execSync } from 'child_process'

const BASE = process.env.BASE_URL || process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:5174'
const SHOTS = process.env.SHOTS_DIR || path.join('predeploy-shots', 'server-today')
const API = process.env.API_URL || `${BASE.replace(/\/$/, '')}/api/v1`

const BM_USER = process.env.ST_BM_USER
const BM_PASS = process.env.ST_BM_PASS
const ADMIN_USER = process.env.ST_ADMIN_USER
const ADMIN_PASS = process.env.ST_ADMIN_PASS

function requireEnv(name: string, value: string | undefined): string {
  if (!value) throw new Error(`${name} is required for local Playwright runs`)
  return value
}
const CLEANUP_PY = process.env.ST_CLEANUP_PY

function cleanupPdShifts() {
  if (!CLEANUP_PY) return
  execSync(`python "${CLEANUP_PY}"`, { stdio: 'inherit' })
}

function addDaysIso(iso: string, delta: number) {
  const [y, m, d] = iso.split('-').map(Number)
  const dt = new Date(Date.UTC(y, m - 1, d + delta))
  return dt.toISOString().slice(0, 10)
}

function shotPath(name: string) {
  fs.mkdirSync(SHOTS, { recursive: true })
  return path.join(SHOTS, name)
}

async function saveShot(page: import('@playwright/test').Page, name: string) {
  const p = shotPath(name)
  await page.screenshot({ path: p, fullPage: true })
  const st = fs.statSync(p)
  expect(st.size).toBeGreaterThan(0)
  return p
}

async function login(page: import('@playwright/test').Page, user: string, pass: string) {
  await page.goto(`${BASE}/login`)
  await page.locator('input[name="username"], input[type="text"]').first().fill(user)
  await page.locator('input[name="password"], input[type="password"]').first().fill(pass)
  await page.locator('button[type="submit"]').click()
  await page.waitForURL(/dashboard|shift-ops|home/i, { timeout: 45000 })
}

async function apiToken(request: import('@playwright/test').APIRequestContext, user: string, pass: string) {
  const r = await request.post(`${API}/auth/login`, { data: { username: user, password: pass } })
  expect(r.ok()).toBeTruthy()
  return (await r.json()).access_token as string
}

async function fetchServerToday(request: import('@playwright/test').APIRequestContext, token: string) {
  const r = await request.get(`${API}/shift-ops/shifts`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  expect(r.ok()).toBeTruthy()
  return (await r.json()).server_today as string
}

async function latestShiftDate(request: import('@playwright/test').APIRequestContext, token: string) {
  const r = await request.get(`${API}/shift-ops/shifts`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  const items = (await r.json()).items as { id: number; shift_date: string }[]
  if (!items.length) return null
  const sorted = [...items].sort((a, b) => b.id - a.id)
  return String(sorted[0].shift_date).slice(0, 10)
}

async function openShiftViaApi(
  request: import('@playwright/test').APIRequestContext,
  token: string,
  shiftDate: string,
  extra: Record<string, unknown> = {},
) {
  const r = await request.post(`${API}/shift-ops/shifts`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { shift_date: shiftDate, shift_number: 1, ...extra },
  })
  return r
}

function shiftOpenDateInput(page: import('@playwright/test').Page) {
  return page.locator('div.bg-white.border.rounded-xl.p-4.space-y-3 input[type="date"]')
}

function clockSkewInitScript(behindOrAheadIso: string) {
  return (iso: string) => {
    const fixed = new Date(iso)
    const RealDate = Date
    // @ts-expect-error test shim
    Date = class extends RealDate {
      constructor(...args: unknown[]) {
        if (args.length === 0) super(fixed.getTime())
        else super(...(args as ConstructorParameters<typeof Date>))
      }
      static now() {
        return fixed.getTime()
      }
    }
    Date.now = () => fixed.getTime()
  }
}

test.describe('shift-ops server today', () => {
  test.setTimeout(90000)
  test.describe.configure({ mode: 'serial' })

  const bmUser = requireEnv('ST_BM_USER', BM_USER)
  const bmPass = requireEnv('ST_BM_PASS', BM_PASS)
  const adminUser = requireEnv('ST_ADMIN_USER', ADMIN_USER)
  const adminPass = requireEnv('ST_ADMIN_PASS', ADMIN_PASS)

  test.beforeEach(() => {
    cleanupPdShifts()
  })

  test('S1 correct browser clock opens server today', async ({ page, request }) => {
    await page.goto(BASE)
    const token = await apiToken(request, bmUser, bmPass)
    const serverToday = await fetchServerToday(request, token)
    await login(page, bmUser, bmPass)
    await page.goto(`${BASE}/shift-ops`)
    await page.getByTestId('shift-open-toggle').click()
    await expect(page.getByTestId('browser-server-date-mismatch')).toHaveCount(0)
    await page.getByTestId('shift-open-save').click()
    await page.waitForTimeout(2000)
    const stored = await latestShiftDate(request, token)
    expect(stored).toBe(serverToday)
    await saveShot(page, 'S1_open_ok.png')
  })

  test('S2 browser one day behind stores server date', async ({ browser, request }) => {
    const token = await apiToken(request, bmUser, bmPass)
    const serverToday = await fetchServerToday(request, token)
    const ctx = await browser.newContext({ timezoneId: 'Asia/Riyadh' })
    const page = await ctx.newPage()
    const behindIso = addDaysIso(serverToday, -1)
    await page.addInitScript(clockSkewInitScript(behindIso), `${behindIso}T12:00:00.000Z`)
    await login(page, bmUser, bmPass)
    await page.goto(`${BASE}/shift-ops`)
    await page.getByTestId('shift-open-toggle').click()
    await expect(page.getByTestId('browser-server-date-mismatch')).toBeVisible()
    const mismatch = page.getByTestId('browser-server-date-mismatch')
    await expect(mismatch).toContainText(behindIso)
    await expect(mismatch).toContainText(serverToday)
    await page.getByTestId('shift-open-save').click()
    await page.waitForTimeout(2000)
    const stored = await latestShiftDate(request, token)
    expect(stored).toBe(serverToday)
    await saveShot(page, 'S2_behind_en.png')
    await ctx.close()
  })

  test('S3 browser one day ahead stores server date', async ({ browser, request }) => {
    const token = await apiToken(request, bmUser, bmPass)
    const serverToday = await fetchServerToday(request, token)
    const ctx = await browser.newContext({ timezoneId: 'Asia/Riyadh' })
    const page = await ctx.newPage()
    const aheadIso = addDaysIso(serverToday, 1)
    await page.addInitScript(clockSkewInitScript(aheadIso), `${aheadIso}T12:00:00.000Z`)
    await login(page, bmUser, bmPass)
    await page.goto(`${BASE}/shift-ops`)
    await page.getByTestId('shift-open-toggle').click()
    await expect(page.getByTestId('browser-server-date-mismatch')).toBeVisible()
    const mismatch = page.getByTestId('browser-server-date-mismatch')
    await expect(mismatch).toContainText(aheadIso)
    await expect(mismatch).toContainText(serverToday)
    await page.getByTestId('shift-open-save').click()
    await page.waitForTimeout(2000)
    const stored = await latestShiftDate(request, token)
    expect(stored).toBe(serverToday)
    await saveShot(page, 'S3_ahead.png')
    await ctx.close()
  })

  test('S4 missing server_today blocks POST', async ({ page, request }) => {
    let openPosts = 0
    await page.route('**/api/v1/shift-ops/shifts**', async (route) => {
      if (route.request().method() === 'POST') {
        openPosts += 1
        return route.continue()
      }
      if (route.request().method() === 'GET') {
        const resp = await route.fetch()
        const json = await resp.json()
        delete json.server_today
        return route.fulfill({ response: resp, json })
      }
      return route.continue()
    })
    await login(page, bmUser, bmPass)
    await page.goto(`${BASE}/shift-ops`)
    await page.getByTestId('shift-open-toggle').click()
    await expect(page.getByText(/server business date|تاريخ العمل من الخادم/i)).toBeVisible()
    await expect(page.getByTestId('shift-open-save')).toBeDisabled()
    await page.getByTestId('shift-open-save').click({ force: true })
    await page.waitForTimeout(500)
    await saveShot(page, 'S4_missing_server_today_en.png')
    expect(openPosts).toBe(0)
  })

  test('S5 midnight refresh blocks stale open', async ({ page, request }) => {
    const token = await apiToken(request, bmUser, bmPass)
    const d1 = await fetchServerToday(request, token)
    expect(d1).toBeTruthy()
    const d0 = addDaysIso(d1, -1)
    let staleNextGet = false
    let forcedServerToday: string = d0
    await page.route('**/api/v1/shift-ops/shifts**', async (route) => {
      if (route.request().method() !== 'GET') return route.continue()
      const resp = await route.fetch()
      const json = await resp.json()
      if (staleNextGet) {
        forcedServerToday = d1
        staleNextGet = false
      }
      json.server_today = forcedServerToday
      return route.fulfill({ response: resp, json })
    })
    await login(page, bmUser, bmPass)
    await page.goto(`${BASE}/shift-ops`)
    await page.getByTestId('shift-open-toggle').click()
    let openPosts = 0
    page.on('request', (req) => {
      if (req.method() === 'POST' && req.url().includes('/shift-ops/shifts')) openPosts += 1
    })
    staleNextGet = true
    await page.getByTestId('shift-open-save').click()
    await page.waitForTimeout(1500)
    expect(openPosts).toBe(0)
    await expect(page.getByText(/server business date changed|تغيّر تاريخ/i)).toBeVisible()
    await saveShot(page, 'S5_midnight_refresh.png')
    await page.getByTestId('shift-open-save').click()
    await page.waitForTimeout(2000)
    expect(openPosts).toBe(1)
    const stored = await latestShiftDate(request, token)
    expect(stored).toBe(d1)
  })

  test('S6b admin date input bounds backdate audit and reject', async ({ browser, page, request }) => {
    const adminToken = await apiToken(request, adminUser, adminPass)
    const serverToday = await fetchServerToday(request, adminToken)
    const minExpected = addDaysIso(serverToday, -7)
    const threeBack = addDaysIso(serverToday, -3)

    for (const delta of [-1, 1]) {
      const skewIso = addDaysIso(serverToday, delta)
      const ctx = await browser.newContext({ timezoneId: 'Asia/Riyadh' })
      const p = await ctx.newPage()
      await p.addInitScript(() => localStorage.setItem('raed.lang', 'en'))
      await p.addInitScript(clockSkewInitScript(skewIso), `${skewIso}T12:00:00.000Z`)
      await login(p, adminUser, adminPass)
      await p.goto(`${BASE}/shift-ops`)
      await p.getByTestId('shift-open-toggle').click()
      const dateInput = shiftOpenDateInput(p)
      await expect(dateInput).toHaveAttribute('max', serverToday)
      await expect(dateInput).toHaveAttribute('min', minExpected)
      await expect(dateInput).toHaveValue(serverToday)
      await saveShot(p, `S6b_bounds_skew_${delta}.png`)
      await ctx.close()
    }

    await page.addInitScript(() => localStorage.setItem('raed.lang', 'en'))
    await login(page, adminUser, adminPass)
    await page.goto(`${BASE}/shift-ops`)
    await page.getByTestId('shift-open-toggle').click()
    const dateInput = shiftOpenDateInput(page)
    await dateInput.fill(threeBack)
    await expect(page.getByText(/backdate|reason/i)).toBeVisible()
    await expect(page.getByTestId('shift-open-save')).toBeDisabled()
    const reasonBox = page.getByPlaceholder(/Backdate reason \(min 5 chars\)/i)
    await reasonBox.fill('ab')
    await expect(page.getByTestId('shift-open-save')).toBeDisabled()
    await reasonBox.fill('Late entry approved for test')
    await page.getByTestId('shift-open-save').click()
    await page.waitForTimeout(2500)
    const stored = await latestShiftDate(request, adminToken)
    expect(stored).toBe(threeBack)
    const shifts = await request.get(`${API}/shift-ops/shifts`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    })
    const items = (await shifts.json()).items as { id: number; shift_date: string }[]
    const shiftId = items.sort((a, b) => b.id - a.id)[0].id
    const audit = await request.get(
      `${API}/audit/logs?action=shift_open_backdated&entity_id=${shiftId}&module=shift_ops`,
      { headers: { Authorization: `Bearer ${adminToken}` } },
    )
    expect(audit.ok()).toBeTruthy()
    const logs = (await audit.json()).items as { action: string; new_values: Record<string, unknown> }[]
    expect(logs.length).toBeGreaterThan(0)
    const age = logs[0].new_values?.age_days
    expect(age === 3 || age === '3' || Number(age) === 3).toBeTruthy()
    await saveShot(page, 'S6b_backdate_ok.png')

    cleanupPdShifts()
    const eightBack = addDaysIso(serverToday, -8)
    const fakeToday = addDaysIso(serverToday, -1)
    await page.route('**/api/v1/shift-ops/shifts**', async (route) => {
      if (route.request().method() === 'GET') {
        const resp = await route.fetch()
        const json = await resp.json()
        json.server_today = fakeToday
        return route.fulfill({ response: resp, json })
      }
      return route.continue()
    })
    await page.goto(`${BASE}/shift-ops`)
    await page.getByTestId('shift-open-toggle').click()
    const dateInput2 = shiftOpenDateInput(page)
    await dateInput2.fill(eightBack)
    await page.getByPlaceholder(/Backdate reason \(min 5 chars\)/i).fill('Too far back attempt')
    await page.getByTestId('shift-open-save').click()
    await page.waitForTimeout(2000)
    await expect(page.getByText(`Server business date (Riyadh): ${serverToday}`)).toBeVisible()
    await expect(page.getByText(/more than 7 days before|too far in the past/i)).toBeVisible()
    await saveShot(page, 'S6b_reject_8d.png')
    expect(await latestShiftDate(request, adminToken)).toBeNull()
    await page.unroute('**/api/v1/shift-ops/shifts**')

    cleanupPdShifts()
    const d0 = serverToday
    const d1 = addDaysIso(d0, 1)
    let forced = d0
    await page.route('**/api/v1/shift-ops/shifts**', async (route) => {
      if (route.request().method() !== 'GET') return route.continue()
      const resp = await route.fetch()
      const json = await resp.json()
      json.server_today = forced
      return route.fulfill({ response: resp, json })
    })
    await page.goto(`${BASE}/shift-ops`)
    await page.getByTestId('shift-open-toggle').click()
    await dateInput.fill(addDaysIso(d0, -7))
    forced = d1
    await page.getByRole('checkbox', { name: /Incomplete shifts only/i }).click()
    await page.waitForTimeout(800)
    await expect(dateInput).toHaveValue(d1)
    await saveShot(page, 'S6b_date_reset_on_server_change.png')
  })

  test('S7 ShiftTodayRedirect uses server today', async ({ browser, request }) => {
    const token = await apiToken(request, bmUser, bmPass)
    const serverToday = await fetchServerToday(request, token)
    const openRes = await openShiftViaApi(request, token, serverToday)
    expect(openRes.ok()).toBeTruthy()
    const shiftId = (await openRes.json()).id as number
    for (const delta of [-1, 1]) {
      const skewIso = addDaysIso(serverToday, delta)
      const ctx = await browser.newContext({ timezoneId: 'Asia/Riyadh' })
      const page = await ctx.newPage()
      await page.addInitScript(clockSkewInitScript(skewIso), `${skewIso}T12:00:00.000Z`)
      await login(page, bmUser, bmPass)
      await page.goto(`${BASE}/shift-ops/today/count`)
      await page.waitForURL(new RegExp(`/shift-ops/${shiftId}/count`), { timeout: 45000 })
      await saveShot(page, `S7_redirect_skew_${delta}.png`)
      await ctx.close()
    }
    cleanupPdShifts()
    const ctx2 = await browser.newContext()
    const page2 = await ctx2.newPage()
    await login(page2, bmUser, bmPass)
    await page2.goto(`${BASE}/shift-ops/today/count`)
    await page2.waitForURL(/shift-ops\?open=1.*reason=no_shift_today|reason=no_shift_today.*open=1/, {
      timeout: 45000,
    })
    await saveShot(page2, 'S7_no_shift_today.png')
    await ctx2.close()
  })

  test('S8 EN and AR screenshots for mismatch and missing server_today', async ({ browser, request }) => {
    const token = await apiToken(request, bmUser, bmPass)
    const serverToday = await fetchServerToday(request, token)
    const behindIso = addDaysIso(serverToday, -1)
    const ctxEn = await browser.newContext({ timezoneId: 'Asia/Riyadh', locale: 'en-US' })
    const pageEn = await ctxEn.newPage()
    await pageEn.addInitScript(() => {
      localStorage.setItem('raed.lang', 'en')
    })
    await pageEn.addInitScript(clockSkewInitScript(behindIso), `${behindIso}T12:00:00.000Z`)
    await login(pageEn, bmUser, bmPass)
    await pageEn.goto(`${BASE}/shift-ops`)
    await pageEn.getByTestId('shift-open-toggle').click()
    await expect(pageEn.getByTestId('browser-server-date-mismatch')).toBeVisible()
    await expect(pageEn.getByText(/server business date|server date/i)).toBeVisible()
    await saveShot(pageEn, 'S8_S2_mismatch_en.png')
    await ctxEn.close()

    const ctxAr = await browser.newContext({ timezoneId: 'Asia/Riyadh', locale: 'ar-SA' })
    const pageAr = await ctxAr.newPage()
    await pageAr.addInitScript(() => {
      localStorage.setItem('raed.lang', 'ar')
    })
    await pageAr.route('**/api/v1/shift-ops/shifts**', async (route) => {
      if (route.request().method() === 'GET') {
        const resp = await route.fetch()
        const json = await resp.json()
        delete json.server_today
        return route.fulfill({ response: resp, json })
      }
      return route.continue()
    })
    await login(pageAr, bmUser, bmPass)
    await pageAr.goto(`${BASE}/shift-ops`)
    await pageAr.getByTestId('shift-open-toggle').click()
    await expect(pageAr.getByText('تعذّر تحميل تاريخ العمل من الخادم')).toBeVisible()
    await expect(pageAr.locator('html')).toHaveAttribute('dir', 'rtl')
    await saveShot(pageAr, 'S8_S4_missing_ar.png')
    await ctxAr.close()
  })
})
