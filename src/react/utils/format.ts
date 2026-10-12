/**
 * Shared display formatting.
 *
 * `formatDate` was copied into the reading log and the dashboard; the two copies
 * agreed on the parse guard and the formatting options but not on the wording for
 * an empty date, so the wording is the caller's to pass.
 */

/**
 * Today as an ISO date (`YYYY-MM-DD`), in the reader's own timezone.
 *
 * Built from the local calendar parts rather than `toISOString`, which would
 * answer in UTC and so name tomorrow or yesterday for a reader either side of
 * midnight.
 */
export function todayIso(): string {
    const now = new Date();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    return `${now.getFullYear()}-${month}-${day}`;
}

/** Format an ISO date (`YYYY-MM-DD`) for display. */
export function formatDate(iso: string | null | undefined, empty = '—'): string {
    if (!iso) return empty;
    const date = new Date(`${iso}T00:00:00`);
    if (Number.isNaN(date.getTime())) return iso;
    return date.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
}
