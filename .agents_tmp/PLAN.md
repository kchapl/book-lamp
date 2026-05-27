# Plan: Migrate from Poetry to uv

## 1. OBJECTIVE

Migrate the **book-lamp** project from Poetry to **uv** as the Python dependency and environment manager, following the [uv documentation](https://docs.astral.sh/uv/).

## 2. CONTEXT SUMMARY

- **Backend**: Python 3.13, Flask, Poetry, psycopg3, Alembic
- **Frontend**: React 18, TypeScript, Vite, npm
- **Tooling**: `mise`, `poetry`, `npm`, `ruff`, `mypy`, `black`, `isort`

Files requiring changes:
| File | Changes |
|------|---------|
| `pyproject.toml` | Convert `[tool.poetry]` to `[project]` + `[tool.uv]` |
| `mise.toml` | Replace `poetry` tool with `uv` |
| `README.md` | Update commands from `poetry run` → `uv run` |
| `GEMINI.md` | Update tooling references |
| `AGENT_CONTEXT.md` | Update tooling references |
| `DEPLOYMENT.md` | Update build commands |
| `.github/workflows/ci.yml` | Replace Poetry setup with uv in all 3 jobs |
| Generate `uv.lock` | Run `uv lock` to create lock file |

## 3. APPROACH OVERVIEW

Convert the project to use uv as the primary Python package manager. This involves:
1. Converting `pyproject.toml` from Poetry to standard `[project]` format compatible with uv
2. Updating `mise.toml` to use uv instead of poetry
3. Updating all documentation and CI/CD workflows
4. Generating the `uv.lock` file for reproducible installs

## 4. IMPLEMENTATION STEPS

### Step 1: Update `pyproject.toml`
- **Goal**: Convert from Poetry format to uv-compatible format AND pin all dependencies to specific versions
- **Method**: 
  - Replace `[tool.poetry]` with `[project]` (PEP 621 metadata)
  - Convert all version specifiers (e.g., `^3.13`, `>=1.0`) to exact pins (e.g., `3.13.0`, `1.0.0`)
  - Add `[tool.uv]` section for tool-specific settings
  - Remove `[build-system]` poetry-core references
- **Reference**: `pyproject.toml`

### Step 2: Update `mise.toml`
- **Goal**: Use uv instead of poetry in mise configuration
- **Method**: Replace `poetry = "latest"` with `uv = "latest"`
- **Reference**: `mise.toml`

### Step 3: Update documentation files
- **Goal**: Replace all poetry references with uv equivalents
- **Method**: Update all instances of:
  - `poetry install` → `uv sync`
  - `poetry run` → `uv run`
  - `poetry.lock` → `uv.lock`
- **Files**: `README.md`, `GEMINI.md`, `AGENT_CONTEXT.md`, `DEPLOYMENT.md`

### Step 4: Update CI/CD workflows
- **Goal**: Replace Poetry setup with uv in GitHub Actions
- **Method**:
  - Remove `POETRY_VERSION` env var
  - Use `astral-sh/setup-uv` action instead of `snok/install-poetry`
  - Update cache keys from `poetry.lock` to `uv.lock`
  - Replace `poetry install` with `uv sync`
  - Replace `poetry run` with `uv run`
- **Reference**: `.github/workflows/ci.yml` (3 jobs: test, lint-and-format, performance)

### Step 5: Generate `uv.lock`
- **Goal**: Create uv lock file for reproducible installs
- **Method**: Run `uv lock` to generate `uv.lock`
- **Reference**: Project root

## 5. TESTING AND VALIDATION

- **Verify `pyproject.toml`**: Run `uv python pin` to confirm uv recognizes the project
- **Verify dependencies**: Run `uv sync` to install dependencies
- **Verify tests**: Run `uv run pytest` to ensure all tests pass
- **Verify CI**: Run `uv run ruff check . && uv run mypy .` to confirm linting works
- **Verify lock file**: Confirm `uv.lock` is generated and contains all dependencies
