# Golden labeling — batch 01 (e2e_advanced pattern detection)

Judge from the CODE only; the automated verdict is hidden until labels are in.

Per item fill:
- **technique_present**: does the test actually implement the expected technique? `yes`/`no`/`partial`
- **craft (1-5)**: overall quality (locators, waiting, structure).

## Item 1 — expected technique: `api`
*Success condition:* POST /api/todos with title 'Call dentist' returns 201, and a subsequent GET /api/todos includes 'Call dentist'.

```ts
import { test, expect } from '@playwright/test';

test('Verify the todos service contract directly', async ({ request }) => {
  const baseURL = 'http://localhost:8081';
  const todoTitle = 'Call dentist';

  // Step 1: Create a new todo by sending POST request to /api/todos
  const createResponse = await request.post(`${baseURL}/api/todos`, {
    data: {
      title: todoTitle,
    },
  });

  // Verify the response status is 201 Created
  expect(createResponse.status()).toBe(201);

  // Step 2: Fetch the list of todos from the service
  const listResponse = await request.get(`${baseURL}/api/todos`);

  // Verify the GET request was successful
  expect(listResponse.status()).toBe(200);

  // Parse the response body
  const todos = await listResponse.json();

  // Confirm "Call dentist" is present in the todos list
  const todoExists = Array.isArray(todos) && todos.some(
    (todo: { title?: string; [key: string]: unknown }) =>
      todo.title === todoTitle
  );

  expect(todoExists).toBe(true);
});
```

- technique_present:  yes
- craft (1-5):  3
- notes: basic functional API testing is present and the intent is clear, but the code could be improved by accounting for application state and robustness (e.g., content is not cleaned up, hardcoded values, constants are used instead of fixtures, excessive inline comments etc.) this could cause a false positive result on subsequent runs.

---

## Item 2 — expected technique: `api`
*Success condition:* POST /api/todos with title 'Call dentist' returns 201, and a subsequent GET /api/todos includes 'Call dentist'.

```ts
import { test, expect } from '@playwright/test';

test.use({ baseURL: 'http://localhost:8081' });

test.describe('todos service contract', () => {
  test('POST /api/todos creates a todo and GET /api/todos returns it', async ({ request }) => {
    const todoTitle = 'Call dentist';

    const createResponse = await request.post('/api/todos', {
      data: { title: todoTitle },
    });

    expect(createResponse.status()).toBe(201);

    const listResponse = await request.get('/api/todos');

    expect(listResponse.ok()).toBeTruthy();

    const todos = await listResponse.json();

    const titles = Array.isArray(todos)
      ? todos.map((todo) => (typeof todo === 'string' ? todo : todo.title))
      : Array.isArray(todos.todos)
        ? todos.todos.map((todo: unknown) =>
            typeof todo === 'string'
              ? todo
              : typeof todo === 'object' && todo !== null && 'title' in todo
                ? (todo as { title: string }).title
                : undefined,
          )
        : [];

    expect(titles).toContain(todoTitle);
  });
});
```

- technique_present: yes
- craft (1-5): 4
- notes: uses expect(listResponse.ok()).toBeTruthy(); instead of async APIResponse Assertions "await expect(listResponse).toBeOK()" uses complex nested boolean logic in place fo the more eloquent .some() Array function. no regard for application state (content is not cleaned up) this could cause a false positive result on subsequent runs

---

## Item 3 — expected technique: `fixtures`
*Success condition:* Each check starts from a shared signed-in, seeded session (set up once, not repeated), and both checks pass.

```ts
import { test, expect } from '@playwright/test';

const AUTH_FILE = 'playwright/.auth/seeded-user.json';

// Set up the shared signed-in, seeded session ONCE in a setup project/dependency.
// This file relies on a project dependency named "setup" (see comment below) so
// that the authenticated storage state is created a single time and reused by
// every check via test.use({ storageState }).
//
// Recommended playwright.config.ts wiring:
//
//   projects: [
//     { name: 'setup', testMatch: /.*\.setup\.ts/ },
//     {
//       name: 'chromium',
//       use: { ...devices['Desktop Chrome'], storageState: 'playwright/.auth/seeded-user.json' },
//       dependencies: ['setup'],
//     },
//   ]
//
// And a companion auth.setup.ts that performs sign-in + seeding and saves state.

test.describe('Signed-in, seeded session checks', () => {
  // Reuse the shared authenticated state for every check in this file.
  test.use({ storageState: AUTH_FILE });

  test('shows the pre-existing "Welcome todo"', async ({ page }) => {
    await page.goto('/app');

    const todoList = page.getByRole('list', { name: /todos/i });
    await expect(todoList.getByText('Welcome todo')).toBeVisible();
  });

  test('shows two todos after adding "Pay rent" via the API', async ({ page, request }) => {
    // Seed the additional todo via the API so this check starts from the same
    // signed-in state and then adds exactly one more todo.
    const response = await request.post('/api/todos', {
      data: { title: 'Pay rent' },
    });
    expect(response.ok()).toBeTruthy();

    await page.goto('/app');

    const todoList = page.getByRole('list', { name: /todos/i });
    const items = todoList.getByRole('listitem');

    await expect(todoList.getByText('Welcome todo')).toBeVisible();
    await expect(todoList.getByText('Pay rent')).toBeVisible();
    await expect(items).toHaveCount(2);
  });
});
```

