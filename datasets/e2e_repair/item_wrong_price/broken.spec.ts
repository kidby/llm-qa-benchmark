import { test, expect } from '@playwright/test';

test('item detail shows price', async ({ page }) => {
  await page.goto('http://localhost:8081/items/2');
  await expect(page.getByTestId('item-title')).toHaveText('USB-C Hub');
  await expect(page.getByTestId('item-price')).toHaveText('$30.00');
});
