import { defineConfig, devices } from '@playwright/test';

const PORT = process.env.PORT ? Number(process.env.PORT) : 5000;
const BASE_URL = process.env.BASE_URL || `http://127.0.0.1:${PORT}`;

export default defineConfig({
    testDir: './tests-e2e',
    globalSetup: require.resolve('./tests-e2e/global.setup'),
    // Run tests serially to prevent database conflicts
    fullyParallel: false,
    forbidOnly: !!process.env.CI,
    retries: process.env.CI ? 2 : 0,
    workers: 1,
    reporter: [['html', { open: 'never' }], ['list']],
    use: {
        baseURL: BASE_URL,
        trace: 'on-first-retry',
        screenshot: 'only-on-failure',
        video: 'retain-on-failure',
    },
    webServer: {
        command: `poetry run flask --app book_lamp.app run --port ${PORT} --host 127.0.0.1`,
        url: BASE_URL,
        timeout: 180000, // Increased timeout for CI
        reuseExistingServer: !process.env.CI,
        env: {
            TEST_MODE: '1',
            FLASK_DEBUG: 'false',
            FLASK_APP: 'book_lamp.app',
            DB_URL: 'sqlite:///e2e_test.db',
        },
        stdout: 'pipe',
        stderr: 'pipe',
    },
    expect: {
        timeout: 30000, // Increased timeout for all assertions
    },
    projects: [
        {
            name: 'chromium',
            use: { ...devices['Desktop Chrome'] },
        },
    ],
});
