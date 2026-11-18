# Testing

Three layers, each with a job the others cannot do:

| Layer | Where | Runs | Covers |
| --- | --- | --- | --- |
| Unit | `tests/`, `src/react/**/__tests__` | pytest, vitest | Pure rules, rendering, request and payload shapes. |
| In-memory integration | `tests/` with `TEST_MODE=1` | pytest | Routes and storage against the in-memory adapter. |
| End-to-end | `e2e/` | Playwright, chromium | The journeys a reader actually takes, against the built SPA. |

## The rule

**End-to-end tests are part of the standard.** A change that adds or alters a
user-facing screen updates `e2e/` first: write the new journey before the
implementation, so the test states the intended behaviour. A new or reshaped
screen also gets a screenshot baseline. A pull request that changes the
interface without touching the suite is incomplete.

This reverses the earlier position that the app needed unit and mock
integration tests only. That position was written down with the removed
Playwright suite; it is no longer the repo's stance.

## Running it

```bash
npx playwright install chromium   # once per machine
npm run build                     # the suite serves the built SPA
npm run test:e2e
```

Regenerate baselines only when the visual change is intended, and review the
images before committing them:

```bash
npm run test:e2e:update
```

## What makes it deterministic

The suite runs with **no retries**, so an intermittent failure is a bug to fix,
not something to paper over.

- `workers: 1` — the test store is one process-wide object.
- `timezoneId: 'UTC'`, `locale: 'en-US'`, `colorScheme: 'light'`,
  `reducedMotion: 'reduce'`, and a fixed viewport.
- Fonts are served by the app from `book_lamp/static/fonts/`; the suite makes no
  request to a font host, so text rasterises the same way everywhere.
- Screenshots are taken only after loading states are gone and `document.fonts`
  is ready. The footer year is hidden, and the seeded Reading dates are fixed
  rather than "this year", so the clock cannot leak into a baseline.
- Baselines must be produced on the platform the suite runs on (Linux in CI).

## The test harness

`TEST_MODE=1` drives the app without Google or PostgreSQL:

- `/test/reset` clears the in-memory store.
- `/test/connect` and `/test/disconnect` sign the test reader in and out, which
  is what makes the auth gate testable.
- `/api/books/lookup` answers the canned ISBN `9780000000000` as "Test Book".
- CSRF checks are bypassed.

The flag bypasses sign-in, so `create_app()` refuses it unless the process is
in development (`FLASK_DEBUG`, or `APP_ENV=development`) or CI (`CI`). A
production process (`APP_ENV=production`) refuses it even when `CI` is set, and
fails to start with a clear error.

## Out of scope

- Exercising Google sign-in itself: only the gate and the authorised state are
  tested.
- PostgreSQL: the in-memory adapter is the subject.
- Cross-browser matrices — chromium only.
- Load, performance and accessibility tooling.
