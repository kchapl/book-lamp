import type { Book, ReadingListItem, Stats, Job, AuthorPage, PublisherPage, HistoryFilters, BooksFilters, ReadingRecord } from '../types';

const API_BASE = '/api';

// Cache for the CSRF token
let csrfToken: string | null = null;

/**
 * Invalidate the cached CSRF token.
 * Call this on logout, session expiry, or session regeneration.
 */
export function invalidateCSRFToken(): void {
    csrfToken = null;
}

/**
 * Fetch the CSRF token from the server.
 * If the token was invalidated, refetches from the server for the current session.
 */
async function fetchCSRFToken(): Promise<string> {
    if (csrfToken) return csrfToken;
    const response = await fetch(`${API_BASE}/csrf-token`);
    if (!response.ok) {
        throw new Error('Failed to fetch CSRF token');
    }
    const data = await response.json();
    csrfToken = data.csrf_token;
    return data.csrf_token;
}

/**
 * Clear session and invalidate CSRF token.
 * Call this on logout.
 */
export async function logout(): Promise<void> {
    invalidateCSRFToken();
    const response = await fetch('/logout', { method: 'GET' });
    if (response.ok) {
        window.location.href = '/';
    }
}

/**
 * Refresh CSRF token for the new session after login.
 * Call this after successful authentication.
 */
export async function refreshCSRFToken(): Promise<string> {
    invalidateCSRFToken();
    return fetchCSRFToken();
}

async function fetchJSON<T>(url: string, options?: RequestInit, retryOnCSRF?: boolean): Promise<T> {
    // For POST/PUT/PATCH/DELETE requests, include CSRF token
    const method = options?.method?.toUpperCase() || 'GET';
    const headers = new Headers(options?.headers);
    headers.set('Content-Type', 'application/json');

    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
        const token = await fetchCSRFToken();
        headers.set('X-CSRF-Token', token);
    }

    const response = await fetch(url, {
        ...options,
        headers,
    });

    if (!response.ok) {
        if (response.status === 401) {
            invalidateCSRFToken();
            window.location.href = '/unauthorised';
            throw new Error('Unauthorized');
        }
        // Retry once on CSRF 403 if not already retried
        if (response.status === 403 && retryOnCSRF !== false) {
            const csrfError = await response.json().catch(() => ({}));
            if (csrfError.error === 'CSRF token validation failed') {
                invalidateCSRFToken();
                return fetchJSON<T>(url, options, false);
            }
        }
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
}

// Jobs API
export async function getJobStatus(jobId: string): Promise<Job> {
    return fetchJSON<Job>(`${API_BASE}/jobs/${jobId}`);
}

// Settings API
export async function updateSettings(settings: Record<string, string>): Promise<void> {
    await fetchJSON(`${API_BASE}/settings`, {
        method: 'POST',
        body: JSON.stringify(settings),
    });
}

// Auth API
export async function authenticateWithGoogle(credential: string): Promise<{ success: boolean; redirect?: string }> {
    return fetchJSON(`${API_BASE}/auth/google`, {
        method: 'POST',
        body: JSON.stringify({ credential }),
    });
}

// Sync diagnostics
export async function getSyncDiagnostics(): Promise<{ status: string; message: string }> {
    return fetchJSON(`${API_BASE}/sync/diagnostics`);
}

// Recommendations
export async function getRecommendations(): Promise<{ recommendations: Book[] }> {
    return fetchJSON(`${API_BASE}/recommendations`);
}

// Books API
export async function getBooks(filters?: Partial<BooksFilters>): Promise<{
    books: Book[];
    sort: string;
    sort_options: Record<string, string>;
    filters: BooksFilters;
    categories: string[];
}> {
    const params = new URLSearchParams();
    if (filters) {
        Object.entries(filters).forEach(([key, value]) => {
            if (value) params.set(key, value);
        });
    }
    const query = params.toString();
    return fetchJSON(`${API_BASE}/books${query ? `?${query}` : ''}`);
}

export async function getBookDetail(bookId: number): Promise<Book> {
    return fetchJSON<Book>(`${API_BASE}/books/${bookId}`);
}

