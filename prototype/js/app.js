(() => {
  'use strict';
  const form = document.querySelector('#sales-form');
  if (!form) return;
  const $ = (id) => document.getElementById(id);
  const els = {
    total: $('total-sale'), invoices: $('invoice-count'), average: $('average-bill'), atm: $('atm-sales'), cash: $('cash-sales'), apps: $('app-sales'),
    refunds: $('refunds'), exchange: $('exchange'), expiry: $('expiry'), expense: $('cash-expense'), deposited: $('cash-deposited'),
    expenseType: $('expense-type'), expenseDetails: $('expense-details'), notes: $('shift-notes'), cashReadonly: $('cash-sales-readonly'),
    paymentTotal: $('payment-total'), paymentDifference: $('payment-difference'), paymentStatus: $('payment-status'), paymentValidation: $('payment-validation'),
    cashSummaryDeposited: $('cash-summary-deposited'), cashDifference: $('cash-difference'), cashStatus: $('cash-status'), cashValidation: $('cash-validation'),
    notesCounter: $('notes-counter'), save: $('save-draft'), submit: $('submit-sales'), message: $('form-message'), lastSaved: $('last-saved'), shiftStatus: $('shift-status')
  };
  const numeric = [els.total, els.invoices, els.atm, els.cash, els.apps, els.refunds, els.exchange, els.expiry, els.expense, els.deposited];
  const financialInputs = [...document.querySelectorAll('input[data-financial]')];
  const money = new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const value = (el) => Math.max(0, Number(String(el.value).replaceAll(',', '')) || 0);
  const sar = (number) => `${money.format(number)} ر.س`;
  const nearlyEqual = (a, b) => Math.abs(a - b) < 0.005;
  const delay = (milliseconds) => new Promise((resolve) => window.setTimeout(resolve, milliseconds));
  const setValidation = (container, status, state) => {
    const supportedStates = ['success', 'warning', 'error'];
    const activeState = supportedStates.includes(state) ? state : 'error';
    supportedStates.forEach((name) => container.classList.toggle(name, name === activeState));
    status.textContent = activeState === 'success' ? '✓ متطابقة' : activeState === 'warning' ? 'يوجد فرق' : 'بيانات غير صالحة';
  };
  function recalculate() {
    const total = value(els.total);
    const billCount = value(els.invoices);
    const cashSales = value(els.cash);
    const payments = value(els.atm) + cashSales + value(els.apps);
    const paymentDiff = payments - total;
    const expense = value(els.expense);
    const deposited = value(els.deposited);
    const cashDiff = cashSales - expense - deposited;
    const averageBill = billCount > 0 ? total / billCount : 0;
    els.average.value = money.format(Number.isFinite(averageBill) ? averageBill : 0);
    els.cashReadonly.value = money.format(cashSales);
    els.paymentTotal.textContent = sar(payments);
    els.paymentDifference.textContent = sar(paymentDiff);
    els.cashSummaryDeposited.textContent = sar(deposited);
    els.cashDifference.textContent = sar(cashDiff);
    const conditional = expense > 0;
    els.expenseType.required = conditional;
    els.expenseDetails.required = conditional;
    document.querySelectorAll('.conditional-required').forEach((mark) => { mark.hidden = !conditional; });
    const paymentMissing = [els.total, els.invoices, els.atm, els.cash, els.apps].some((input) => input.value.trim() === '' || value(input) < Number(input.min || 0));
    const expenseInvalid = expense > cashSales;
    const cashMissing = els.deposited.value.trim() === '' || value(els.deposited) < 0 || (conditional && (!els.expenseType.value || !els.expenseDetails.value.trim()));
    setValidation(els.paymentValidation, els.paymentStatus, paymentMissing ? 'error' : nearlyEqual(paymentDiff, 0) ? 'success' : 'warning');
    setValidation(els.cashValidation, els.cashStatus, expenseInvalid || cashMissing ? 'error' : nearlyEqual(cashDiff, 0) ? 'success' : 'warning');
    return { paymentDiff, cashDiff, expenseInvalid };
  }
  function showMessage(text, error = false) {
    els.message.textContent = text;
    els.message.style.color = error ? '#c43c3c' : '#198754';
  }
  function markAndValidate() {
    [...form.elements].forEach((el) => { if (el.matches('input,select,textarea')) el.classList.add('touched'); });
    const { paymentDiff, cashDiff, expenseInvalid } = recalculate();
    if (!form.checkValidity()) { form.reportValidity(); showMessage('يرجى استكمال الحقول الإلزامية.', true); return false; }
    if (expenseInvalid) { els.expense.focus(); showMessage('لا يمكن الإرسال: المصروف أكبر من مبيعات الكاش.', true); return false; }
    if (!nearlyEqual(paymentDiff, 0)) { els.atm.focus(); showMessage('لا يمكن الإرسال: يوجد فرق في طرق الدفع.', true); return false; }
    if (!nearlyEqual(cashDiff, 0)) { els.deposited.focus(); showMessage('لا يمكن الإرسال: يوجد فرق في تسوية الكاش.', true); return false; }
    return true;
  }
  numeric.forEach((input) => {
    input.addEventListener('input', () => { if (String(input.value).includes('-')) input.value = '0'; showMessage(''); recalculate(); });
    input.addEventListener('keydown', (event) => { if (['-', '+', 'e', 'E'].includes(event.key)) event.preventDefault(); });
    input.addEventListener('change', recalculate);
    input.addEventListener('blur', () => { input.classList.add('touched'); recalculate(); });
  });
  financialInputs.forEach((input) => {
    input.addEventListener('focus', () => { input.value = input.value.replaceAll(',', ''); });
    input.addEventListener('input', () => {
      const raw = input.value.replaceAll(',', '');
      const parts = raw.replace(/[^\d.]/g, '').split('.');
      input.value = parts.length > 1 ? `${parts.shift()}.${parts.join('')}` : parts[0];
    });
    input.addEventListener('blur', () => { input.value = money.format(value(input)); recalculate(); });
  });
  [els.expenseType, els.expenseDetails].forEach((input) => input.addEventListener('input', recalculate));
  els.notes.addEventListener('input', () => {
    if (els.notes.value.length > 300) els.notes.value = els.notes.value.slice(0, 300);
    els.notesCounter.textContent = `${els.notes.value.length} / 300`;
  });
  els.save.addEventListener('click', async () => {
    recalculate();
    const originalText = els.save.textContent;
    els.save.disabled = true;
    els.save.textContent = 'جارٍ الحفظ...';
    await delay(450);
    const time = new Intl.DateTimeFormat('ar-SA', { hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date());
    els.lastSaved.textContent = `آخر حفظ: ${time}`;
    els.shiftStatus.className = 'badge badge-saved';
    els.shiftStatus.innerHTML = '<span class="dot"></span>محفوظة';
    els.save.textContent = originalText;
    els.save.disabled = false;
    showMessage('تم حفظ المسودة محليًا بنجاح.');
  });
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!markAndValidate()) return;
    if (!window.confirm('هل تريد إرسال مبيعات الشفت وإغلاقها؟ لن تتمكن من التعديل بعد الإرسال.')) return;
    els.submit.disabled = true;
    els.submit.textContent = 'جارٍ الإرسال...';
    await delay(600);
    [...form.elements].forEach((el) => { el.disabled = true; });
    form.classList.add('form-locked');
    els.shiftStatus.className = 'badge badge-submitted';
    els.shiftStatus.removeAttribute('style');
    els.shiftStatus.innerHTML = '<span class="dot"></span>مغلق';
    showMessage('تم إرسال وإغلاق مبيعات الشفت بنجاح.');
  });
  recalculate();
})();

