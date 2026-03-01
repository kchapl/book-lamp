import { submitPostRequest } from './base-ui.js';

/**
 * Reading List Drag-and-Drop Reordering
 */

export function removeBook(bookId: string, deleteUrl: string): void {
    submitPostRequest(deleteUrl);
}

document.addEventListener('DOMContentLoaded', () => {
    const list = document.getElementById('reading-list-container');
    if (!list) return;

    const reorderUrl = list.getAttribute('data-reorder-url');
    if (!reorderUrl) return;

    let draggingItem: HTMLElement | null = null;

    list.addEventListener('dragstart', (e: DragEvent) => {
        const target = (e.target as HTMLElement).closest('.draggable-item') as HTMLElement;
        if (!target) return;
        draggingItem = target;
        setTimeout(() => target.classList.add('dragging'), 0);
    });

    list.addEventListener('dragend', (e: DragEvent) => {
        const target = (e.target as HTMLElement).closest('.draggable-item') as HTMLElement;
        if (!target) return;
        target.classList.remove('dragging');
        draggingItem = null;
        saveOrder(list, reorderUrl);
    });

    list.addEventListener('dragover', (e: DragEvent) => {
        e.preventDefault();
        const afterElement = getDragAfterElement(list, e.clientY);
        const currentDraggable = document.querySelector('.dragging');
        if (currentDraggable) {
            if (afterElement == null) {
                list.appendChild(currentDraggable);
            } else {
                list.insertBefore(currentDraggable, afterElement);
            }
        }
    });
});

function getDragAfterElement(container: HTMLElement, y: number): Element | null {
    const draggableElements = [...container.querySelectorAll('.draggable-item:not(.dragging)')];

    return draggableElements.reduce((closest, child) => {
        const box = child.getBoundingClientRect();
        const offset = y - box.top - box.height / 2;
        if (offset < 0 && offset > closest.offset) {
            return { offset: offset, element: child };
        } else {
            return closest;
        }
    }, { offset: Number.NEGATIVE_INFINITY } as { offset: number, element: Element | null }).element;
}

export function saveOrder(list: HTMLElement, reorderUrl: string): void {
    const items = [...list.querySelectorAll<HTMLElement>('.draggable-item')];
    const bookIds = items.map(item => parseInt(item.dataset.bookId || '0'));

    fetch(reorderUrl, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ book_ids: bookIds })
    });
}

// Expose for template
if (typeof window !== 'undefined') {
    (window as any).removeBook = removeBook;
}
