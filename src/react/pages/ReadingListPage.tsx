import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
    DndContext,
    closestCenter,
    KeyboardSensor,
    PointerSensor,
    useSensor,
    useSensors,
    DragEndEvent,
} from '@dnd-kit/core';
import {
    arrayMove,
    SortableContext,
    sortableKeyboardCoordinates,
    useSortable,
    verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { getReadingList, reorderReadingList, removeFromReadingList, startReading } from '../services/api';
import type { ReadingListItem } from '../types';

interface SortableItemProps {
    book: ReadingListItem;
    onRemove: (id: number) => void;
    onStartReading: (id: number) => void;
}

const SortableItem: React.FC<SortableItemProps> = ({ book, onRemove, onStartReading }) => {
    const {
        attributes,
        listeners,
        setNodeRef,
        transform,
        transition,
        isDragging,
    } = useSortable({ id: book.book_id });

    const style = {
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.5 : 1,
    };

    return (
        <div ref={setNodeRef} style={style} className="reading-list-item">
            <div className="drag-handle" {...attributes} {...listeners}>
                ⋮⋮
            </div>
            {book.thumbnail_url ? (
                <img src={book.thumbnail_url} alt={book.title} className="item-thumbnail" />
            ) : (
                <div className="item-placeholder">📖</div>
            )}
            <div className="item-info">
                <h3>{book.title}</h3>
                <p>{book.author}</p>
            </div>
            <div className="item-actions">
                <button onClick={() => onStartReading(book.book_id)} className="btn btn-primary">
                    Start Reading
                </button>
                <button onClick={() => onRemove(book.book_id)} className="btn btn-danger">
                    Remove
                </button>
            </div>
        </div>
    );
};

const ReadingListPage: React.FC = () => {
    const navigate = useNavigate();
    const [books, setBooks] = useState<ReadingListItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const sensors = useSensors(
        useSensor(PointerSensor),
        useSensor(KeyboardSensor, {
            coordinateGetter: sortableKeyboardCoordinates,
        })
    );

    useEffect(() => {
        loadReadingList();
    }, []);

    const loadReadingList = async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await getReadingList();
            setBooks(data.books || []);
        } catch (err) {
            console.error('Failed to load reading list:', err);
            setError('Failed to load reading list');
        } finally {
            setLoading(false);
        }
    };

    const handleDragEnd = async (event: DragEndEvent) => {
        const { active, over } = event;
        if (!over || active.id === over.id) return;

        const oldIndex = books.findIndex((b) => b.book_id === active.id);
        const newIndex = books.findIndex((b) => b.book_id === over.id);

        const newBooks = arrayMove(books, oldIndex, newIndex);
        setBooks(newBooks);

        try {
            await reorderReadingList(newBooks.map((b) => b.book_id));
        } catch (err) {
            console.error('Failed to save new order:', err);
            loadReadingList();
        }
    };

    const handleRemove = async (bookId: number) => {
        try {
            await removeFromReadingList(bookId);
            setBooks(books.filter((b) => b.book_id !== bookId));
        } catch (err) {
            console.error('Failed to remove book:', err);
        }
    };

    const handleStartReading = async (bookId: number) => {
        try {
            await startReading(bookId);
            setBooks(books.filter((b) => b.book_id !== bookId));
        } catch (err) {
            console.error('Failed to start reading:', err);
        }
    };

    return (
        <div className="reading-list-page">
            <h1>Reading List</h1>
            <p className="subtitle">Drag to reorder your reading list</p>

            {loading ? (
                <div className="loading">Loading...</div>
            ) : books.length === 0 ? (
                <div className="empty-state">
                    <h2>Your reading list is empty</h2>
                    <p>Add books from your collection or when browsing.</p>
                    <Link to="/books" className="btn btn-primary">Browse Books</Link>
                </div>
            ) : (
                <DndContext
                    sensors={sensors}
                    collisionDetection={closestCenter}
                    onDragEnd={handleDragEnd}
                >
                    <SortableContext items={books.map((b) => b.book_id)} strategy={verticalListSortingStrategy}>
                        <div className="reading-list">
                            {books.map((book) => (
                                <SortableItem
                                    key={book.book_id}
                                    book={book}
                                    onRemove={handleRemove}
                                    onStartReading={handleStartReading}
                                />
                            ))}
                        </div>
                    </SortableContext>
                </DndContext>
            )}

            {error && <p className="error-message">{error}</p>}
        </div>
    );
};

export default ReadingListPage;