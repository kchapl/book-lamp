import React, { useState } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import {
    getBookDetail,
    updateBook,
    deleteBook,
    createReading,
    updateReading,
    deleteReading,
    addToReadingList,
    removeFromReadingList,
} from '../services/api';
import { Button, Dialog, IconButton, Select, SelectOption, TextField } from '../ui';
import { useResource } from '../hooks/useResource';
import { endsReading, statusClass } from '../utils/status';
import { todayIso } from '../utils/format';
import { draftWithStatus, readingDraft, readingPayload, type ReadingDraft } from '../utils/reading';
import { seriesPath } from '../utils/series';
import type { Book, Reading } from '../types';

interface ReadingFormProps {
    /** Field ids are suffixed with this, so the add and edit forms coexist. */
    idPrefix: string;
    draft: ReadingDraft;
    onChange: (draft: ReadingDraft) => void;
    onSubmit: () => void;
    onCancel: () => void;
    submitLabel: string;
    error: string | null;
    heading: string;
}

/**
 * The Reading fields, shared by the add and edit forms.
 *
 * Both forms collect the same four values and enforce the same rule — a Reading
 * that has ended must carry an end date (ADR-0003) — so the fields live in one
 * place rather than being spelled out twice.
 */
const ReadingForm: React.FC<ReadingFormProps> = ({
    idPrefix,
    draft,
    onChange,
    onSubmit,
    onCancel,
    submitLabel,
    error,
    heading,
}) => {
    const withStatus = (status: string): ReadingDraft =>
        draftWithStatus(draft, status, todayIso());

    return (
        <div className="reading-form">
            <h3>{heading}</h3>
            <Select
                id={`${idPrefix}-status`}
                label="Status"
                value={draft.status}
                onValueChange={(value) => onChange(withStatus(value))}
            >
                <SelectOption value="Completed">Completed</SelectOption>
                <SelectOption value="In Progress">In Progress</SelectOption>
                <SelectOption value="Abandoned">Abandoned</SelectOption>
            </Select>
            <TextField
                id={`${idPrefix}-start-date`}
                label="Started"
                type="date"
                value={draft.start_date}
                onValueChange={(value) => onChange({ ...draft, start_date: value })}
            />
            {endsReading(draft.status) && (
                <TextField
                    id={`${idPrefix}-end-date`}
                    label="Ended"
                    type="date"
                    value={draft.end_date}
                    onValueChange={(value) => onChange({ ...draft, end_date: value })}
                />
            )}
            <TextField
                id={`${idPrefix}-rating`}
                label="Rating (1–5)"
                type="number"
                min="1"
                max="5"
                value={String(draft.rating)}
                onValueChange={(value) => onChange({ ...draft, rating: parseInt(value) || 0 })}
            />
            {error && <p className="error-message">{error}</p>}
            <div className="form-actions">
                <Button onClick={onSubmit}>{submitLabel}</Button>
                <Button variant="text" onClick={onCancel}>
                    Cancel
                </Button>
            </div>
        </div>
    );
};

