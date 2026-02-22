---
name: performance-engineer
description: Guidelines and standards for ensuring high performance in the Book Lamp application, covering frontend web vitals, backend efficiency, and Google Sheets API optimization.
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
- **Critical CSS**: Ensure CSS is lean. Avoid large frameworks; use scoped Vanilla CSS.
- **JavaScript Efficiency**: 
  - Minimise the use of third-party scripts.
  - Implement lazy loading for non-critical components and images.
  - Ensure the main thread is not blocked by long-running tasks.
- **Resource Hints**: Use `dns-prefetch`, `preconnect`, and `preload` where applicable (e.g., for Google Fonts or API endpoints).

## 2. Backend & Data Performance

Since our "database" is Google Sheets, minimizing latency and API overhead is critical.

### Google Sheets API Optimization
- **Batching**: Never perform row-by-row updates in a loop. Use `batchUpdate` or `values.batchUpdate`.
- **Minimise Fetching**: Only request the ranges and fields required. Avoid fetching the whole sheet if only a few rows are needed.
- **Caching**: Implement caching mechanisms for frequently accessed but rarely changed data (e.g., Book lists) to avoid redundant API calls.
- **Connection Stability**: Handle rate limiting (429 errors) gracefully with exponential backoff.

### External API Integration (Book Lookups)
- **Concurrency**: Use `asyncio` or threading to fetch data from multiple providers (Open Library, Google Books) in parallel.
- **Timeouts**: Set strict timeouts for external requests to prevent them from hanging the application.
- **Stale-While-Revalidate**: Prefer serve-from-cache while updating data in the background.

## 3. Performance Verification

Performance is a requirement. All changes must be verified to ensure they meet the project's performance standards.

- **Efficiency Verification**: Use unit tests (refer to the **Testing** skill) to ensure backend operations use batching and avoid N+1 patterns.
- **Auditing**: Perform manual Lighthouse audits for new features. Ensure the performance score remains 90+ and payloads fit within initial windows.
- **Regressions**: Ensure no new feature or bug fix introduces performance regressions. If a bottleneck is suspected, use profiling tools (cProfile).

## 4. Architectural Patterns for Performance

- **Lazy Loading Strategy**: Use `loading="lazy"` for book covers.
- **Pagination/Virtualization**: For large book collections, implement server-side pagination or windowing to avoid DOM bloat.
- **State Management**: Keep the frontend state lean. Avoid unnecessary re-renders in templates.

## 5. Standard Tools & Measurement
- **Chrome DevTools**: Use the Network and Performance tabs for debugging.
- **Manual Auditing**: Regularly audit pages using Chrome DevTools Lighthouse to ensure performance scores remain 90+.
- **cProfile / line_profiler**: Use these for identifying bottlenecks in Python logic.

## 6. Performance "Gotchas" (Awareness)
- **Google Sheets Latency**: API calls to Google Sheets typically take 200ms-1s. Minimize these in the request-response cycle.
- **Template Bloat**: Large Jinja2 templates with deep loops can slow down server-side rendering.
- **Unoptimized Search**: Regex-based searches on large datasets in memory can be slow; prefer literal searches or optimized indexing if the dataset grows.
