import React, { useState, useEffect, useContext } from 'react';
import { Link } from 'react-router-dom';
import { AppContext } from '../App';
import GoogleAuth from '../components/GoogleAuth';
import BookExhibit from '../components/BookExhibit';
import Icon, { IconName } from '../components/Icon';
import { getRecommendations } from '../services/api';
import type { Book } from '../types';

const FEATURES: { icon: IconName; title: string; body: string }[] = [
    {
        icon: 'books',
        title: 'Track reading',
        body: 'Keep a record of the books you have read, are reading, or mean to read next.',
    },
    {
        icon: 'chart',
        title: 'See the whole shelf',
        body: 'A dashboard that shows your collection by status, pace, ratings and subjects.',
    },
    {
        icon: 'bookmark',
        title: 'Plan what is next',
        body: 'Queue books on a reading list and start the next one when you are ready.',
    },
];

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
                <h1>Your books, kept like an exhibition.</h1>
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

            <section className="features" aria-label="What Book Lamp does">
                {FEATURES.map((feature) => (
                    <article className="feature-card" key={feature.title}>
                        <Icon name={feature.icon} size="lg" />
                        <h3>{feature.title}</h3>
                        <p>{feature.body}</p>
                    </article>
                ))}
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
