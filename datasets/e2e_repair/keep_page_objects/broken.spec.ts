import { test, expect, type Page } from '@playwright/test';

class ItemPage {
  constructor(private readonly page: Page) {}

  async open(id: string): Promise<void> {
    // Bug: the detail route is /items/<id>, not /item/<id>.
    await this.page.goto(`http://localhost:8081/item/${id}`);
  }

  title() {
    return this.page.getByTestId('item-title');
  }

  price() {
    return this.page.getByTestId('item-price');
  }
}

test('item detail shows title and price', async ({ page }) => {
  const item = new ItemPage(page);
  await item.open('2');
  await expect(item.title()).toHaveText('USB-C Hub');
  await expect(item.price()).toHaveText('$29.50');
});