export async function createBook(book: Partial<Book>): Promise<Book> {
    return fetchJSON<Book>(`${API_BASE}/books`, {
        method: 'POST',
        body: JSON.stringify(book),
    });
}

export async function updateBook(bookId: number, book: Partial<Book>): Promise<void> {
    await fetchJSON(`${API_BASE}/books/${bookId}/edit`, {
        method: 'POST',
        body: JSON.stringify(book),
    });
}

export async function deleteBook(bookId: number): Promise<void> {
    await fetchJSON(`${API_BASE}/books/${bookId}/delete`, {
        method: 'POST',
    });
}

export async function searchBooks(query: string): Promise<{
    books: Book[];
    search_query: string;
}> {
    const params = new URLSearchParams({ q: query });
    return fetchJSON(`${API_BASE}/books/search?${params}`);
}

// Reading Records API
export async function createReadingRecord(bookId: number, record: Partial<ReadingRecord>): Promise<ReadingRecord> {
    return fetchJSON<ReadingRecord>(`${API_BASE}/books/${bookId}/reading-records`, {
        method: 'POST',
        body: JSON.stringify(record),
    });
}

export async function updateReadingRecord(recordId: number, record: Partial<ReadingRecord>): Promise<void> {
    await fetchJSON(`${API_BASE}/reading-records/${recordId}/edit`, {
        method: 'POST',
        body: JSON.stringify(record),
    });
}

export async function deleteReadingRecord(recordId: number): Promise<void> {
    await fetchJSON(`${API_BASE}/reading-records/${recordId}/delete`, {
        method: 'POST',
    });
}

// Reading List API
export async function getReadingList(): Promise<{ books: ReadingListItem[] }> {
    return fetchJSON<{ books: ReadingListItem[] }>(`${API_BASE}/reading-list`);
}

export async function reorderReadingList(bookIds: number[]): Promise<void> {
    await fetchJSON(`${API_BASE}/reading-list/reorder`, {
        method: 'POST',
        body: JSON.stringify({ book_ids: bookIds }),
    });
}

export async function removeFromReadingList(bookId: number): Promise<void> {
    await fetchJSON(`${API_BASE}/reading-list/remove/${bookId}`, {
        method: 'POST',
    });
}

export async function startReading(bookId: number): Promise<void> {
    await fetchJSON(`${API_BASE}/books/${bookId}/start-reading`, {
        method: 'POST',
    });
}

export async function addToReadingList(bookId: number): Promise<void> {
    await fetchJSON(`${API_BASE}/books/${bookId}/add-to-reading-list`, {
        method: 'POST',
    });
}

// History API
export async function getHistory(filters?: Partial<HistoryFilters>): Promise<{
    history: ReadingRecord[];
    statuses: string[];
    filters: HistoryFilters;
}> {
    const params = new URLSearchParams();
    if (filters) {
        Object.entries(filters).forEach(([key, value]) => {
            if (value !== undefined && value !== '') params.set(key, String(value));
        });
    }
    const query = params.toString();
    return fetchJSON(`${API_BASE}/history${query ? `?${query}` : ''}`);
}

// Stats API
export async function getStats(): Promise<Stats> {
    return fetchJSON<Stats>(`${API_BASE}/stats`);
}

// Author/Publisher pages
export async function getAuthorPage(authorSlug: string): Promise<AuthorPage> {
    return fetchJSON<AuthorPage>(`${API_BASE}/author/${authorSlug}`);
}

export async function getPublisherPage(publisherSlug: string): Promise<PublisherPage> {
    return fetchJSON<PublisherPage>(`${API_BASE}/publisher/${publisherSlug}`);
}

// ISBN lookup
export async function lookupISBN(isbn: string): Promise<Book | null> {
    const params = new URLSearchParams({ isbn });
    return fetchJSON(`${API_BASE}/books/lookup?${params}`);
}

// Fetch covers
export async function fetchCovers(bookIds: number[]): Promise<void> {
    await fetchJSON(`${API_BASE}/books/fetch-covers`, {
        method: 'POST',
        body: JSON.stringify({ book_ids: bookIds }),
    });
}