import { showConfirm, submitPostRequest } from './base-ui.js';
import { setRecordEditMode, deleteRecord, updateRecordDateLabels } from './reading-records.js';

/**
 * Book Detail Page Logic
 */

export function setEditMode(isEdit: boolean): void {
    const header = document.getElementById('book-header');
    if (header) {
        header.setAttribute('data-edit-mode', isEdit.toString());
    }
}

export function deleteBook(bookId: string, deleteUrl: string): void {
    showConfirm(
        'Delete Book',
        'Permanently remove this book and all its reading history? This cannot be undone.',
        () => submitPostRequest(deleteUrl)
    );
}

export function toggleForm(bookId: string): void {
    const form = document.getElementById(`form-${bookId}`);
    if (form) {
        form.classList.toggle('hidden');
    }
}

export function updateDateLabels(bookId: string, status: string): void {
    const endGroup = document.getElementById(`end-date-group-${bookId}`);
    const endLabel = document.getElementById(`end-date-label-${bookId}`);
    const ratingGroup = document.getElementById(`rating-group-${bookId}`);

    if (!endGroup || !endLabel || !ratingGroup) return;

    const endInput = endGroup.querySelector('input');

    if (status === 'Completed') {
        endGroup.classList.remove('hidden');
        endLabel.textContent = 'Completion Date';
        if (endInput) (endInput as HTMLInputElement).required = true;
        ratingGroup.classList.remove('hidden');
    } else if (status === 'Abandoned') {
        endGroup.classList.remove('hidden');
        endLabel.textContent = 'Abandoned Date';
        if (endInput) (endInput as HTMLInputElement).required = true;
        ratingGroup.classList.add('hidden');
    } else {
        endGroup.classList.add('hidden');
        if (endInput) (endInput as HTMLInputElement).required = false;
        ratingGroup.classList.add('hidden');
    }
}

// Global exposing for template calls
if (typeof window !== 'undefined') {
    (window as any).setEditMode = setEditMode;
    (window as any).deleteBook = deleteBook;
    (window as any).toggleForm = toggleForm;
    (window as any).updateDateLabels = updateDateLabels;

    // Make sure these are also available on window if not explicitly imported in history.html
    (window as any).setRecordEditMode = setRecordEditMode;
    (window as any).deleteRecord = deleteRecord;
    (window as any).updateRecordDateLabels = updateRecordDateLabels;
}
