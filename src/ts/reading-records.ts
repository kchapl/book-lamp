import { showConfirm, submitPostRequest } from './base-ui.js';

/**
 * Shared Reading Record Logic
 */

export function setRecordEditMode(recordId: string, isEdit: boolean): void {
    const record = document.getElementById(`record-${recordId}`);
    if (record) {
        record.setAttribute('data-edit-mode', isEdit.toString());
    }
}

export function deleteRecord(recordId: string, deleteUrl: string): void {
    showConfirm(
        'Delete Record',
        'Remove this reading record from your history?',
        () => submitPostRequest(deleteUrl)
    );
}

export function updateRecordDateLabels(recordId: string, status: string): void {
    const endGroup = document.getElementById(`record-end-date-group-${recordId}`);
    const endLabel = document.getElementById(`record-end-date-label-${recordId}`);
    const ratingGroup = document.getElementById(`record-rating-group-${recordId}`);

    if (!endGroup || !endLabel) return; // ratingGroup can be null in history view

    const endInput = endGroup.querySelector('input');

    if (status === 'Completed') {
        endGroup.classList.remove('hidden');
        endLabel.textContent = 'Completion Date';
        if (endInput) endInput.required = true;
        if (ratingGroup) ratingGroup.classList.remove('hidden');
    } else if (status === 'Abandoned') {
        endGroup.classList.remove('hidden');
        endLabel.textContent = 'Abandoned Date';
        if (endInput) endInput.required = true;
        if (ratingGroup) ratingGroup.classList.add('hidden');
    } else {
        endGroup.classList.add('hidden');
        if (endInput) endInput.required = false;
        if (ratingGroup) ratingGroup.classList.add('hidden');
    }
}

// Global exposing for template calls
if (typeof window !== 'undefined') {
    (window as any).setRecordEditMode = setRecordEditMode;
    (window as any).deleteRecord = deleteRecord;
    (window as any).updateRecordDateLabels = updateRecordDateLabels;
}
