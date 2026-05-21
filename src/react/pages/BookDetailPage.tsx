import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getBookDetail, updateBook, deleteBook, createReadingRecord, updateReadingRecord, deleteReadingRecord, addToReadingList, removeFromReadingList } from '../services/api';
import type { Book, ReadingRecord } from '../types';

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
        return <div className="loading">Loading...</div>;
    }

    if (error || !book) {
        return <div className="error-message">{error || 'Book not found'}</div>;
    }

    return (
        <div className="book-detail-page">
            <button onClick={() => navigate(-1)} className="btn btn-back">← Back</button>

            {isEditing ? (
                <div className="edit-form">
                    <h2>Edit Book</h2>
                    <label>
                        Title:
                        <input
                            type="text"
                            value={editForm.title || ''}
                            onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
                        />
                    </label>
                    <label>
                        Author:
                        <input
                            type="text"
                            value={editForm.author || ''}
                            onChange={(e) => setEditForm({ ...editForm, author: e.target.value })}
                        />
                    </label>
                    <label>
                        ISBN:
                        <input
                            type="text"
                            value={editForm.isbn13 || ''}
                            onChange={(e) => setEditForm({ ...editForm, isbn13: e.target.value })}
                        />
                    </label>
                    <label>
                        Publisher:
                        <input
                            type="text"
                            value={editForm.publisher || ''}
                            onChange={(e) => setEditForm({ ...editForm, publisher: e.target.value })}
                        />
                    </label>
                    <label>
                        Year:
                        <input
                            type="number"
                            value={editForm.publication_year || ''}
                            onChange={(e) => setEditForm({ ...editForm, publication_year: parseInt(e.target.value) || undefined })}
                        />
                    </label>
                    <div className="form-actions">
                        <button onClick={handleSaveEdit} className="btn btn-primary">Save</button>
                        <button onClick={() => setIsEditing(false)} className="btn">Cancel</button>
                    </div>
                </div>
            ) : (
                <>
                    <div className="book-header">
                        {book.cover_url ? (
                            <img src={book.cover_url} alt={book.title} className="book-cover-large" />
                        ) : (
                            <div className="book-placeholder-large">📖</div>
                        )}
                        <div className="book-meta">
                            <h1>{book.title}</h1>
                            <p className="author">by {book.author || 'Unknown Author'}</p>
                            {book.publisher && <p className="publisher">{book.publisher}</p>}
                            {book.publication_year && <p className="year">{book.publication_year}</p>}
                            {book.isbn13 && <p className="isbn">ISBN: {book.isbn13}</p>}
                            {book.bisac_category && <p className="category">{book.bisac_category}</p>}
                            {book.description && <p className="description">{book.description}</p>}
                        </div>
                    </div>

                    <div className="book-actions">
                        <button onClick={() => setIsEditing(true)} className="btn">Edit Book</button>
                        <button
                            onClick={handleToggleReadingList}
                            className={`btn ${book.is_planned ? 'btn-secondary' : 'btn-primary'}`}
                        >
                            {book.is_planned ? 'Remove from Reading List' : 'Add to Reading List'}
                        </button>
                        <button onClick={() => setShowDeleteConfirm(true)} className="btn btn-danger">Delete Book</button>
                    </div>

                    <section className="reading-records">
                        <h2>Reading History</h2>
                        <button onClick={() => setShowAddRecord(true)} className="btn btn-primary">
                            + Add Reading Record
                        </button>

                        {showAddRecord && (
                            <div className="add-record-form">
                                <h3>Add Reading Record</h3>
                                <label>
                                    Status:
                                    <select
                                        value={newRecord.status}
                                        onChange={(e) => setNewRecord({ ...newRecord, status: e.target.value })}
                                    >
                                        <option value="Completed">Completed</option>
                                        <option value="In Progress">In Progress</option>
                                        <option value="Abandoned">Abandoned</option>
                                    </select>
                                </label>
                                <label>
                                    Rating (1-5):
                                    <input
                                        type="number"
                                        min="1"
                                        max="5"
                                        value={newRecord.rating}
                                        onChange={(e) => setNewRecord({ ...newRecord, rating: parseInt(e.target.value) || 0 })}
                                    />
                                </label>
                                <div className="form-actions">
                                    <button onClick={handleAddRecord} className="btn btn-primary">Add</button>
                                    <button onClick={() => setShowAddRecord(false)} className="btn">Cancel</button>
                                </div>
                            </div>
                        )}

                        {book.reading_records && book.reading_records.length > 0 ? (
                            <div className="records-list">
                                {book.reading_records.map((record) => (
                                    <div key={record.id} className="record-item">
                                        <span className={`status-badge status-${record.status.toLowerCase().replace(' ', '-')}`}>
                                            {record.status}
                                        </span>
                                        {record.rating && <span className="rating">⭐ {record.rating}/5</span>}
                                        <span className="dates">
                                            {record.start_date} → {record.end_date || 'Present'}
                                        </span>
                                        {record.notes && <p className="notes">{record.notes}</p>}
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <p>No reading records yet.</p>
                        )}
                    </section>
                </>
            )}

            {showDeleteConfirm && (
                <div className="modal-overlay">
                    <div className="modal">
                        <h3>Delete Book?</h3>
                        <p>Are you sure you want to delete "{book.title}"? This action cannot be undone.</p>
                        <div className="modal-actions">
                            <button onClick={handleDelete} className="btn btn-danger">Delete</button>
                            <button onClick={() => setShowDeleteConfirm(false)} className="btn">Cancel</button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default BookDetailPage;