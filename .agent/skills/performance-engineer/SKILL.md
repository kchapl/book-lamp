---
name: performance-engineer
description: Guidelines and standards for ensuring high performance in the Book Lamp application, covering frontend web vitals, PostgreSQL/backend efficiency and external API usage.
---

# Performance Engineer Skill

This skill outlines the performance standards, awareness, and practices required to maintain a fast, responsive, and efficient application. All new features and bug fixes MUST adhere to these standards.

## 1. Core Web Vitals (Frontend Standards)

We aim for "Good" ratings across all Google Core Web Vitals. Every page must be audited using Lighthouse or PageSpeed Insights.

| Metric | Target | Description |
| :--- | :--- | :--- |
| **LCP** (Largest Contentful Paint) | < 2.5s | Measures loading performance. |
| **INP** (Interaction to Next Paint) | < 200ms | Measures responsiveness. |
| **CLS** (Cumulative Layout Shift) | < 0.1 | Measures visual stability. |
| **Lighthouse Performance** | 90+ | Overall performance score. |

### Frontend Best Practices
- **Asset Optimization**: Use modern image formats (WebP). Ensure images have `width` and `height` attributes to prevent CLS.
- **Critical CSS**: Keep CSS lean; use the project's stylesheets (`book_lamp/static/css/` and `src/react/styles/`) rather than pulling in a heavy CSS framework.
- **JavaScript Efficiency**: 
  - Minimise the use of third-party scripts.
  - Implement lazy loading for non-critical components and images.
  - Ensure the main thread is not blocked by long-running tasks.
- **Resource Hints**: Use `dns-prefetch`, `preconnect`, and `preload` where applicable (e.g., for Google Fonts or API endpoints).

## 2. Backend & Data Performance

The primary datastore is PostgreSQL, reached through the `PostgresStorage`
adapter. Keep database work efficient and off the request's critical path.

### PostgreSQL Access
- **Avoid N+1**: Fetch related rows in one query (or a small fixed number) rather than looping over per-row queries.
- **Batch writes**: Use bulk operations for imports instead of row-by-row inserts.
- **Index and filter**: Rely on the indexes Alembic adds; push filtering and sorting into SQL where practical and select only the columns you need.
- **Pooling**: Reuse the connection pool; never open a connection per call.
- **Background work**: Run long jobs (imports, metadata backfills) through the PostgreSQL-backed job queue instead of blocking a request.

### External API Integration (Book Lookups)
- **Concurrency**: Use `asyncio` or threading to fetch data from multiple providers (Open Library, Google Books) in parallel.
- **Timeouts**: Set strict timeouts for external requests to prevent them from hanging the application.
- **Stale-While-Revalidate**: Prefer serve-from-cache while updating data in the background.

## 3. Performance Verification

Performance is a requirement. All changes must be verified to ensure they meet the project's performance standards.

- **Efficiency Verification**: Use unit tests (refer to the **Testing** skill) to ensure backend operations use batching and avoid N+1 patterns.
- **Auditing**: There is no automated Lighthouse check in CI, so audit manually for new features. Aim for a 90+ performance score and keep payloads within initial budgets.
- **Regressions**: Ensure no new feature or bug fix introduces performance regressions. If a bottleneck is suspected, use profiling tools (cProfile).

## 4. Architectural Patterns for Performance

- **Lazy Loading Strategy**: Use `loading="lazy"` for book covers.
- **Pagination/Virtualization**: For large book collections, implement server-side pagination or windowing to avoid DOM bloat.
- **State Management**: Keep the frontend state lean. Avoid unnecessary React re-renders.

## 5. Standard Tools & Measurement
- **Chrome DevTools**: Use the Network and Performance tabs for debugging.
- **Manual Auditing**: Regularly audit pages using Chrome DevTools Lighthouse to ensure performance scores remain 90+.
- **cProfile / line_profiler**: Use these for identifying bottlenecks in Python logic.

## 6. Performance "Gotchas" (Awareness)
- **External API latency**: Book lookups against Open Library / Google Books can take hundreds of milliseconds. Cache results and keep them off the request's critical path where possible.
- **Large client bundles**: Every route beyond `/` is code-split; keep new heavy dependencies out of the initial bundle and lazy-load them (for example the barcode scanner).
- **Unoptimised Search**: Regex-based searches over large in-memory datasets can be slow; prefer literal, indexed searches as the collection grows.
