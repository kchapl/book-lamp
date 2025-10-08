import { defineConfig, devices } from '@playwright/test';

const PORT = process.env.PORT ? Number(process.env.PORT) : 5000;
const BASE_URL = process.env.BASE_URL || `http://127.0.0.1:${PORT}`;

export default defineConfig({
    testDir: './tests-e2e',
    globalSetup: require.resolve('./tests-e2e/global.setup'),
    fullyParallel: true,
    forbidOnly: !!process.env.CI,
    retries: process.env.CI ? 2 : 0,
    workers: process.env.CI ? 2 : undefined,
    reporter: [['html', { open: 'never' }], ['list']],
    use: {
        baseURL: BASE_URL,
        trace: 'on-first-retry',
        screenshot: 'only-on-failure',
        video: 'retain-on-failure',
    },
    webServer: {
        command: `TEST_MODE=1 FLASK_DEBUG=false FLASK_APP=book_lamp.app:app DB_URL=sqlite:///e2e_test.db poetry run flask run --port ${PORT} --host 127.0.0.1`,
        url: BASE_URL,
        timeout: 60_000,
        reuseExistingServer: !process.env.CI,
    },
    projects: [
        {
            name: 'chromium',
            use: { ...devices['Desktop Chrome'] },
        },
    ],
});


