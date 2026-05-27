# GEMINI.md

## Project Overview
**book-lamp** is a personal reading history tracker that uses **PostgreSQL** as its primary storage engine. It is built with a **Python (Flask)** backend and a **TypeScript** frontend, designed for self-hosting with cloud database providers like Neon.

### Key Features
- **PostgreSQL Integration:** All reading data is stored in PostgreSQL tables with Alembic migrations.
- **AI Recommendations:** Optional book recommendations powered by LLMs (OpenAI).
- **Barcode Scanning:** Frontend supports barcode scanning via `html5-qrcode`.
- **Import/Export:** Supports importing reading history from Libib CSV files.
- **Metadata Enrichment:** Automatically fetches book covers and metadata (e.g., BISAC categories) from Open Library and Google Books.

### Core Technologies
- **Backend:** Python 3.13, Flask, uv, psycopg3, Alembic.
- **Frontend:** React 18, TypeScript, Vite (Build), React Router, @dnd-kit (Drag and Drop), html5-qrcode.
- **Tooling:** `mise` (tool version management), `uv`, `npm`, `ruff`, `mypy`, `black`, `isort`.

---

## Building and Running

### Prerequisites
- **mise**: (Required) This project uses `mise` to manage Python, Node, and uv versions. Ensure it is installed and configured.

### Initial Setup
1. **Install Tools:**
   ```bash
   mise install
   ```
2. **Install Dependencies:**
   ```bash
   uv sync --all-extras
   npm install
   ```
2. **Configure Environment:**
   Create a `.env` file based on `.env.example`:
   ```env
   FLASK_DEBUG=True
   SECRET_KEY=your_secret_key
   DATABASE_URL=postgresql://localhost/booklamp
   GOOGLE_CLIENT_ID=optional_oauth_client_id
   LLM_API_KEY=optional_openai_key
   ```
3. **Start Database:**
   ```bash
   podman-compose up -d
   uv run alembic upgrade head
   ```
4. **Build Frontend:**
   ```bash
   # Build vanilla TypeScript (legacy)
   npm run build:ts
   
   # Build React SPA
   npm run build:react
   
   # Or build both
   npm run build
   ```

### Running the Application
```bash
# Start the Flask development server
uv run flask --app book_lamp.app run

# For development with hot reload
npm run dev
```

### Testing
- **Backend (Pytest):** `uv run pytest`
- **Frontend (Vitest):** `npm test`
- **Lighthouse:** `npm run lighthouse:ci`

---

## Development Conventions

### Engineering Principles
- **Clarity over Cleverness:** Prefer readable, explicit code and simple designs.
- **Pure/Effectful Separation:** Keep domain logic in pure functions; isolate I/O (PostgreSQL, network) at the edges behind adapters.
- **British English:** All comments and naming must use British English (e.g., `authorisation`).
- **Small Edits:** Make incremental, cohesive edits with tests; avoid large, risky rewrites.

### Coding Standards
- **Python:**
  - Use `uv run` for all commands.
  - Format with `black` and `isort` (default configs).
  - Lint with `ruff` and type-check with `mypy` (strict mode).
  - Routes should be thin; delegate logic to services.
- **Frontend:**
  - **React 18:** All new UI MUST use React components in `src/react/`.
  - **TypeScript Only:** All logic MUST be in TypeScript. Never edit compiled files directly.
  - **CSS:** Use dedicated files in `static/css/` for global styles. React-specific styles in `src/react/styles/`.
  - **HTML:** Keep templates focused on structure and Jinja2 logic. React renders UI via components.

### Testing Policy
- **Mandatory Testing:** All new features must have unit tests.
- **Mocking:** Only mock process boundaries (PostgreSQL, network).
- **Regression Tests:** Add a test for every bug fix.
- **TEST_MODE:** Uses `MockStorage` (in-memory) instead of real Google Sheets.

### Security & Reliability
- **Database Security:** Use parameterized queries; validate all inputs before database operations.
- **No Regex Search:** Do not use unsanitized user input in regular expressions to prevent ReDoS.
- **Safe Redirects:** Use `get_safe_redirect_target` for user-controlled redirects.

---

## Project Structure
- `book_lamp/`: Main Python package.
  - `app.py`: Flask application entry point and routes (serves both Jinja2 templates and React SPA).
  - `services/`: Business logic and storage adapters (e.g., `postgres_storage.py`).
  - `templates/`: Jinja2 HTML templates (legacy) and `index.html` (React SPA entry point).
  - `static/`: Compiled JS, CSS, and assets. React app is built to `static/react/`.
- `src/ts/`: Legacy vanilla TypeScript source files.
- `src/react/`: React 18 application (replaces vanilla TypeScript).
  - `pages/`: Page components (Home, Books, History, etc.)
  - `components/`: Shared UI components (Layout, etc.)
  - `services/`: API service layer.
  - `types/`: TypeScript type definitions.
  - `styles/`: React-specific CSS styles.
- `tests/`: Backend test suite.
- `scripts/`: Utility scripts (e.g., Lighthouse reporting).
- `pyproject.toml` / `package.json`: Dependency manifests.
