import fs from 'node:fs/promises';
import path from 'node:path';
import puppeteer from 'puppeteer';
import {startFlow, generateReport} from 'lighthouse/core/index.js';

const BASE_URL = process.env.LIGHTHOUSE_BASE_URL || 'http://127.0.0.1:8010';
const REPORT_DIR = path.resolve(process.cwd(), 'lighthouse-reports');

async function ensureDir(dir) {
  await fs.mkdir(dir, {recursive: true});
}

async function clearStorage(page) {
  await page.evaluate(() => {
    localStorage.clear();
    sessionStorage.clear();
  });
  const cookies = await page.cookies();
  if (cookies.length) {
    await page.deleteCookie(...cookies);
  }
}

async function login(page, username, password = 'Raed@2025') {
  await page.goto(`${BASE_URL}/login`, {waitUntil: 'networkidle2'});
  await clearStorage(page);
  await page.goto(`${BASE_URL}/login`, {waitUntil: 'networkidle2'});
  await page.type('input[type="text"]', username, {delay: 10});
  await page.type('input[type="password"], input[type="text"][autocomplete="current-password"]', password, {delay: 10});
  await Promise.all([
    page.waitForResponse((resp) => resp.url().includes('/api/v1/auth/login') && resp.request().method() === 'POST'),
    page.click('button[type="submit"]'),
  ]);
  await page.waitForFunction(() => location.pathname === '/dashboard' || location.pathname === '/supply-chain/control');
  await page.waitForNetworkIdle();
}

async function runFlow(browser, name, stepsFn) {
  const page = await browser.newPage();
  await page.setViewport({width: 1440, height: 1000, deviceScaleFactor: 1});
  const flow = await startFlow(page, {
    name,
    config: {
      extends: 'lighthouse:default',
      settings: {
        onlyCategories: ['performance', 'accessibility', 'best-practices', 'seo'],
        throttlingMethod: 'provided',
        screenEmulation: {
          mobile: false,
          width: 1440,
          height: 1000,
          deviceScaleFactor: 1,
          disabled: false,
        },
        formFactor: 'desktop',
      },
    },
  });
  try {
    await stepsFn(page, flow);
    const result = await flow.createFlowResult();
    const html = await flow.generateReport();
    const json = generateReport(result, 'json');
    await fs.writeFile(path.join(REPORT_DIR, `${name}.html`), html, 'utf8');
    await fs.writeFile(path.join(REPORT_DIR, `${name}.json`), json, 'utf8');
    return summarizeFlow(result);
  } finally {
    await page.close();
  }
}

function summarizeFlow(flowResult) {
  return {
    name: flowResult.name,
    steps: flowResult.steps.map((step) => ({
      name: step.name,
      categories: Object.fromEntries(
        Object.entries(step.lhr.categories || {}).map(([key, value]) => [
          key,
          {
            score: value.score,
            title: value.title,
          },
        ]),
      ),
      finalUrl: step.lhr.finalDisplayedUrl || step.lhr.finalUrl,
    })),
  };
}

async function snapshotRoute(page, flow, stepName, route) {
  await page.goto(`${BASE_URL}${route}`, {waitUntil: 'networkidle2'});
  await flow.snapshot({stepName});
}

async function prepareDailyOrder(page) {
  await page.goto(`${BASE_URL}/orders/daily`, {waitUntil: 'networkidle2'});
  await page.select('select', '11');
  await page.waitForFunction(() => document.querySelectorAll('tbody tr').length > 1);
}

async function prepareBranchRequests(page) {
  await page.goto(`${BASE_URL}/supply-chain/branch-requests`, {waitUntil: 'networkidle2'});
  await page.waitForFunction(() => {
    const selects = document.querySelectorAll('select');
    return selects.length >= 2 && selects[0].options.length > 1;
  });
  const selects = await page.$$('select');
  if (selects[0]) {
    await selects[0].select('6').catch(() => {});
  }
  await page.waitForNetworkIdle();
}

async function main() {
  await ensureDir(REPORT_DIR);
  const browser = await puppeteer.launch({
    headless: true,
    defaultViewport: null,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });

  try {
    const summaries = [];

    summaries.push(await runFlow(browser, 'login-page', async (page, flow) => {
      await flow.navigate(`${BASE_URL}/login`, {stepName: 'Login page'});
    }));

    summaries.push(await runFlow(browser, 'super-admin-core', async (page, flow) => {
      await flow.navigate(`${BASE_URL}/login`, {stepName: 'Login page'});
      await login(page, 'super.admin');
      await flow.snapshot({stepName: 'Control center'});
      await prepareDailyOrder(page);
      await flow.snapshot({stepName: 'Daily order'});
      await snapshotRoute(page, flow, 'Admin kitchens', '/admin/kitchens');
    }));

    summaries.push(await runFlow(browser, 'branch-user-core', async (page, flow) => {
      await flow.navigate(`${BASE_URL}/login`, {stepName: 'Login page'});
      await login(page, 'branch_onda_13_al_malqa');
      await prepareBranchRequests(page);
      await flow.snapshot({stepName: 'Branch requests'});
      await snapshotRoute(page, flow, 'Branch employees', '/branch-employees');
    }));

    summaries.push(await runFlow(browser, 'warehouse-delivery-core', async (page, flow) => {
      await flow.navigate(`${BASE_URL}/login`, {stepName: 'Login page'});
      await login(page, 'warehouse_dammam_user');
      await snapshotRoute(page, flow, 'Warehouse', '/supply-chain/warehouse');
      await clearStorage(page);
      await login(page, 'delivery_dammam');
      await snapshotRoute(page, flow, 'Delivery', '/supply-chain/delivery');
    }));

    await fs.writeFile(
      path.join(REPORT_DIR, 'summary.json'),
      JSON.stringify({baseUrl: BASE_URL, generatedAt: new Date().toISOString(), flows: summaries}, null, 2),
      'utf8',
    );

    console.log(`Lighthouse reports saved to ${REPORT_DIR}`);
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
