import { test, expect } from '@playwright/test';

test.describe('SynterionX Web Platform E2E Tests', () => {

  test('1. Login page renders brand assets, logo, and form inputs', async ({ page }) => {
    await page.goto('/login');

    // Page title verification
    await expect(page).toHaveTitle(/SynterionX/i);

    // Brand and logo verification
    const heading = page.getByRole('heading', { name: 'SYNTERIONX' });
    await expect(heading).toBeVisible();

    const logo = page.locator('img[alt="SynterionX Logo"]');
    await expect(logo).toBeVisible();

    // Form inputs verification
    const usernameInput = page.getByPlaceholder(/Enter username/i);
    const passwordInput = page.getByPlaceholder(/Enter password/i);
    const submitBtn = page.getByRole('button', { name: /Sign In/i });

    await expect(usernameInput).toBeVisible();
    await expect(passwordInput).toBeVisible();
    await expect(submitBtn).toBeVisible();
  });

  test('2. Client-side validation: empty credentials block submission and show warning', async ({ page }) => {
    await page.goto('/login');

    // Click submit with empty username
    await page.getByRole('button', { name: /Sign In/i }).click();
    const usernameError = page.locator('.bg-rose-50');
    await expect(usernameError).toBeVisible();
    await expect(usernameError).toContainText(/Username is required/i);

    // Fill username only, click submit with empty password
    await page.getByPlaceholder(/Enter username/i).fill('admin');
    await page.getByRole('button', { name: /Sign In/i }).click();
    const passwordError = page.locator('.bg-rose-50');
    await expect(passwordError).toBeVisible();
    await expect(passwordError).toContainText(/Password is required/i);
  });

  test('3. Error handling: invalid credentials trigger descriptive error banner', async ({ page }) => {
    await page.goto('/login');

    // Enter wrong credentials
    await page.getByPlaceholder(/Enter username/i).fill('invalid_user_999');
    await page.getByPlaceholder(/Enter password/i).fill('wrong_password_xyz');
    await page.getByRole('button', { name: /Sign In/i }).click();

    // Verify error banner is displayed
    const errorBanner = page.locator('.bg-rose-50');
    await expect(errorBanner).toBeVisible({ timeout: 5000 });
    await expect(errorBanner).toContainText(/Invalid username or password|Account may be locked/i);
  });

  test('4. Successful authentication and operations console landing', async ({ page }) => {
    await page.goto('/login');

    // Login with valid credentials
    await page.getByPlaceholder(/Enter username/i).fill('admin');
    await page.getByPlaceholder(/Enter password/i).fill('admin123');
    await page.getByRole('button', { name: /Sign In/i }).click();

    // Should redirect to root operations dashboard
    await page.waitForURL('**/', { timeout: 8000 });
    await expect(page).toHaveURL('http://127.0.0.1:4173/');

    // Verify Navbar header elements
    const brand = page.getByRole('heading', { name: /SYNTERION X/i });
    await expect(brand).toBeVisible();

    // Verify Sidebar navigation items
    await expect(page.getByRole('link', { name: /Dashboard/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /Live Monitoring/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /Camera List/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /Notifications/i })).toBeVisible();
  });

  test('5. Sidebar navigation between core modules without console errors', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    // Authenticate first
    await page.goto('/login');
    await page.getByPlaceholder(/Enter username/i).fill('admin');
    await page.getByPlaceholder(/Enter password/i).fill('admin123');
    await page.getByRole('button', { name: /Sign In/i }).click();
    await page.waitForURL('**/', { timeout: 8000 });

    // Navigate to Camera List
    await page.getByRole('link', { name: /Camera List/i }).click();
    await page.waitForURL('**/cameras', { timeout: 5000 });
    await expect(page).toHaveURL(/.*\/cameras/);

    // Navigate to Notifications
    await page.getByRole('link', { name: /Notifications/i }).click();
    await page.waitForURL('**/notifications', { timeout: 5000 });
    await expect(page).toHaveURL(/.*\/notifications/);

    // Navigate to Live Monitoring
    await page.getByRole('link', { name: /Live Monitoring/i }).click();
    await page.waitForURL('**/monitoring', { timeout: 5000 });
    await expect(page).toHaveURL(/.*\/monitoring/);

    // Navigate to System Status
    await page.getByRole('link', { name: /System Status/i }).click();
    await page.waitForURL('**/system', { timeout: 5000 });
    await expect(page).toHaveURL(/.*\/system/);

    // Navigate back to Dashboard
    await page.getByRole('link', { name: /Dashboard/i }).click();
    await page.waitForURL('**/', { timeout: 5000 });
    await expect(page).toHaveURL('http://127.0.0.1:4173/');

    // Filter out expected dev/websocket transient logs
    const criticalErrors = consoleErrors.filter(
      err => !err.includes('favicon') && !err.includes('WebSocket') && !err.includes('ws proxy')
    );
    expect(criticalErrors).toHaveLength(0);
  });

  test('6. Sign out clears session and redirects back to login page', async ({ page }) => {
    // Authenticate first
    await page.goto('/login');
    await page.getByPlaceholder(/Enter username/i).fill('admin');
    await page.getByPlaceholder(/Enter password/i).fill('admin123');
    await page.getByRole('button', { name: /Sign In/i }).click();
    await page.waitForURL('**/', { timeout: 8000 });

    // Click Sign Out in Navbar
    const signOutBtn = page.getByRole('button', { name: /Sign Out/i });
    await expect(signOutBtn).toBeVisible();
    await signOutBtn.click();

    // Verify redirected back to /login
    await page.waitForURL('**/login', { timeout: 5000 });
    await expect(page).toHaveURL(/.*\/login/);

    // Try navigating back to root dashboard - should redirect to /login because token is gone
    await page.goto('/');
    await page.waitForURL('**/login', { timeout: 5000 });
    await expect(page).toHaveURL(/.*\/login/);
  });
});

