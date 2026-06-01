import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getRecommendations } from '../services/api';
import type { Book } from '../types';
import '../styles/home.css';

const HomePage: React.FC = () => {
    const [recommendations, setRecommendations] = useState<Book[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        loadRecommendations();
    }, []);

    const loadRecommendations = async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await getRecommendations();
            setRecommendations(data.recommendations || []);
        } catch (err) {
            console.error('Failed to load recommendations:', err);
            setError('Failed to load recommendations');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="home-page">
            <section className="hero">
                <h1>Your Personal Library</h1>
                <p>A thoughtful space to track your reading journey, discover new books, and build your personal collection.</p>
                <div className="hero-actions">
                    <Link to="/books" className="btn btn-primary">My Books</Link>
                    <Link to="/stats" className="btn btn-outline">View Statistics</Link>
                </div>
            </section>

            <section className="features">
                <div className="feature-card">
                    <h3>Track Reading</h3>
                    <p>Keep track of books you've read, are currently reading, or want to read next.</p>
                </div>
                <div className="feature-card">
                    <h3>Statistics</h3>
                    <p>View insights about your reading habits, favourite authors, and genres.</p>
                </div>
                <div className="feature-card">
                    <h3>Reading List</h3>
                    <p>Build your queue of books to read next with an organised reading list.</p>
                </div>
            </section>

            {loading ? (
                <div className="recommendations-loading">
                    <div className="skeleton-cards">
                        {[1, 2, 3, 4].map((i) => (
                            <div key={i} className="skeleton-card">
                                <div className="skeleton-image"></div>
                                <div className="skeleton-title"></div>
                                <div className="skeleton-author"></div>
                            </div>
                        ))}
                    </div>
                </div>
            ) : recommendations.length > 0 ? (
                <section className="recommendations">
                    <h2>Recommended for You</h2>
                    <div className="book-grid">
                        {recommendations.map((book) => (
                            <Link
                                key={book.id}
                                to={`/books/${book.id}`}
                                className="book-card"
                            >
                                {book.thumbnail_url ? (
                                    <img src={book.thumbnail_url} alt={book.title} loading="lazy" />
                                ) : (
                                    <div className="book-placeholder">📚</div>
                                )}
                                <div className="book-info">
                                    <h3>{book.title}</h3>
                                    <p className="book-author">{book.author || 'Unknown Author'}</p>
                                </div>
                            </Link>
                        ))}
                    </div>
                </section>
            ) : (
                error && <p className="error-message">{error}</p>
            )}
        </div>
    );
};

export default HomePage;