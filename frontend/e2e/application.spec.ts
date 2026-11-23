import { expect, test } from '@playwright/test';

test.beforeEach(async ({ request }) => {
  await expect.poll(async () => {
    try { return (await request.get('http://127.0.0.1:47541/health')).ok(); }
    catch { return false; }
  }, { timeout: 20_000 }).toBeTruthy();
});

test('loads, predicts, optimizes, simulates a scenario, and retrieves saved runs', async ({ page, request }) => {
  const health = await request.get('http://127.0.0.1:47541/health');
  expect(health.ok()).toBeTruthy();
  expect((await health.json()).database).toBe('READY');

  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Request forecast' })).toBeVisible();

  const wellSelector = page.getByRole('combobox').first();
  await wellSelector.selectOption('BW-DEMO-002');
  await expect(wellSelector).toHaveValue('BW-DEMO-002');

  await page.getByRole('button', { name: 'Request forecast' }).click();
  await expect(page.getByText(/Day \+1:/)).toBeVisible({ timeout: 15_000 });

  await page.getByRole('button', { name: 'Optimizer Review' }).click();
  await page.getByRole('button', { name: 'Run finite-grid optimization' }).click();
  await expect(page.getByText('GRID SEARCH COMPLETED')).toBeVisible({ timeout: 15_000 });

  await page.getByRole('button', { name: 'Scenario Lab' }).click();
  await expect(page.getByText('BACKEND SCENARIO RESULTS')).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/Estimated cycle oil \(\d+ days\)/)).toBeVisible();

  await page.getByRole('button', { name: 'Saved Runs' }).click();
  await expect(page.getByRole('heading', { name: 'Saved analysis runs' })).toBeVisible();
  await expect(page.getByRole('button', { name: /Production forecast/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /Joint optimization/ })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Inputs' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Outputs' })).toBeVisible();
  await expect(page.getByText(/objective_weights/)).toBeVisible();
});

test('shows saved-run retrieval errors without mock records', async ({ page }) => {
  await page.route('**/api/wells/BW-DEMO-001/analysis-runs**', (route) => route.fulfill({
    status: 503,
    contentType: 'application/json',
    body: JSON.stringify({ detail: 'Test database unavailable' }),
  }));
  await page.goto('/');
  await page.getByRole('button', { name: 'Saved Runs' }).click();
  await expect(page.getByRole('alert')).toContainText('Test database unavailable');
  await expect(page.getByText('Production forecast', { exact: true })).toHaveCount(0);
});

test('shows infeasible optimization without rendering a recommendation', async ({ page }) => {
  await page.route('**/optimize/joint', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      status: 'NO_FEASIBLE_CANDIDATE',
      algorithm: 'Finite grid search with weighted ranking and nondominated filtering',
      recommended_plan: null,
      expected_outcome: null,
      constraint_verification: { status: 'No candidate met the configured constraints' },
      pareto_frontier: [],
      rejected_alternatives_sample: [],
      decision_support_disclaimer: 'No recommendation is available; review model assumptions and constraints.',
    }),
  }));
  await page.goto('/');
  await page.getByRole('button', { name: 'Optimizer Review' }).click();
  await page.getByRole('button', { name: 'Run finite-grid optimization' }).click();
  await expect(page.getByRole('alert')).toContainText('No feasible candidate was found.');
  await expect(page.getByText('SELECTED CANDIDATE TRADE-OFF')).toHaveCount(0);
});

test('skips malformed saved-run records and displays valid entries', async ({ page }) => {
  await page.route('**/api/wells/BW-DEMO-001/analysis-runs**', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ runs: [
      { run_id: '', result: null },
      {
        run_id: 'valid-run', well_id: 'BW-DEMO-001', kind: 'production_forecast',
        source_mode: 'SIMULATION', created_at: '2026-11-22T10:00:00Z',
        result: { inputs: { well_id: 'BW-DEMO-001' }, forecast_horizons: { t_plus_1: { prediction_bpd: 1 } } },
      },
    ] }),
  }));
  await page.goto('/');
  await page.getByRole('button', { name: 'Saved Runs' }).click();
  await expect(page.getByText(/Skipped 1 invalid saved record/)).toBeVisible();
  await expect(page.getByRole('button', { name: /Production forecast/ })).toBeVisible();
  await expect(page.getByText(/valid-run/)).toBeVisible();
});

