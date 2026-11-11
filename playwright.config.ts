import { defineConfig } from '@playwright/test';
import { BASE_URL } from './e2e/env';

/**
 * End-to-end coverage of the journeys a reader actually takes.
 *
 * Determinism is not optional: the suite runs with no retries, so the clock,
 * locale, colour scheme, motion and viewport are pinned, and the app serves its
 * own fonts. The subject is the built SPA on Flask with `TEST_MODE=1` and the
 * in-memory store: no database, no Google credentials, no manual step.
 */
export default defineConfig({
    testDir: './e2e',
    fullyParallel: false,
    // One worker: the test store is a single process-wide object, so specs
    // that share it must not run at the same time.
    workers: 1,
    retries: 0,
    forbidOnly: !!process.env.CI,
    timeout: 15_000,
    globalTimeout: 60_000,
    expect: {
        timeout: 5_000,
        toHaveScreenshot: {
            animations: 'disabled',
            caret: 'hide',
            // Rendering can differ by a few pixels between Linux images; the
            // threshold catches layout and content changes, not antialiasing.
            maxDiffPixelRatio: 0.002,
        },
    },
    reporter: process.env.CI ? [['github'], ['list']] : [['list']],
    globalSetup: './e2e/global-setup.ts',
    use: {
        baseURL: BASE_URL,
        timezoneId: 'UTC',
        locale: 'en-US',
        colorScheme: 'light',
        reducedMotion: 'reduce',
        viewport: { width: 1280, height: 900 },
        trace: 'retain-on-failure',
    },
    projects: [{ name: 'chromium', use: { browserName: 'chromium' } }],
    webServer: {
        command: 'uv run flask --app book_lamp.app run --port 5055',
        url: BASE_URL,
        // A stale server would serve a different build than the one under test.
        reuseExistingServer: false,
        timeout: 30_000,
        env: {
            TEST_MODE: '1',
            // Development is what makes TEST_MODE legal without the debug
            // reloader; the guard in book_lamp/__init__.py enforces that.
            APP_ENV: 'development',
            SECRET_KEY: 'e2e-secret',
            GOOGLE_CLIENT_ID: 'dummy-client-id',
            // Recommendations are a live provider call; an unconfigured key
            // makes the route answer with an empty list, offline.
            LLM_API_KEY: '',
        },
    },
});
