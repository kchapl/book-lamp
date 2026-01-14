# book-lamp

A personal reading history tracker using Google Sheets for storage.

## Setup

1. Install dependencies: `poetry install`
2. Follow [SHEETS_SETUP.md](SHEETS_SETUP.md) to configure Google Sheets
3. Create `.env` file with required variables:
   ```
   FLASK_ENV=development
   GOOGLE_CLIENT_ID=your_oauth_client_id
   GOOGLE_CLIENT_SECRET=your_oauth_client_secret

   SECRET_KEY=your_secret_key
   ```
4. Initialize sheets: `poetry run flask --app book_lamp.app init-sheets`
5. Run the app: `poetry run flask --app book_lamp.app run`

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