test('registers a well and imports measured CSV through the data workspace', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Field Data' }).click();
  await page.getByLabel('Well ID').fill('E2E-FIELD-001');
  await page.getByLabel('Display name').fill('Browser ingestion well');
  await page.getByRole('button', { name: 'Register well' }).click();
  await expect(page.getByText('Well E2E-FIELD-001 registered. It has no measured data until ingestion succeeds.')).toBeVisible();
  await page.getByLabel('Source ID').fill('playwright-csv');
  await page.getByLabel('CSV file', { exact: true }).setInputFiles({
    name: 'measurements.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from('well_id,measured_at,variable,value,unit\nE2E-FIELD-001,2026-11-22T10:00:00Z,oil_rate_bpd,80,bbl/day\nE2E-FIELD-001,2026-11-22T10:01:00Z,steam_injected_tons,2000,metric_ton\nE2E-FIELD-001,2026-11-22T10:02:00Z,soak_days,6,day\n'),
  });
  await page.getByRole('button', { name: 'Submit CSV' }).click();
  await expect(page.getByText(/3 accepted, 0 rejected/)).toBeVisible();
  await expect(page.getByText(/playwright-csv · INGESTION_RECORDED/)).toBeVisible();
  await page.getByRole('combobox').first().selectOption('E2E-FIELD-001');
  await page.getByRole('button', { name: /Build traceable snapshot/ }).click();
  await expect(page.getByLabel('Field twin snapshot')).toContainText('AVAILABLE_MEASUREMENTS');
  await expect(page.getByLabel('Field twin snapshot')).toContainText('measurement_references');
  const thermalParameters = Object.fromEntries(Object.entries({ native_temp_c:[47,'°C'], steam_temp_c:[295,'°C'], steam_quality:[0.78,'fraction'], latent_heat_kj_kg:[1420,'kJ/kg'], water_cp_kj_kg_k:[4.184,'kJ/kg/K'], formation_thickness_m:[18,'m'], porosity:[0.26,'fraction'], rock_density_kg_m3:[2450,'kg/m3'], rock_cp_kj_kg_k:[0.92,'kJ/kg/K'], conduction_decay_rate:[0.0135,'1/day'] }).map(([key,[value,unit]]) => [key,{value,unit,source:'test-well-config',classification:'OPERATOR_CONFIGURED',validation_status:'VALIDATED'}]));
  await page.getByLabel('Physical configuration JSON').fill(JSON.stringify(thermalParameters));
  await page.getByRole('button', { name: 'Save versioned configuration' }).click();
  await page.getByRole('button', { name: 'Execute physics against this snapshot' }).click();
  await expect(page.getByLabel('Physics execution run')).toContainText('PARTIAL');
  await expect(page.getByLabel('Physics execution run')).toContainText('peak_temperature_c');
  await expect(page.getByLabel('Physics execution run')).toContainText('NOT_VALIDATED_ON_HELD_OUT_FIELD_DATA');
  await expect(page.getByLabel('Physics model eligibility')).toContainText('production_reservoir');
  await expect(page.getByLabel('Physics model eligibility')).toContainText('BLOCKED');
  await expect(page.getByLabel('Physics comparison')).toContainText('NO_COMPATIBLE_MEASURED_OUTPUTS');
  await expect(page.getByRole('heading', { name: /Physics run history \(1\)/ })).toBeVisible();
  await expect(page.getByLabel('Calibration eligibility')).toContainText('NOT_ASSESSED');
  await page.reload();
  await page.getByRole('combobox').first().selectOption('E2E-FIELD-001');
  await page.getByRole('button', { name: 'Field Data' }).click();
  await expect(page.getByRole('heading', { name: /Physics run history \(1\)/ })).toBeVisible();
  await page.getByRole('button', { name: /config v1/ }).click();
  await expect(page.getByLabel('Physics execution run')).toContainText('peak_temperature_c');
  await page.getByLabel('Calibration period start').fill('2026-11-20');
  await page.getByLabel('Calibration period end').fill('2026-11-22');
  await page.getByRole('button', { name: 'Build persisted measurement dataset' }).click();
  await expect(page.getByText(/0 paired observations/)).toBeVisible();
  await expect(page.getByLabel('Calibration dataset details')).toContainText('missing_measurement_types');
  await expect(page.getByLabel('Calibration dataset details')).toContainText('viscosity_cp');
  await expect(page.getByText('Observed and predicted viscosity (cP)')).toHaveCount(0);
});

