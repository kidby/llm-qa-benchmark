import { test, expect } from '@playwright/test';

test('open item detail', async ({ page }) => {
  await page.goto('http://localhost:8081/item/2');
  await expect(page.getByTestId('item-title')).toHaveText('USB-C Hub');
});
