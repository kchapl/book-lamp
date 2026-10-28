import React, { useEffect, useState } from 'react';
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
import { Button, IconButton } from '../ui';
import { useResource } from '../hooks/useResource';
import type { ReadingListItem } from '../types';

/**
 * The Reading List's add action lands on the Add a Book form with the
 * reading-list option already ticked: a reader who came from the list means to
 * queue the Book, not just record it.
 */
const ADD_BOOK_TO_READING_LIST = '/books/new?add_to_reading_list=1';

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
    } = useSortable({ id: book.id });

    const style = {
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.5 : 1,
    };

    return (
        <div ref={setNodeRef} style={style} className="reading-list-item">
            <IconButton
                icon="grip"
                className="drag-handle"
                aria-label={`Reorder ${book.title}`}
                {...(attributes as object)}
                {...(listeners as object)}
            />
            {book.thumbnail_url ? (
                <img src={book.thumbnail_url} alt={book.title} className="item-thumbnail" />
            ) : (
                <div className="item-placeholder">📖</div>
            )}
            <div className="item-info">
                <h2>{book.title}</h2>
                <p>{book.author}</p>
            </div>
            <div className="item-actions">
                <Button onClick={() => onStartReading(book.id)}>Start Reading</Button>
                <Button variant="outlined" className="btn-danger" onClick={() => onRemove(book.id)}>
                    Remove
                </Button>
            </div>
        </div>
    );
};

const ReadingListPage: React.FC = () => {
    const loadReadingList = async () => (await getReadingList()).books || [];

    const { data, loading, error, reload } = useResource(loadReadingList, [], {
        errorMessage: 'Failed to load reading list',
    });

    // A write shows its effect at once, while the request is in flight. The
    // override is dropped as soon as a fresh list arrives, so the server stays
    // the source of truth and a failed write falls back to what it holds.
    const [pending, setPending] = useState<ReadingListItem[] | null>(null);
    useEffect(() => setPending(null), [data]);
    const books = pending ?? data ?? [];

    const sensors = useSensors(
        useSensor(PointerSensor),
        useSensor(KeyboardSensor, {
            coordinateGetter: sortableKeyboardCoordinates,
        })
    );

    const handleDragEnd = async (event: DragEndEvent) => {
        const { active, over } = event;
        if (!over || active.id === over.id) return;

        const oldIndex = books.findIndex((b) => b.id === active.id);
        const newIndex = books.findIndex((b) => b.id === over.id);
        if (oldIndex < 0 || newIndex < 0) return;

        const next = arrayMove(books, oldIndex, newIndex);
        setPending(next);

        try {
            await reorderReadingList(next.map((b) => b.id));
        } catch (err) {
            console.error('Failed to save new order:', err);
        } finally {
            reload();
        }
    };

    const handleRemove = async (bookId: number) => {
        setPending(books.filter((b) => b.id !== bookId));
        try {
            await removeFromReadingList(bookId);
        } catch (err) {
            console.error('Failed to remove book:', err);
        } finally {
            reload();
        }
    };

    const handleStartReading = async (bookId: number) => {
        setPending(books.filter((b) => b.id !== bookId));
        try {
            await startReading(bookId);
        } catch (err) {
            console.error('Failed to start reading:', err);
        } finally {
            reload();
        }
    };

    return (
        <div className="reading-list-page page">
            <header className="page-header">
                <div>
                    <p className="eyebrow label-placard">What is next</p>
                    <h1>Reading List</h1>
                    <p className="subtitle">Drag to reorder the queue.</p>
                </div>
                {!loading && books.length > 0 && (
                    <Button variant="filled" icon="plus" to={ADD_BOOK_TO_READING_LIST}>
                        Add a book
                    </Button>
                )}
            </header>

            {loading ? (
                <div className="loading">Loading…</div>
            ) : books.length === 0 ? (
                <div className="empty-state">
                    <h2>Your reading list is empty</h2>
                    <p>Add books from your log or while browsing.</p>
                    <Button variant="filled" icon="plus" to={ADD_BOOK_TO_READING_LIST}>
                        Add a book
                    </Button>
                    <Button variant="text" to="/books">
                        Browse Books
                    </Button>
                </div>
            ) : (
                <DndContext
                    sensors={sensors}
                    collisionDetection={closestCenter}
                    onDragEnd={handleDragEnd}
                >
                    <SortableContext items={books.map((b) => b.id)} strategy={verticalListSortingStrategy}>
                        <div className="reading-list">
                            {books.map((book) => (
                                <SortableItem
                                    key={book.id}
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