test('records an incomplete CSS cycle and inspects readiness without invented history', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Field Data' }).click();
  await expect(page.getByRole('heading', { name: 'Petroleum operational records' })).toBeVisible();
  await expect(page.getByText(/No operational events, CSS cycles, or SRP records/)).toBeVisible();
  await page.getByLabel('CSS cycle JSON').fill(JSON.stringify({
    cycle_number: 97,
    injection_start: '2025-06-01T00:00:00Z',
    injection_end: '2025-06-01T08:00:00Z',
    source: 'playwright-controlled-fixture',
    provenance: { source_record_id: 'e2e-cycle-fixture', evidence: 'test-only' },
  }));
  await page.getByRole('button', { name: 'Save CSS cycle' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'CSS cycle saved.' })).toBeVisible();
  await page.getByText('Inspect record and measurement links').click();
  await expect(page.getByText(/"status": "INCOMPLETE"/)).toBeVisible();
  await expect(page.getByText(/Data linkage readiness is not calibration/)).toBeVisible();
  await page.getByLabel('Dataset type').selectOption('css_cycle');
  await page.getByLabel('Period start', { exact: true }).fill('2025-01-01');
  await page.getByLabel('Period end', { exact: true }).fill('2025-12-31');
  await page.getByRole('button', { name: 'Build operational dataset' }).click();
  await expect(page.getByLabel('Operational dataset result')).toContainText('chronological_order_insufficient_groups_or_gap_for_split');
  await page.getByLabel('Operational import record type').selectOption('event');
  const eventRecord = JSON.stringify({ well_id: 'BW-DEMO-001', event_type: 'MAINTENANCE', occurred_at: '2025-06-02T00:00:00Z', external_id: 'e2e-maintenance-97', source: 'playwright-controlled-fixture', provenance: { source_record_id: 'e2e-event-fixture', evidence: 'test-only' } });
  const escapedRecord = `"${eventRecord.replaceAll('"', '""')}"`;
  await page.getByLabel('Operational CSV file').setInputFiles({ name: 'operational-events.csv', mimeType: 'text/csv', buffer: Buffer.from(`schema_version,record_json\n1.0,${escapedRecord}\n`) });
  await page.getByRole('button', { name: 'Import CSV' }).click();
  await expect(page.getByText(/Operational CSV: 1 accepted/)).toBeVisible();
  await expect(page.getByLabel('Well operational timeline')).toContainText('css_cycle');
});

test('exposes measured-data model lifecycle and blocks training in simulation mode', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Field Models' }).click();
  await expect(page.getByRole('heading', { name: 'Field Production Models' })).toBeVisible();
  await expect(page.getByRole('alert')).toContainText('disabled in simulation mode');
  await expect(page.getByRole('button', { name: 'Train measured-data candidate' })).toBeDisabled();
  await expect(page.getByRole('heading', { name: /Model registry/ })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Promoted model inference' })).toBeVisible();
});