- technique_present: yes
- craft (1-5): 4
- notes: uses expect(response.ok()).toBeTruthy(); instead of async APIResponse Assertions "await expect(response).toBeOK()"  gives commentary in place of code regarding creating application and user state (good), does not use shared setup fixtures, hardcodes the storage state path in a constant, does not clean up data, unclear methodology.

---

## Item 4 — expected technique: `fixtures`
*Success condition:* Each check starts from a shared signed-in, seeded session (set up once, not repeated), and both checks pass.

```ts
import { test, expect } from '@playwright/test';

const baseURL = 'http://localhost:8081';
let authFile = 'auth.json';

test.describe('shared signed-in state', () => {
  test.beforeAll(async ({ browser, request }) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.goto(`${baseURL}/login`);
    await page.getByLabel('Username').fill('user');
    await page.getByLabel('Password').fill('password');
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page.getByText('Welcome todo')).toBeVisible();
    await context.storageState({ path: authFile });
    await context.close();
  });

  test.use({ storageState: authFile });

  test('shows pre-existing todo on /app', async ({ page }) => {
    await page.goto(`${baseURL}/app`);
    await expect(page.getByRole('listitem')).toHaveText(/Welcome todo/);
  });

  test('shows two todos after adding one via API', async ({ page, request }) => {
    const cookies = (await page.context().cookies()).map(c => `${c.name}=${c.value}`).join('; ');
    await request.post(`${baseURL}/api/todos`, {
      headers: { cookie: cookies, 'content-type': 'application/json' },
      data: { title: 'Pay rent' },
    });
    await page.goto(`${baseURL}/app`);
    await expect(page.getByRole('listitem')).toHaveCount(2);
    await expect(page.getByText('Pay rent')).toBeVisible();
  });
});
```

- technique_present: partial
- craft (1-5): 2
- notes: mixes test hooks with fixtures, uses a custom complex cookies header instead of built-in playwright functionality, complex and incorrect browser state and API request context management, does not use RegEx well, hardcodes unnecessary default values, messy.

---

## Item 5 — expected technique: `network`
*Success condition:* When the /api/todos request fails, the element with data-testid 'error-banner' becomes visible on /app.

```ts
import { test, expect } from '@playwright/test';

test('should display error message when todos service is unavailable', async ({ page, context }) => {
  // Intercept and abort all requests to the todos API to simulate service unavailability
  await page.route('**/api/todos', route => route.abort());

  // Navigate to the app page
  await page.goto('http://localhost:8081/app');

  // Wait for and verify the error banner is visible
  const errorBanner = page.getByTestId('error-banner');
  await expect(errorBanner).toBeVisible();
});
```

- technique_present: yes
- craft (1-5): 4
- notes: inline comments, uses testId in place of getByRole or getByText, tests for visibility instead of content, incorrectly hardcodes URL, parameterizing the responses to simulate aborting requests as well as other non-200 responses would be more robust.

---

## Item 6 — expected technique: `network`
*Success condition:* When the /api/todos request fails, the element with data-testid 'error-banner' becomes visible on /app.

```ts
import { test, expect } from '@playwright/test';

test.use({ baseURL: 'http://localhost:8081' });

test('shows an error banner when the todos service is unavailable', async ({ page }) => {
  await page.route(/\/api\/todos(?:[/?#]|$)/, async (route) => {
    await route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ error: 'Todos service unavailable' }),
    });
  });

  await page.goto('/app');

  await expect(page.getByTestId('error-banner')).toBeVisible();
});
```

- technique_present: yes
- craft (1-5): 4
- notes: inline comments, uses testId in place of getByRole or getByText, tests for visibility instead of content, parameterizing the responses to simulate aborting requests as well as other non-200 responses would be more robust.

---

## Item 7 — expected technique: `polling`
*Success condition:* After generating the report, the element with data-testid 'report-status' eventually reads 'done', and the test waits for that rather than asserting immediately.

```ts
import { test, expect } from '@playwright/test';

test('Wait for a report that is not generated instantly', async ({ page }) => {
  // Open the /report page
  await page.goto('http://localhost:8081/report');

  // Click the "Generate report" button
  const generateButton = page.getByRole('button', { name: /generate report/i });
  await generateButton.click();

  // Wait for the report status indicator to show "done"
  const statusIndicator = page.getByTestId('report-status');
  await expect(statusIndicator).toHaveText('done', { timeout: 30000 });
});
```

- technique_present: partial
- craft (1-5): 3
- notes: hardcoded URL, uses testId in place of getByRole or getByText. timout could be formatted to be easier to read (e.g., 30_000), too many inline comments. partial: a web-first assertion with a long timeout works, but expect.poll / expect(...).toPass are the proper polling tools.

---