(() => {
  'use strict';
  const form = document.querySelector('#inventory-form');
  if (!form) return;

  const $ = (id) => document.getElementById(id);
  // Future production source:
  // Item Master filtered by current brand and Shift Count Item = Yes.
  const brandInventoryConfig = Object.freeze({
    ONDA: Object.freeze({
      code: 'ONDA',
      name: 'ONDA',
      branchName: 'أوندا 9 - رأس تنورة',
      // APPROVED ONDA PROTOTYPE COUNT LIST
      // SOURCE: Coffee_Consumption_Tracker_1.xlsx
      // SCOPE: Coffee Beans, Cups, Desserts only
      inventoryItems: [
      { category: 'Coffee Beans', name: 'TRH 996g', unit: 'كيس', opening: 20 },
      { category: 'Coffee Beans', name: 'Costa Rica', unit: 'كيس', opening: 14 },
      { category: 'Coffee Beans', name: 'Colombian 990g', unit: 'كيس', opening: 18 },
      { category: 'Coffee Beans', name: 'Guatemala 990g', unit: 'كيس', opening: 12 },
      { category: 'Cups', name: '12 oz - paper', unit: 'قطعة', opening: 240 },
      { category: 'Cups', name: '12 oz - plastic', unit: 'قطعة', opening: 180 },
      { category: 'Cups', name: '8 oz', unit: 'قطعة', opening: 210 },
      { category: 'Cups', name: '8 oz - lids', unit: 'قطعة', opening: 220 },
      { category: 'Cups', name: '6 oz', unit: 'قطعة', opening: 160 },
      { category: 'Cups', name: '6 oz - lids', unit: 'قطعة', opening: 175 },
      { category: 'Cups', name: '4 oz', unit: 'قطعة', opening: 120 },
      { category: 'Cups', name: '4 oz - lids', unit: 'قطعة', opening: 130 },
      { category: 'Desserts', name: 'Lemon cake', unit: 'قطعة', opening: 18 },
      { category: 'Desserts', name: 'Cookies', unit: 'قطعة', opening: 30 },
      { category: 'Desserts', name: 'Brownies', unit: 'قطعة', opening: 22 },
      { category: 'Desserts', name: 'Brownies - zaatar', unit: 'قطعة', opening: 16 },
      { category: 'Desserts', name: 'Cheese strawberry', unit: 'قطعة', opening: 14 },
      { category: 'Desserts', name: 'Cheese pecan', unit: 'قطعة', opening: 12 },
      { category: 'Desserts', name: 'Tiramisu', unit: 'قطعة', opening: 15 },
      { category: 'Desserts', name: 'Eclair', unit: 'قطعة', opening: 20 },
      { category: 'Desserts', name: 'Cheese croissant', unit: 'قطعة', opening: 24 },
      { category: 'Desserts', name: 'Zaatar croissant', unit: 'قطعة', opening: 21 },
        { category: 'Desserts', name: 'Turkey croissant', unit: 'قطعة', opening: 19 }
      ]
    }),
    RONALDOS: Object.freeze({
      code: 'RONALDOS',
      name: 'RONALDOS',
      branchName: 'رونالدوز - فرع تجريبي',
      inventoryItems: [
        { name: 'العجين', unit: 'كجم', opening: 32 },
        { name: 'الدجاج', unit: 'كجم', opening: 18 },
        { name: 'شرمب', unit: 'كجم', opening: 9 }
      ]
    }),
    SHAWARMA: Object.freeze({
      code: 'SHAWARMA',
      name: 'SHAWARMA',
      branchName: 'شاورما - فرع تجريبي',
      inventoryItems: [
        { name: 'سيخ دجاج', unit: 'سيخ', opening: 6 },
        { name: 'سيخ لحم', unit: 'سيخ', opening: 4 }
      ]
    })
  });
  const requestedBrand = new URLSearchParams(window.location.search).get('brand')?.toUpperCase();
  const currentBrand = brandInventoryConfig[requestedBrand] || brandInventoryConfig.ONDA;

  const itemFields = ['opening', 'received', 'returned', 'damaged', 'closing'];
  const fieldLabels = {
    opening: 'رصيد افتتاح', received: 'وارد', returned: 'مرتجع', damaged: 'تالف', closing: 'رصيد إقفال'
  };
  const renderBrandInventory = (brand) => {
    const body = $('inventory-items-body');
    body.dataset.brand = brand.code;
    document.documentElement.dataset.brand = brand.code;
    document.title = `إغلاق جرد الشفت | ${brand.name}`;
    document.querySelector('.brand-logo').alt = brand.name;
    document.querySelector('.shift-meta dd').textContent = brand.branchName;
    body.innerHTML = brand.inventoryItems.map((item) => {
      const fields = itemFields.map((field) => {
        const initialValue = field === 'opening' ? item.opening : '';
        const stateAttributes = field === 'opening'
          ? 'readonly aria-readonly="true" tabindex="-1"'
          : 'required aria-required="true"';
        return `<td><input aria-label="${fieldLabels[field]} ${item.name}" data-field="${field}" value="${initialValue}" inputmode="decimal" step="0.01" min="0" ${stateAttributes}></td>`;
      }).join('');
      const itemDirection = /^[\u0600-\u06ff]/.test(item.name) ? 'rtl' : 'ltr';
      return `<tr data-inventory-row data-brand="${brand.code}"><td><span class="row-status" aria-label="حالة ${item.name}"></span></td><th scope="row" class="inventory-item-name" dir="${itemDirection}">${item.name}</th><td>${item.unit}</td>${fields}<td><output data-consumption aria-label="الاستهلاك المحسوب ${item.name}" aria-readonly="true">—</output></td><td><input aria-label="ملاحظات ${item.name}" data-note placeholder="اختياري"></td></tr>`;
    }).join('');
  };
  renderBrandInventory(currentBrand);
  const rows = [...form.querySelectorAll('[data-inventory-row]')];
  const notes = $('inventory-notes');
  const notesCounter = $('inventory-notes-counter');
  const saveButton = $('inventory-save-draft');
  const submitButton = $('inventory-submit');
  const statusBadge = $('inventory-shift-status');
  const lastSaved = $('inventory-last-saved');
  const formMessage = $('inventory-form-message');
  const validation = $('inventory-validation');
  const validationStatus = $('inventory-validation-status');
  const numberFormat = new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const delay = (milliseconds) => new Promise((resolve) => window.setTimeout(resolve, milliseconds));
  const numericPattern = /^\d+(?:\.\d{0,2})?$/;

  const setMessage = (text, error = false) => {
    formMessage.textContent = text;
    formMessage.style.color = error ? '#c43c3c' : '#198754';
  };

  const setValidationState = (state, text) => {
    ['success', 'warning', 'error'].forEach((name) => validation.classList.toggle(name, name === state));
    validationStatus.textContent = text;
  };

  function inspectRow(row) {
    const openingRaw = row.querySelector('[data-field="opening"]').value.trim();
    const editableFields = ['received', 'returned', 'damaged', 'closing'];
    const editableValues = editableFields.map((field) => row.querySelector(`[data-field="${field}"]`).value.trim());
    const incomplete = editableValues.some((raw) => raw === '');
    const invalidOpening = !numericPattern.test(openingRaw) || Number(openingRaw) < 0;
    const invalidEditable = editableValues.some((raw) => raw !== '' && (!numericPattern.test(raw) || Number(raw) < 0));
    const invalid = invalidOpening || invalidEditable;
    let consumption = null;
    if (!incomplete && !invalid) {
      const [received, returned, damaged, closing] = editableValues.map(Number);
      const opening = Number(openingRaw);
      consumption = opening + received - returned - damaged - closing;
      if (!Number.isFinite(consumption) || consumption < 0) consumption = null;
    }
    const state = invalid || (!incomplete && consumption === null) ? 'invalid' : incomplete ? 'incomplete' : 'complete';
    row.dataset.state = state;
    const marker = row.querySelector('.row-status');
    marker.setAttribute('aria-label', state === 'complete' ? 'مكتمل' : state === 'incomplete' ? 'غير مكتمل' : 'قيمة غير صحيحة');
    row.querySelector('[data-consumption]').textContent = consumption === null ? '—' : numberFormat.format(consumption);
    return { state, consumption: consumption ?? 0 };
  }

  function recalculateInventory() {
    const results = rows.map(inspectRow);
    const complete = results.filter((result) => result.state === 'complete').length;
    const invalid = results.filter((result) => result.state === 'invalid').length;
    const incomplete = rows.length - complete;
    $('inventory-total-items').textContent = String(rows.length);
    $('inventory-complete-items').textContent = String(complete);
    $('inventory-incomplete-items').textContent = String(incomplete);
    $('inventory-validation-complete').textContent = String(complete);
    $('inventory-validation-incomplete').textContent = String(incomplete);
    if (invalid > 0) setValidationState('error', 'توجد قيم غير صحيحة');
    else if (incomplete > 0) setValidationState('warning', 'يوجد أصناف غير مكتملة');
    else setValidationState('success', 'جاهز للإرسال');
    return { complete, incomplete, invalid };
  }

  rows.forEach((row) => {
    row.querySelectorAll('[data-field]').forEach((input) => {
      input.inputMode = 'decimal';
      input.autocomplete = 'off';
      if (input.readOnly) return;
      input.addEventListener('keydown', (event) => { if (['+', '-', 'e', 'E'].includes(event.key)) event.preventDefault(); });
      input.addEventListener('focus', () => { if (input.value !== '') input.select(); });
      input.addEventListener('input', () => { setMessage(''); recalculateInventory(); });
    });
  });

  notes.addEventListener('input', () => {
    if (notes.value.length > 300) notes.value = notes.value.slice(0, 300);
    notesCounter.textContent = `${notes.value.length} / 300`;
  });

  form.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && event.target.tagName !== 'TEXTAREA' && event.target.tagName !== 'BUTTON') event.preventDefault();
  });

  saveButton.addEventListener('click', async () => {
    recalculateInventory();
    saveButton.disabled = true;
    saveButton.textContent = 'جارٍ الحفظ...';
    await delay(450);
    const time = new Intl.DateTimeFormat('ar-SA', { hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date());
    lastSaved.textContent = `آخر حفظ: ${time}`;
    statusBadge.className = 'badge badge-saved';
    statusBadge.innerHTML = '<span class="dot"></span>محفوظة';
    saveButton.textContent = 'حفظ كمسودة';
    saveButton.disabled = false;
    setMessage('تم حفظ مسودة الجرد محليًا بنجاح.');
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const result = recalculateInventory();
    if (result.invalid > 0) { setMessage('لا يمكن الإرسال: توجد قيم غير صحيحة.', true); form.querySelector('tr[data-state="invalid"] input').focus(); return; }
    if (result.incomplete > 0) { setMessage('لا يمكن الإرسال: يوجد أصناف غير مكتملة.', true); form.querySelector('tr[data-state="incomplete"] input[value=""]').focus(); return; }
    if (!window.confirm('بعد إرسال الجرد لن يتمكن مستخدم الفرع من تعديل بيانات هذا الشفت. هل تريد المتابعة؟')) return;
    submitButton.disabled = true;
    saveButton.disabled = true;
    submitButton.textContent = 'جارٍ الإرسال...';
    await delay(600);
    form.querySelectorAll('input, textarea, button').forEach((control) => { control.disabled = true; });
    form.classList.add('form-locked');
    statusBadge.className = 'badge badge-submitted';
    statusBadge.innerHTML = '<span class="dot"></span>مغلق';
    setMessage('تم إرسال وإغلاق جرد الشفت بنجاح.');
  });

  recalculateInventory();
})();
