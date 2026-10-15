/**
 * Reading Status helpers.
 *
 * A Reading Status is one of "In Progress", "Completed" or "Abandoned"
 * (see CONTEXT.md). The visual language renders each as a condition chip whose
 * styling is keyed off the status, so the class name is derived in one place.
 *
 * Two screens need that same status in another shape, and they are derived here
 * too rather than spelled out again: the dashboard's tiles and meters take an
 * `is-*` accent class instead of `status-*`, and a Book waiting on the reading
 * list takes the planned role without carrying a status at all.
 */

export type StatusClass = 'status-completed' | 'status-in-progress' | 'status-abandoned' | 'status-planned';

/**
 * The accent spelling, for the dashboard's status tiles and meter fills
 * (`static/css/pages.css`: `.status-card.is-completed`, `.meter-fill.is-planned`).
 */
export type StatusAccentClass = 'is-completed' | 'is-in-progress' | 'is-abandoned' | 'is-planned';

/** The status a Reading carries while it is under way. */
export const IN_PROGRESS_STATUS = 'In Progress';

/** The three statuses that give a Book a Reading Status, in reading order. */
export const READING_STATUSES = [IN_PROGRESS_STATUS, 'Completed', 'Abandoned'] as const;

/**
 * The chip for a Book that is waiting on the reading list.
 *
 * Not a Reading Status — a Book on the list has no Reading — but the visual
 * language gives the planned role to it.
 */
export const READING_LIST_CLASS: StatusClass = 'status-planned';

export function statusClass(status?: string): StatusClass {
    switch (status) {
        case 'Completed':
            return 'status-completed';
        case IN_PROGRESS_STATUS:
            return 'status-in-progress';
        case 'Abandoned':
            return 'status-abandoned';
        default:
            // A Book with no Reading is on the reading list, which is the planned
            // role; an unrecognised status falls back to it as well.
            return READING_LIST_CLASS;
    }
}

/**
 * The same status in the accent spelling, for the dashboard's tiles and meters.
 *
 * Derived from `statusClass` rather than written out again, so a status that
 * changes there cannot leave the dashboard behind.
 */
export function statusAccentClass(status?: string): StatusAccentClass {
    return statusClass(status).replace('status-', 'is-') as StatusAccentClass;
}

/**
 * The statuses that end a Reading, so a Reading carrying one knows its end date.
 *
 * Mirrors `ENDING_STATUSES` in `book_lamp/utils/readings.py`, which is where the
 * rule is enforced for every writer.
 */
export const ENDING_STATUSES = ['Completed', 'Abandoned'] as const;

/** Whether a Reading carrying this status has ended. */
export function endsReading(status: string): boolean {
    return (ENDING_STATUSES as readonly string[]).includes(status);
}
