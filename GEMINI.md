# GEMINI.md

## Project Overview
**book-lamp** is a personal reading history tracker that uses **Google Sheets** as its primary storage engine. It is built with a **Python (Flask)** backend and a **TypeScript** frontend, emphasizing privacy by only requesting the minimum necessary Google Drive permissions (`drive.file` scope).

### Key Features
- **Google Sheets Integration:** No traditional database; all reading data is stored in spreadsheet tabs.
- **AI Recommendations:** Optional book recommendations powered by LLMs (OpenAI).
- **Barcode Scanning:** Frontend supports barcode scanning via `html5-qrcode`.
- **Import/Export:** Supports importing reading history from Libib CSV files.
- **Metadata Enrichment:** Automatically fetches book covers and metadata (e.g., BISAC categories) from Open Library and Google Books.

### Core Technologies
- **Backend:** Python 3.13, Flask, Poetry, Authlib (OAuth), Google API Client.
- **Frontend:** TypeScript, Vitest (Testing), Vanilla CSS, Jinja2 Templates.
- **Tooling:** `mise` (tool version management), `poetry`, `npm`, `ruff`, `mypy`, `black`, `isort`.

---

## Building and Running

### Prerequisites
- **mise** (recommended for managing Python/Node/Poetry versions).
- **Google Cloud Console Project:** Required for OAuth credentials (Client ID and Secret).

### Initial Setup
1. **Install Dependencies:**
   ```bash
   poetry install
   npm install
   ```
2. **Configure Environment:**
   Create a `.env` file based on `.env.example`:
   ```env
   FLASK_ENV=development
   SECRET_KEY=your_secret_key
   GOOGLE_CLIENT_ID=your_oauth_client_id
   GOOGLE_CLIENT_SECRET=your_oauth_client_secret
   LLM_API_KEY=optional_openai_key
   ```
3. **Build Frontend:**
   ```bash
   npm run build
   ```

### Running the Application
```bash
poetry run flask --app book_lamp.app run
```

### Testing
- **Backend (Pytest):** `poetry run pytest`
- **Frontend (Vitest):** `npm test`
- **Lighthouse:** `npm run lighthouse:ci`

---

## Development Conventions

### Engineering Principles
- **Clarity over Cleverness:** Prefer readable, explicit code and simple designs.
- **Pure/Effectful Separation:** Keep domain logic in pure functions; isolate I/O (Sheets API, network) at the edges behind adapters.
- **British English:** All comments and naming must use British English (e.g., `authorisation`).
- **Small Edits:** Make incremental, cohesive edits with tests; avoid large, risky rewrites.

### Coding Standards
- **Python:**
  - Use `poetry run` for all commands.
  - Format with `black` and `isort` (default configs).
  - Lint with `ruff` and type-check with `mypy` (strict mode).
  - Routes should be thin; delegate logic to services.
- **Frontend:**
  - **TypeScript Only:** All logic MUST be in `src/ts/`. Never edit compiled `.js` files in `static/`.
  - **CSS:** Use dedicated files in `static/` (e.g., `base.css`, `books.css`). No inline styles or `<style>` blocks in HTML.
  - **HTML:** Keep templates focused on structure and Jinja2 logic.

### Testing Policy
- **Mandatory Testing:** All new features must have unit tests.
- **Mocking:** Only mock process boundaries (Sheets API, network).
- **Regression Tests:** Add a test for every bug fix.
- **TEST_MODE:** Uses `MockStorage` (in-memory) instead of real Google Sheets.

### Security & Reliability
- **Protobuf Patch:** A security patch for CVE-2026-0994 is applied in `app.py`. Ensure this remains at the entry point.
- **No Regex Search:** Do not use unsanitized user input in regular expressions to prevent ReDoS.
- **Safe Redirects:** Use `get_safe_redirect_target` for user-controlled redirects.

---

## Project Structure
- `book_lamp/`: Main Python package.
  - `app.py`: Flask application entry point and routes.
  - `services/`: Business logic and storage adapters (e.g., `sheets_storage.py`).
  - `templates/`: Jinja2 HTML templates.
  - `static/`: Compiled JS, CSS, and assets.
- `src/ts/`: TypeScript source files.
- `tests/`: Backend test suite.
- `scripts/`: Utility scripts (e.g., Lighthouse reporting).
- `pyproject.toml` / `package.json`: Dependency manifests.
