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