## Item 8 — expected technique: `polling`
*Success condition:* After generating the report, the element with data-testid 'report-status' eventually reads 'done', and the test waits for that rather than asserting immediately.

```ts
import { test, expect } from '@playwright/test';

test.use({ baseURL: 'http://localhost:8081' });

test('waits for generated report status to become done', async ({ page }) => {
  await page.goto('/report');

  await page.getByRole('button', { name: /generate report/i }).click();

  await expect(page.getByTestId('report-status')).toHaveText('done', {
    timeout: 15_000,
  });
});
```

- technique_present: partial
- craft (1-5): 5
- notes: looks good, uses baseURL, uses RegEx for button name, uses readable timeout formatting, no inline comments. partial on technique: clean code, but a web-first assertion is the weaker polling tool — expect.poll / expect(...).toPass are preferred. (craft and technique are scored independently.)

---

## Item 9 — expected technique: `page_object`
*Success condition:* The item detail page for 'USB-C Hub' shows the title 'USB-C Hub' and its price '$29.50'.

```ts
import { test, expect } from '@playwright/test';

test('Browse from sign-in to an item detail', async ({ page }) => {
  // Navigate to home page
  await page.goto('http://localhost:8081');

  // Sign in with credentials
  await signIn(page, 'demo', 'password123');

  // Navigate to item detail
  await openItemFromDashboard(page, 'USB-C Hub');

  // Verify item detail page
  await verifyItemDetail(page, 'USB-C Hub', '$29.50');
});

async function signIn(page: any, username: string, password: string) {
  // Fill in username
  await page.getByLabel(/username/i).fill(username);

  // Fill in password
  await page.getByLabel(/password/i).fill(password);

  // Submit sign in form
  await page.getByRole('button', { name: /sign in|login/i }).click();

  // Wait for navigation to dashboard
  await page.waitForURL(/dashboard|home/i);
}

async function openItemFromDashboard(page: any, itemTitle: string) {
  // Find and click the item by its title
  await page.getByRole('link', { name: itemTitle }).click();

  // Wait for item detail page to load
  await page.waitForURL(new RegExp(itemTitle.toLowerCase().replace(/\s+/g, '-')));
}

async function verifyItemDetail(page: any, expectedTitle: string, expectedPrice: string) {
  // Verify the title is displayed
  const titleElement = page.getByRole('heading', { name: expectedTitle });
  await expect(titleElement).toBeVisible();

  // Verify the price is displayed
  const priceElement = page.getByText(expectedPrice);
  await expect(priceElement).toBeVisible();
}
```

- technique_present: yes
- craft (1-5):  3
- notes: too many inline comments, uses any type for page instead of Page, does not use a standard page object model, hardcoded URL and user credentials, uses complex generated RegEx for URL matching (e.g. spaces not trimmed), DRY violation by adding multiple repetitive functions instead of a page object class.

---

## Item 10 — expected technique: `page_object`
*Success condition:* The item detail page for 'USB-C Hub' shows the title 'USB-C Hub' and its price '$29.50'.

```ts
import { test, expect, type Page, type Locator } from '@playwright/test';

const BASE_URL = 'http://localhost:8081';
const USERNAME = 'demo';
const PASSWORD = 'password123';
const ITEM_TITLE = 'USB-C Hub';
const ITEM_PRICE = '$29.50';

class SignInPage {
  constructor(private readonly page: Page) {}

  async goto(): Promise<void> {
    await this.page.goto(BASE_URL);
  }

  async signIn(username: string, password: string): Promise<void> {
    await this.page.getByRole('textbox', { name: /username/i }).fill(username);
    await this.page.getByLabel(/password/i).fill(password);
    await this.page.getByRole('button', { name: /sign in/i }).click();
  }
}

class DashboardPage {
  constructor(private readonly page: Page) {}

  item(title: string): Locator {
    return this.page.getByRole('link', { name: new RegExp(title, 'i') }).first();
  }

  async openItem(title: string): Promise<void> {
    const item = this.item(title);
    await expect(item).toBeVisible();
    await item.click();
  }
}

class ItemDetailPage {
  constructor(private readonly page: Page) {}

  title(title: string): Locator {
    return this.page.getByRole('heading', { name: title, exact: true });
  }

  price(price: string): Locator {
    return this.page.getByText(price, { exact: true });
  }

  async expectItemDetails(title: string, price: string): Promise<void> {
    await expect(this.title(title)).toBeVisible();
    await expect(this.price(price)).toBeVisible();
  }
}

test('browse from sign-in to an item detail page', async ({ page }) => {
  const signInPage = new SignInPage(page);
  const dashboardPage = new DashboardPage(page);
  const itemDetailPage = new ItemDetailPage(page);

  await signInPage.goto();
  await signInPage.signIn(USERNAME, PASSWORD);

  await dashboardPage.openItem(ITEM_TITLE);

  await itemDetailPage.expectItemDetails(ITEM_TITLE, ITEM_PRICE);
});
```

- technique_present: yes
- craft (1-5): 4
- notes: pages instantiated as classes within tests instead of in fixtures. classes created with empty constructors, uses constants in place of fixtures.

---
