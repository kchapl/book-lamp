import React, { useState, useEffect, useContext } from 'react';
import { Link } from 'react-router-dom';
import { AppContext } from '../App';
import GoogleAuth from '../components/GoogleAuth';
import BookExhibit from '../components/BookExhibit';
import Icon from '../components/Icon';
import { getRecommendations } from '../services/api';
import type { Book } from '../types';

const HomePage: React.FC = () => {
    const { isAuthorized } = useContext(AppContext);
    const [recommendations, setRecommendations] = useState<Book[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (isAuthorized) {
            loadRecommendations();
        }
    }, [isAuthorized]);

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
        <div className="home-page page">
            <section className="hero">
                <p className="eyebrow label-placard">The reading room</p>
                <h1>Your books.</h1>
                <p>
                    Book Lamp is a quiet record of what you have read: the collection on the
                    shelves, the reading list ahead of you, and a dashboard that shows how it
                    all adds up.
                </p>
                {isAuthorized ? (
                    <div className="hero-actions">
                        <Link to="/books" className="btn btn-primary">
                            <Icon name="books" size="sm" />
                            Browse the collection
                        </Link>
                        <Link to="/dashboard" className="btn btn-outline">
                            <Icon name="chart" size="sm" />
                            Open the dashboard
                        </Link>
                    </div>
                ) : (
                    <div className="auth-card">
                        <p>Sign in with Google to open your reading room:</p>
                        <GoogleAuth />
                    </div>
                )}
            </section>

            {loading ? (
                <section className="recommendations" aria-busy="true">
                    <h2>Recommended for you</h2>
                    <div className="skeleton-grid">
                        {[1, 2, 3].map((i) => (
                            <div key={i} className="skeleton-card">
                                <div className="skeleton-image" />
                                <div className="skeleton-title" />
                                <div className="skeleton-author" />
                            </div>
                        ))}
                    </div>
                </section>
            ) : recommendations.length > 0 ? (
                <section className="recommendations">
                    <h2>Recommended for you</h2>
                    <div className="exhibit-grid">
                        {recommendations.map((book) => (
                            <BookExhibit key={book.id} book={book} />
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
