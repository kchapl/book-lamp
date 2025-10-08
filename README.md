# book-lamp

Using `colima` for local docker management.
# TODO stop and start automatically

## End-to-end tests (Playwright)

Install Node dependencies once:

```bash
npm ci
npx playwright install --with-deps
```

Run the E2E suite (starts the app automatically):

```bash
npm test
```

Headed mode:

```bash
npm run test:ui
```

Artifacts (screenshots/videos/traces) are saved under `playwright-report/` and `test-results/`.