const BookDetailPage: React.FC = () => {
    const { bookId } = useParams<{ bookId: string }>();
    const navigate = useNavigate();
    const [isEditing, setIsEditing] = useState(false);
    const [editForm, setEditForm] = useState<Partial<Book>>({});
    const [showAddRecord, setShowAddRecord] = useState(false);
    const [addRecordError, setAddRecordError] = useState<string | null>(null);
    const [newRecord, setNewRecord] = useState<ReadingDraft>({
        status: 'Completed',
        rating: 5,
        start_date: todayIso(),
        end_date: todayIso(),
    });
    // The Reading being edited, if any. One at a time: a Book's history is a
    // short list, and two open forms would need two drafts to keep straight.
    const [editingRecord, setEditingRecord] = useState<Reading | null>(null);
    const [editRecord, setEditRecord] = useState<ReadingDraft | null>(null);
    const [editRecordError, setEditRecordError] = useState<string | null>(null);
    const [recordToDelete, setRecordToDelete] = useState<Reading | null>(null);
    const [deleteRecordError, setDeleteRecordError] = useState<string | null>(null);
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

    const loadBook = async () => {
        if (!bookId) throw new Error('No book id in the route');
        return getBookDetail(Number(bookId));
    };

    const { data: book, loading, error, reload } = useResource(loadBook, [bookId], {
        errorMessage: 'Failed to load book',
    });

    const handleSaveEdit = async () => {
        if (!bookId) return;

        // The author field holds the display string, which a person cannot
        // un-join. So while it is untouched, send the names it was built from;
        // once it is edited, it is new text and the server reads it.
        const payload: Partial<Book> = { ...editForm };
        if ((editForm.author || '') !== (book?.author || '')) {
            delete payload.authors;
        }

        try {
            await updateBook(Number(bookId), payload);
            setIsEditing(false);
            reload();
        } catch (err) {
            console.error('Failed to update book:', err);
        }
    };

    const handleDelete = async () => {
        if (!bookId) return;
        try {
            await deleteBook(Number(bookId));
            navigate('/books');
        } catch (err) {
            console.error('Failed to delete book:', err);
        }
    };

    const handleAddRecord = async () => {
        if (!bookId) return;
        setAddRecordError(null);
        try {
            await createReading(Number(bookId), readingPayload(newRecord));
            setShowAddRecord(false);
            reload();
        } catch (err) {
            setAddRecordError(err instanceof Error ? err.message : 'Failed to add reading');
        }
    };

    /** Open the edit form on a Reading, pre-filled from it. */
    const openEditRecord = (record: Reading) => {
        setEditRecordError(null);
        setEditRecord(readingDraft(record));
        setEditingRecord(record);
    };

    const handleUpdateRecord = async () => {
        if (!editingRecord || !editRecord) return;
        setEditRecordError(null);
        try {
            await updateReading(editingRecord.id, readingPayload(editRecord));
            setEditingRecord(null);
            setEditRecord(null);
            reload();
        } catch (err) {
            setEditRecordError(err instanceof Error ? err.message : 'Failed to update reading');
        }
    };

    const handleDeleteRecord = async () => {
        if (!recordToDelete) return;
        setDeleteRecordError(null);
        try {
            await deleteReading(recordToDelete.id);
            setRecordToDelete(null);
            reload();
        } catch (err) {
            setDeleteRecordError(err instanceof Error ? err.message : 'Failed to delete reading');
        }
    };

    const handleToggleReadingList = async () => {
        if (!bookId || !book) return;
        try {
            if (book.is_planned) {
                await removeFromReadingList(Number(bookId));
            } else {
                await addToReadingList(Number(bookId));
            }
            reload();
        } catch (err) {
            console.error('Failed to toggle reading list:', err);
        }
    };

    if (loading) {
        return <div className="loading">Loading…</div>;
    }

    if (error || !book) {
        return <div className="page"><p className="error-message">{error || 'Book not found'}</p></div>;
    }

    const cover = book.cover_url || book.thumbnail_url;
    const currentStatus = book.latest_status ?? book.readings?.[0]?.status;

    return (
        <div className="book-detail-page page">
            <Button variant="text" icon="arrow-left" className="btn-back" onClick={() => navigate(-1)}>
                Back
            </Button>

            {isEditing ? (
                <div className="edit-form">
                    <h2>Edit book</h2>
                    <TextField
                        id="edit-title"
                        label="Title"
                        value={editForm.title || ''}
                        onValueChange={(value) => setEditForm({ ...editForm, title: value })}
                    />
                    <TextField
                        id="edit-author"
                        label="Author"
                        value={editForm.author || ''}
                        onValueChange={(value) => setEditForm({ ...editForm, author: value })}
                    />
                    <TextField
                        id="edit-isbn"
                        label="ISBN"
                        value={editForm.isbn13 || ''}
                        onValueChange={(value) => setEditForm({ ...editForm, isbn13: value })}
                    />
                    <TextField
                        id="edit-publisher"
                        label="Publisher"
                        value={editForm.publisher || ''}
                        onValueChange={(value) => setEditForm({ ...editForm, publisher: value })}
                    />
                    <TextField
                        id="edit-year"
                        label="Year"
                        type="number"
                        value={editForm.publication_year ? String(editForm.publication_year) : ''}
                        onValueChange={(value) =>
                            setEditForm({
                                ...editForm,
                                publication_year: parseInt(value) || undefined,
                            })
                        }
                    />
                    <div className="form-actions">
                        <Button onClick={handleSaveEdit}>Save</Button>
                        <Button variant="text" onClick={() => setIsEditing(false)}>
                            Cancel
                        </Button>
                    </div>
                </div>
            ) : (
                <>
                    <section className="book-header">
                        {cover ? (
                            <img src={cover} alt="" className="book-cover-large" />
                        ) : (
                            <div className="book-placeholder-large" aria-hidden="true">
                                📖
                            </div>
                        )}
                        <div className="book-meta">
                            {currentStatus && (
                                <span className={`status-badge ${statusClass(currentStatus)}`}>
                                    {currentStatus}
                                </span>
                            )}
                            <h1>{book.title}</h1>
                            <p className="author">by {book.author || 'Unknown Author'}</p>

                            <dl className="placard">
                                {book.publisher && (
                                    <div className="placard-row">
                                        <dt>Publisher</dt>
                                        <dd>{book.publisher}</dd>
                                    </div>
                                )}
                                {book.publication_year && (
                                    <div className="placard-row">
                                        <dt>Published</dt>
                                        <dd className="numeric">{book.publication_year}</dd>
                                    </div>
                                )}
                                {book.isbn13 && (
                                    <div className="placard-row">
                                        <dt>ISBN</dt>
                                        <dd className="numeric">{book.isbn13}</dd>
                                    </div>
                                )}
                                {book.bisac_category && (
                                    <div className="placard-row">
                                        <dt>Subject</dt>
                                        <dd>{book.bisac_category}</dd>
                                    </div>
                                )}
                                {book.series && (
                                    <div className="placard-row">
                                        <dt>Series</dt>
                                        <dd>
                                            <Link to={seriesPath(book.series)}>{book.series}</Link>
                                        </dd>
                                    </div>
                                )}
                            </dl>

                            {book.description && (
                                <p className="description">{book.description}</p>
                            )}
                        </div>
                    </section>

                    <div className="book-actions">
                        <Button
                            variant="outlined"
                            onClick={() => {
                                setEditForm(book);
                                setIsEditing(true);
                            }}
                        >
                            Edit
                        </Button>
                        <Button
                            variant={book.is_planned ? 'tonal' : 'filled'}
                            icon="bookmark"
                            onClick={handleToggleReadingList}
                        >
                            {book.is_planned ? 'Remove from reading list' : 'Add to reading list'}
                        </Button>
                        <Button
                            variant="outlined"
                            className="btn-danger"
                            onClick={() => setShowDeleteConfirm(true)}
                        >
                            Delete
                        </Button>
                    </div>

                    <section className="readings section">
                        <div className="row-between">
                            <h2>Reading history</h2>
                            <Button
                                variant="outlined"
                                icon="plus"
                                onClick={() => {
                                    setAddRecordError(null);
                                    setShowAddRecord(true);
                                }}
                            >
                                Add reading
                            </Button>
                        </div>

                        {showAddRecord && (
                            <ReadingForm
                                idPrefix="record"
                                heading="Add reading"
                                submitLabel="Add"
                                draft={newRecord}
                                onChange={setNewRecord}
                                onSubmit={handleAddRecord}
                                onCancel={() => setShowAddRecord(false)}
                                error={addRecordError}
                            />
                        )}

                        {book.readings && book.readings.length > 0 ? (
                            <div className="records-list">
                                {book.readings.map((record) => (
                                    <div key={record.id} className="record-item">
                                        <div className="record-main">
                                            <span className={`status-badge ${statusClass(record.status)}`}>
                                                {record.status}
                                            </span>
                                            {record.rating ? (
                                                <span className="rating-stars" aria-label={`${record.rating} out of 5`}>
                                                    {'★'.repeat(record.rating)}
                                                    {'☆'.repeat(5 - record.rating)}
                                                </span>
                                            ) : null}
                                            <span className="dates">
                                                {record.start_date} → {record.end_date || 'Present'}
                                            </span>
                                        </div>
                                        <div className="record-actions">
                                            <IconButton
                                                icon="edit"
                                                aria-label={`Edit reading of ${record.start_date}`}
                                                onClick={() => openEditRecord(record)}
                                            />
                                            <IconButton
                                                icon="delete"
                                                aria-label={`Delete reading of ${record.start_date}`}
                                                onClick={() => {
                                                    setDeleteRecordError(null);
                                                    setRecordToDelete(record);
                                                }}
                                            />
                                        </div>
                                        {record.notes && <p className="notes">{record.notes}</p>}
                                        {editingRecord?.id === record.id && editRecord && (
                                            <ReadingForm
                                                idPrefix="edit-record"
                                                heading="Edit reading"
                                                submitLabel="Save"
                                                draft={editRecord}
                                                onChange={setEditRecord}
                                                onSubmit={handleUpdateRecord}
                                                onCancel={() => {
                                                    setEditingRecord(null);
                                                    setEditRecord(null);
                                                }}
                                                error={editRecordError}
                                            />
                                        )}
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="empty-state">
                                <h2>No readings yet</h2>
                                <p>Record the first attempt at this book to begin its history.</p>
                            </div>
                        )}
                    </section>
                </>
            )}

            <Dialog
                open={showDeleteConfirm}
                onClose={() => setShowDeleteConfirm(false)}
                headline="Delete this book?"
                actions={
                    <>
                        <Button variant="text" onClick={() => setShowDeleteConfirm(false)}>
                            Cancel
                        </Button>
                        <Button variant="filled" className="btn-danger" onClick={handleDelete}>
                            Delete
                        </Button>
                    </>
                }
            >
                <p>
                    This removes “{book.title}” and its reading history. This cannot be undone.
                </p>
            </Dialog>

            <Dialog
                open={recordToDelete !== null}
                onClose={() => {
                    setRecordToDelete(null);
                    setDeleteRecordError(null);
                }}
                headline="Delete this reading?"
                actions={
                    <>
                        <Button
                            variant="text"
                            onClick={() => {
                                setRecordToDelete(null);
                                setDeleteRecordError(null);
                            }}
                        >
                            Cancel
                        </Button>
                        <Button variant="filled" className="btn-danger" onClick={handleDeleteRecord}>
                            Delete
                        </Button>
                    </>
                }
            >
                <p>
                    This removes the reading that started {recordToDelete?.start_date} from the
                    history. This cannot be undone.
                </p>
                {deleteRecordError && <p className="error-message">{deleteRecordError}</p>}
            </Dialog>
        </div>
    );
};

export default BookDetailPage;
