import React from 'react';
import { Link } from 'react-router-dom';
import type { Book } from '../types';
import { statusClass } from '../utils/status';

interface BookExhibitProps {
    book: Book;
    /** Where the exhibit links. Defaults to the Book's detail page. */
    to?: string;
}

/**
 * A Book presented as an exhibit: a framed cover on a plinth, then a placard
 * with the title, author and an accession line. Used by the collection grid,
 * the home page and publisher pages so every Book reads the same way.
 */
const BookExhibit: React.FC<BookExhibitProps> = ({ book, to }) => {
    const cover = book.cover_url || book.thumbnail_url;

    return (
        <Link to={to ?? `/books/${book.id}`} className="exhibit">
            <div className="exhibit-plinth">
                {cover ? (
                    <img className="exhibit-cover" src={cover} alt="" loading="lazy" />
                ) : (
                    <span className="exhibit-cover-placeholder" aria-hidden="true">
                        📖
                    </span>
                )}
            </div>
            <div className="exhibit-placard">
                <h3 className="exhibit-title">{book.title}</h3>
                <p className="exhibit-author">{book.author || 'Unknown author'}</p>
                <div className="exhibit-meta">
                    {book.latest_status && (
                        <span className={`status-badge ${statusClass(book.latest_status)}`}>
                            {book.latest_status}
                        </span>
                    )}
                    {book.publication_year && (
                        <span className="exhibit-accession">{book.publication_year}</span>
                    )}
                </div>
            </div>
        </Link>
    );
};

export default BookExhibit;
