# Performance Engineering Examples

This file provides concrete examples of performance-aware code patterns within the Book Lamp project.

## 1. PostgreSQL: Batching vs. Loops

### ❌ BAD: One round trip per row

A query inside a loop pays connection and network overhead for every row.

```python
# N+1: one round trip per book
for book in books:
    conn.execute(
        "INSERT INTO books (isbn13, title) VALUES (%s, %s)",
        [book["isbn13"], book["title"]],
    )
```

### ✅ GOOD: Bulk write

Consolidate the whole batch into a single round trip.

```python
# One round trip for the entire batch
with pool.connection() as conn:
    conn.cursor().executemany(
        "INSERT INTO books (isbn13, title) VALUES (%s, %s)",
        [(b["isbn13"], b["title"]) for b in books],
    )
```

## 2. External API: Concurrent Lookups

### ❌ BAD: Sequential Requests

Waiting for each provider to finish before starting the next.

```python
def lookup_book(isbn):
    data = open_library_lookup(isbn)  # Wait 500ms
    if not data:
        data = google_books_lookup(isbn)  # Wait another 500ms
    return data
```

### ✅ GOOD: Concurrent Requests

Fetch from multiple sources at once and keep them off the request's critical
path. (The provider clients are synchronous today; prefer running bulk lookups
in the background job queue.)

```python
import asyncio

async def lookup_book(isbn):
    tasks = [
        open_library_lookup(isbn),
        google_books_lookup(isbn),
        itunes_lookup(isbn),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return merge_results(results)
```

## 3. Frontend: Optimised Images

### ❌ BAD: Unoptimised Image

Causes layout shifts and slows down first paint.

```jsx
<img src={book.thumbnailUrl} />
```

### ✅ GOOD: Optimised Image

Prevents layout shift (CLS) and improves loading (LCP).

```jsx
<img
    src={book.thumbnailUrl}
    alt={`Cover of ${book.title}`}
    width={120}
    height={180}
    loading="lazy"
    decoding="async"
/>
```

## 4. Frontend: Throttling & Debouncing

Ensure expensive operations such as search-as-you-type don't overwhelm the main
thread or the server.

```ts
// GOOD: debounced search
let timeout: ReturnType<typeof setTimeout>;
function onSearchInput(event: React.ChangeEvent<HTMLInputElement>) {
    clearTimeout(timeout);
    timeout = setTimeout(() => {
        performSearch(event.target.value);
    }, 300); // Wait for the user to stop typing
}
```
