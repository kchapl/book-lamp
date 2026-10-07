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
import Icon from '../components/Icon';
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
            <button onClick={() => navigate(-1)} className="btn btn-text btn-back">
                <Icon name="arrow-left" size="sm" />
                Back
            </button>

            {isEditing ? (
                <div className="edit-form">
                    <h2>Edit exhibit</h2>
                    <label className="field">
                        <span className="field-label">Title</span>
                        <input
                            type="text"
                            value={editForm.title || ''}
                            onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
                        />
                    </label>
                    <label className="field">
                        <span className="field-label">Author</span>
                        <input
                            type="text"
                            value={editForm.author || ''}
                            onChange={(e) => setEditForm({ ...editForm, author: e.target.value })}
                        />
                    </label>
                    <label className="field">
                        <span className="field-label">ISBN</span>
                        <input
                            type="text"
                            value={editForm.isbn13 || ''}
                            onChange={(e) => setEditForm({ ...editForm, isbn13: e.target.value })}
                        />
                    </label>
                    <label className="field">
                        <span className="field-label">Publisher</span>
                        <input
                            type="text"
                            value={editForm.publisher || ''}
                            onChange={(e) => setEditForm({ ...editForm, publisher: e.target.value })}
                        />
                    </label>
                    <label className="field">
                        <span className="field-label">Year</span>
                        <input
                            type="number"
                            value={editForm.publication_year || ''}
                            onChange={(e) =>
                                setEditForm({
                                    ...editForm,
                                    publication_year: parseInt(e.target.value) || undefined,
                                })
                            }
                        />
                    </label>
                    <div className="form-actions">
                        <button onClick={handleSaveEdit} className="btn btn-primary">
                            Save
                        </button>
                        <button onClick={() => setIsEditing(false)} className="btn btn-text">
                            Cancel
                        </button>
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
                        <button onClick={() => setIsEditing(true)} className="btn btn-outline">
                            Edit
                        </button>
                        <button
                            onClick={handleToggleReadingList}
                            className={`btn ${book.is_planned ? 'btn-tonal' : 'btn-primary'}`}
                        >
                            <Icon name="bookmark" size="sm" />
                            {book.is_planned ? 'Remove from reading list' : 'Add to reading list'}
                        </button>
                        <button onClick={() => setShowDeleteConfirm(true)} className="btn btn-danger">
                            Delete
                        </button>
                    </div>

                    <section className="reading-records section">
                        <div className="row-between">
                            <h2>Reading history</h2>
                            <button onClick={() => setShowAddRecord(true)} className="btn btn-outline">
                                <Icon name="plus" size="sm" />
                                Add reading record
                            </button>
                        </div>

                        {showAddRecord && (
                            <div className="add-record-form">
                                <h3>Add reading record</h3>
                                <label className="field">
                                    <span className="field-label">Status</span>
                                    <select
                                        value={newRecord.status}
                                        onChange={(e) => setNewRecord({ ...newRecord, status: e.target.value })}
                                    >
                                        <option value="Completed">Completed</option>
                                        <option value="In Progress">In Progress</option>
                                        <option value="Abandoned">Abandoned</option>
                                    </select>
                                </label>
                                <label className="field">
                                    <span className="field-label">Rating (1–5)</span>
                                    <input
                                        type="number"
                                        min="1"
                                        max="5"
                                        value={newRecord.rating}
                                        onChange={(e) =>
                                            setNewRecord({ ...newRecord, rating: parseInt(e.target.value) || 0 })
                                        }
                                    />
                                </label>
                                <div className="form-actions">
                                    <button onClick={handleAddRecord} className="btn btn-primary">
                                        Add
                                    </button>
                                    <button onClick={() => setShowAddRecord(false)} className="btn btn-text">
                                        Cancel
                                    </button>
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

            {showDeleteConfirm && (
                <div className="modal-overlay">
                    <div className="modal" role="dialog" aria-modal="true" aria-labelledby="delete-title">
                        <h3 id="delete-title">Delete this book?</h3>
                        <p>
                            This removes “{book.title}” and its reading history. This cannot be undone.
                        </p>
                        <div className="modal-actions">
                            <button onClick={() => setShowDeleteConfirm(false)} className="btn btn-text">
                                Cancel
                            </button>
                            <button onClick={handleDelete} className="btn btn-danger">
                                Delete
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default BookDetailPage;
