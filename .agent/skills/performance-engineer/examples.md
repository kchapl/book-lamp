# Performance Engineering Examples

This file provides concrete examples of performance-aware code patterns within the Book Lamp project.

## 1. Google Sheets API: Batching vs. Loops

### ❌ BAD: Row-by-row updates in a loop
Performing a network request for every row is extremely slow due to the 200ms-1s latency per Google Sheets API call.

```python
# Inefficient loop
for book in books_to_update:
    sheet.values().update(
        spreadsheetId=ID,
        range=f"Books!A{book['row_idx']}",
        body={'values': [[book['title'], book['author']]]}
    ).execute()
```

### ✅ GOOD: Batch Update
Consolidate many updates into a single network request.

```python
# Efficient batching
requests = []
for book in books_to_update:
    requests.append({
        'updateCells': {
            'range': {'sheetId': 0, 'startRowIndex': book['row_idx']-1, 'endRowIndex': book['row_idx']},
            'fields': 'userEnteredValue',
            'rows': [{'values': [{'userEnteredValue': {'stringValue': book['title']}}, 
                                {'userEnteredValue': {'stringValue': book['author']}}]}]
        }
    })

service.spreadsheets().batchUpdate(
    spreadsheetId=ID,
    body={'requests': requests}
).execute()
```

## 2. External API: Concurrent Lookups

### ❌ BAD: Sequential Requests
Waiting for each provider to finish before starting the next.

```python
def lookup_book(isbn):
    data = open_library_lookup(isbn) # Wait 500ms
    if not data:
        data = google_books_lookup(isbn) # Wait 500ms
    return data
```

### ✅ GOOD: Concurrent Requests (with asyncio)
Fetch from multiple sources simultaneously.

```python
import asyncio

async def lookup_book(isbn):
    # Launch all lookups at once
    tasks = [
        open_library_lookup(isbn),
        google_books_lookup(isbn),
        itunes_lookup(isbn)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    # Process results as they come or pick the best one
    return merge_results(results)
```

## 3. Frontend: Resource Hints & Attributes

### ❌ BAD: Unoptimized Image
Causes layout shifts and slows down first paint.

```html
<img src="{{ book.thumbnail_url }}">
```

### ✅ GOOD: Optimized Image
Prevents layout shifts (CLS) and improves loading performance (LCP).

```html
<img src="{{ book.thumbnail_url }}" 
     alt="Cover of {{ book.title }}"
     width="120"
     height="180"
     loading="lazy"
     fetchpriority="high" 
     onerror="this.src='/static/img/placeholder.webp'">
```

## 4. Frontend: Throttling & Debouncing
Ensure expensive operations like search-as-you-type don't overwhelm the main thread or the server.

```javascript
// GOOD: Debounced search
let timeout;
function onSearchInput(e) {
    clearTimeout(timeout);
    timeout = setTimeout(() => {
        performSearch(e.target.value);
    }, 300); // Wait for user to stop typing
}
```
