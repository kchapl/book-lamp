/**
 * Reading Status helpers.
 *
 * A Reading Status is one of "In Progress", "Completed" or "Abandoned"
 * (see CONTEXT.md). The visual language renders each as a condition chip whose
 * styling is keyed off the status, so the class name is derived in one place.
 */

export type StatusClass = 'status-completed' | 'status-in-progress' | 'status-abandoned' | 'status-planned';

export function statusClass(status?: string): StatusClass {
    switch (status) {
        case 'Completed':
            return 'status-completed';
        case 'In Progress':
            return 'status-in-progress';
        case 'Abandoned':
            return 'status-abandoned';
        default:
            return 'status-planned';
    }
}

/** The three statuses that give a Book a Reading Status, in reading order. */
export const READING_STATUSES = ['In Progress', 'Completed', 'Abandoned'] as const;

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
