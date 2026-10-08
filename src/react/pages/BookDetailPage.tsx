import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
    getBookDetail,
    updateBook,
    deleteBook,
    createReadingRecord,
    addToReadingList,
    removeFromReadingList,
} from '../services/api';
import { Button, Dialog, Select, SelectOption, TextField } from '../ui';
import { statusClass } from '../utils/status';
import type { Book } from '../types';

const BookDetailPage: React.FC = () => {
    const { bookId } = useParams<{ bookId: string }>();
    const navigate = useNavigate();
    const [book, setBook] = useState<Book | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [isEditing, setIsEditing] = useState(false);
    const [editForm, setEditForm] = useState<Partial<Book>>({});
    const [showAddRecord, setShowAddRecord] = useState(false);
    const [newRecord, setNewRecord] = useState({ status: 'Completed', rating: 5 });
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

    useEffect(() => {
        if (bookId) {
            loadBook(parseInt(bookId));
        }
    }, [bookId]);

    const loadBook = async (id: number) => {
        setLoading(true);
        setError(null);
        try {
            const data = await getBookDetail(id);
            setBook(data);
            setEditForm(data);
        } catch (err) {
            console.error('Failed to load book:', err);
            setError('Failed to load book');
        } finally {
            setLoading(false);
        }
    };

    const handleSaveEdit = async () => {
        if (!bookId) return;
        try {
            await updateBook(parseInt(bookId), editForm);
            setIsEditing(false);
            loadBook(parseInt(bookId));
        } catch (err) {
            console.error('Failed to update book:', err);
        }
    };

    const handleDelete = async () => {
        if (!bookId) return;
        try {
            await deleteBook(parseInt(bookId));
            navigate('/books');
        } catch (err) {
            console.error('Failed to delete book:', err);
        }
    };

    const handleAddRecord = async () => {
        if (!bookId) return;
        try {
            await createReadingRecord(parseInt(bookId), newRecord);
            setShowAddRecord(false);
            loadBook(parseInt(bookId));
        } catch (err) {
            console.error('Failed to add record:', err);
        }
    };

    const handleToggleReadingList = async () => {
        if (!bookId || !book) return;
        try {
            if (book.is_planned) {
                await removeFromReadingList(parseInt(bookId));
            } else {
                await addToReadingList(parseInt(bookId));
            }
            loadBook(parseInt(bookId));
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
    const currentStatus = book.latest_status ?? book.reading_records?.[0]?.status;

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
                                        <dd>{book.series}</dd>
                                    </div>
                                )}
                            </dl>

                            {book.description && (
                                <p className="description">{book.description}</p>
                            )}
                        </div>
                    </section>

                    <div className="book-actions">
                        <Button variant="outlined" onClick={() => setIsEditing(true)}>
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

                    <section className="reading-records section">
                        <div className="row-between">
                            <h2>Reading history</h2>
                            <Button variant="outlined" icon="plus" onClick={() => setShowAddRecord(true)}>
                                Add reading record
                            </Button>
                        </div>

                        {showAddRecord && (
                            <div className="add-record-form">
                                <h3>Add reading record</h3>
                                <Select
                                    id="record-status"
                                    label="Status"
                                    value={newRecord.status}
                                    onValueChange={(value) => setNewRecord({ ...newRecord, status: value })}
                                >
                                    <SelectOption value="Completed">Completed</SelectOption>
                                    <SelectOption value="In Progress">In Progress</SelectOption>
                                    <SelectOption value="Abandoned">Abandoned</SelectOption>
                                </Select>
                                <TextField
                                    id="record-rating"
                                    label="Rating (1–5)"
                                    type="number"
                                    min="1"
                                    max="5"
                                    value={String(newRecord.rating)}
                                    onValueChange={(value) =>
                                        setNewRecord({ ...newRecord, rating: parseInt(value) || 0 })
                                    }
                                />
                                <div className="form-actions">
                                    <Button onClick={handleAddRecord}>Add</Button>
                                    <Button variant="text" onClick={() => setShowAddRecord(false)}>
                                        Cancel
                                    </Button>
                                </div>
                            </div>
                        )}

                        {book.reading_records && book.reading_records.length > 0 ? (
                            <div className="records-list">
                                {book.reading_records.map((record) => (
                                    <div key={record.id} className="record-item">
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
                                        {record.notes && <p className="notes">{record.notes}</p>}
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="empty-state">
                                <h2>No reading records yet</h2>
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
        </div>
    );
};

export default BookDetailPage;
