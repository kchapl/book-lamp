import React from 'react';
import { Link } from 'react-router-dom';
import type { Book } from '../types';
import { statusClass } from '../utils/status';
import { splitSubtitle } from '../utils/title';

interface BookExhibitProps {
    book: Book;
    /** Where the exhibit links. Defaults to the Book's detail page. */
    to?: string;
    /**
     * Heading level for the title. Use `h2` when the grid is the page's main
     * content (so the heading order stays h1 → h2) and `h3` when it sits under
     * its own section heading. Defaults to `h3`.
     */
    titleAs?: 'h2' | 'h3';
}

/**
 * A Book presented as an exhibit: a framed cover on a plinth, then a placard
 * with the title, author and an accession line. Used by the books grid,
 * the home page and publisher pages so every Book reads the same way.
 */
const BookExhibit: React.FC<BookExhibitProps> = ({ book, to, titleAs = 'h3' }) => {
    const cover = book.cover_url || book.thumbnail_url;
    const Title = titleAs;
    // The stored title keeps its subtitle; the card reads the two parts apart,
    // so the heading names the work and the subtitle qualifies the edition.
    const { title, subtitle } = splitSubtitle(book.title);

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
                <Title className="exhibit-title">{title}</Title>
                {subtitle && <p className="exhibit-subtitle">{subtitle}</p>}
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
