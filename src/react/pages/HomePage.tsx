import React, { useContext } from 'react';
import { AppContext } from '../App';
import GoogleAuth from '../components/GoogleAuth';
import BookExhibit from '../components/BookExhibit';
import { Button } from '../ui';
import { getRecommendations } from '../services/api';
import { useResource } from '../hooks/useResource';

const HomePage: React.FC = () => {
    const { isAuthorized } = useContext(AppContext);

    const loadRecommendations = async () => {
        const data = await getRecommendations();
        return data.recommendations || [];
    };

    // Recommendations need a session, so the resource stays disabled — and not
    // loading — until the visitor is signed in.
    const { data, loading, error } = useResource(loadRecommendations, [isAuthorized], {
        enabled: isAuthorized,
        errorMessage: 'Failed to load recommendations',
    });

    const recommendations = data ?? [];

    return (
        <div className="home-page page">
            <section className="hero">
                <p className="eyebrow label-placard">The reading room</p>
                <h1>Your books.</h1>
                {isAuthorized ? (
                    <div className="hero-actions">
                        <Button variant="filled" icon="books" to="/books">
                            Browse your books
                        </Button>
                        <Button variant="outlined" icon="chart" to="/dashboard">
                            Open the dashboard
                        </Button>
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
