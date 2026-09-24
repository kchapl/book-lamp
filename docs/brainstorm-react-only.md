# Brainstorm: a fully React Book Lamp

The app has already drifted a long way toward React. Today:

- **React SPA is live for every page route.** `/`, `/books`, `/history`, `/dashboard`, `/author/...`, `/unauthorised`, and the catch-all all serve `static/react/index.html` via `book_lamp/routes/spa.py`. Verified with a live server in TEST_MODE: every route returns the React shell; the Jinja fallback is unreachable in practice.
- **One Jinja call left.** `render_template("index.html")` in `spa.py` is a dead fallback branch that only triggers if `static/react/index.html` is missing (i.e. a broken build).
- **Jinja2 is still a hard Flask dependency** (Flask bundles it), so removing templates doesn't remove the library — but it removes all *template logic* from the product surface.
- **A full legacy layer survives in the repo** and is now misleading:
  - 15 Jinja templates in `book_lamp/templates/` (only `index.html` is technically reachable, and only on a broken build).
  - Legacy browser-form routes are gone (POSTs to `/books` etc. return 405), but ~29 backend tests still exercise the old form-post + full-page-HTML behaviour (`test_manual_entry.py`, `test_books.py`, `test_history.py`, `test_search.py`, `test_author_page.py`, parts of `test_libib_import.py`), all failing or asserting markup that no longer exists.
  - `src/ts/` legacy vanilla TS is still compiled by `npm run build` and copied into `static/` alongside the React bundle.
  - Docs (`README`, `GEMINI.md`, `AGENT_CONTEXT.md`) still describe a dual template/React world, and `GEMINI.md` says "React 18" while the app is on React 19.2.
  - `book_lamp/static/react/index.html` is a committed build artefact whose script tags are re-written on each build.

The ask — "remove use of Jinja2 templates so the app is entirely React" — is therefore less a porting job and more a **removal-and-rewiring job**. That opens several possible shapes, ranked below by value for cost.

## Ideas, ranked by value for cost

### 1. Delete the template layer and harden the SPA shell (Top pick)
**What it is.** Remove `book_lamp/templates/` entirely; drop `template_folder` from the app factory; delete `render_template` and its import from `spa.py` so the SPA handler fails loudly (503 with a hint to run `npm run build`) if the built shell is missing; migrate the stale template-era backend tests to the JSON API surface the React app actually calls.

**Why a demanding user would notice.** No more dead fallback silently serving a shell-less page on a broken build; removes ~1,550 lines of dead template code that has already produced a red test suite and misleads contributors; container images built from the repo get smaller.

**Cost.** Low-to-medium. One focused change to `spa.py` + app factory, `git rm` of templates, a test-sweep, and docs. Nothing user-visible changes.

### 2. De-legacy the frontend build
**What it is.** Drop the vanilla-TS `src/ts/` pipeline from `npm run build` (`tsc && cp -r book_lamp/static/ts/* book_lamp/static/ && vite build` becomes just `vite build`), delete `src/ts/` and its compiled copies in `book_lamp/static/`.

**Why a demanding user would notice.** Smaller deploys and no half-legacy global namespace (`src/ts/base-ui.ts` even exposes functions to "templates"); `tsc` build time drops; a newcomer reads one frontend, not two.

**Cost.** Low. Mostly deletions plus verifying the React app doesn't import anything from `src/ts/` (I checked: it doesn't).

### 3. Clean up the test suite to match the SPA reality
**What it is.** Rewrite the ~29 failing legacy-HTML tests as JSON-API tests (most equivalent coverage already exists in `test_api_routes.py`) or delete them; keep meaningful regressions (e.g. duplicate-ISBN handling, filter logic) as API-level tests rather than HTML-string assertions.

**Why a demanding user would notice.** A permanently red suite masks real regressions — nobody can tell new breakage from the 29 pre-existing failures.

**Cost.** Medium. Mechanical per test, but needs judgement about which behaviours lose coverage if only tested through React.

### 4. Docs honesty pass
**What it is.** Update `README`, `GEMINI.md`, and `AGENT_CONTEXT.md` to describe the React-only architecture, correct "React 18" → 19, and remove legacy instructions like `build:ts`.

**Why a demanding user (or agent) would notice.** AGENTS-style docs actively steer contributors and coding agents into editing the wrong layer today.

**Cost.** Low.

### 5. (Bonus) Move the SPA shell out of git
**What it is.** Stop committing `book_lamp/static/react/index.html` (and `assets/`) to the repo; build in CI/deploy instead. Vite writes the shell automatically.

**Why a demanding user would notice.** No more "the committed index.html disagrees with the source" drift; smaller diffs.

**Cost.** Low code, some deploy-pipeline care.

## Recommended build plan for idea #1 (start-cold instructions)

1. **`book_lamp/__init__.py`**: remove `template_folder="templates"` from the `Flask(...)` factory call.
2. **`book_lamp/routes/spa.py`**: remove `render_template` import; replace `_serve_spa`'s fallback branch with a plain error response, e.g. return a 503 `Response("SPA build missing: run 'npm run build'", mimetype="text/plain")` if `static/react/index.html` is absent.
3. **`git rm -r book_lamp/templates`** (15 files). Nothing else in `book_lamp/` references them (verified: only `spa.py` called `render_template`).
4. **Rebuild the shell**: `npm run build:react` so `static/react/index.html` is freshly generated.
5. **Tests**: delete or rewrite the 29 failing template-era tests. Rewrite, don't delete, the ones guarding real logic: duplicate-ISBN add (`test_manual_entry.py`), filter logic (`test_books.py` — API equivalents already exist in `test_api_routes.py`, so deletion is acceptable there), import success/failure paths (`test_libib_import.py`, already partially migrated to the `/books/import` JSON+redirect behaviour). Add a small `test_spa.py` asserting `/`, `/books`, `/author/x`, and a bogus path all return 200 with the React shell, and that a missing shell yields 503.
6. **Docs**: update `README`, `GEMINI.md`, `AGENT_CONTEXT.md` to the React-only reality (folds in idea #4).
7. **Verify**: `uv run pytest` fully green; `npm test`; `npm run build`; boot the app and curl `/`, `/books`, `/unauthorised`, `/definitely-missing` for 200 + React shell.

Rough scope: ~1,550 deleted lines (templates) + test churn + ~30 lines of Python edits. No user-visible behaviour change; the payoff is correct asset caching, a truthful test suite, and one frontend instead of three.
