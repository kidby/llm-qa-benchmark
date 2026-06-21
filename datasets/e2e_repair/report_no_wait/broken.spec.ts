import { test, expect } from '@playwright/test';

test('report finishes', async ({ page }) => {
  await page.goto('http://localhost:8081/report');
  await page.getByTestId('generate').click();
  const text = await page.getByTestId('report-status').textContent();
  expect(text).toBe('done');
});
