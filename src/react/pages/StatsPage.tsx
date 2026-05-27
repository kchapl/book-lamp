import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getStats } from '../services/api';
import type { Stats } from '../types';

const StatsPage: React.FC = () => {
    const [stats, setStats] = useState<Stats | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        loadStats();
    }, []);

    const loadStats = async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await getStats();
            setStats(data);
        } catch (err) {
            console.error('Failed to load stats:', err);
            setError('Failed to load statistics');
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return <div className="loading">Loading...</div>;
    }

    if (error || !stats) {
        return <div className="error-message">{error || 'Failed to load stats'}</div>;
    }

    return (
        <div className="stats-page">
            <h1>Statistics</h1>

            <div className="stats-overview">
                <div className="stat-card">
                    <span className="stat-value">{stats.total_books}</span>
                    <span className="stat-label">Books Completed</span>
                </div>
                <div className="stat-card">
                    <span className="stat-value">{stats.total_authors}</span>
                    <span className="stat-label">Authors</span>
                </div>
                <div className="stat-card">
                    <span className="stat-value">{stats.total_records}</span>
                    <span className="stat-label">Reading Records</span>
                </div>
                <div className="stat-card">
                    <span className="stat-value">{stats.avg_rating.toFixed(1)}</span>
                    <span className="stat-label">Average Rating</span>
                </div>
            </div>

            <div className="stats-section">
                <h2>Reading Status</h2>
                <div className="progress-bars">
                    {Object.entries(stats.status_counts).map(([status, count]) => {
                        const percentage = stats.total_books > 0 
                            ? (count / stats.total_books) * 100 
                            : 0;
                        return (
                            <div key={status} className="progress-item">
                                <span className="progress-label">{status}</span>
                                <div className="progress-bar">
                                    <div 
                                        className={`progress-fill status-${status.toLowerCase().replace(' ', '-')}`}
                                        style={{ width: `${percentage}%` }}
                                    ></div>
                                </div>
                                <span className="progress-count">{count}</span>
                            </div>
                        );
                    })}
                </div>
            </div>

            <div className="stats-section">
                <h2>Rating Distribution</h2>
                <div className="rating-bars">
                    {stats.rating_distribution.map(([rating, count]) => {
                        const percentage = stats.total_records > 0
                            ? (count / stats.total_records) * 100
                            : 0;
                        return (
                            <div key={rating} className="rating-item">
                                <span className="rating-label">{'★'.repeat(rating)}</span>
                                <div className="rating-bar">
                                    <div 
                                        className="rating-fill"
                                        style={{ width: `${percentage}%` }}
                                    ></div>
                                </div>
                                <span className="rating-count">{count}</span>
                            </div>
                        );
                    })}
                </div>
            </div>

            <div className="stats-columns">
                <div className="stats-section">
                    <h2>Top Authors</h2>
                    <ul className="top-list">
                        {stats.top_authors.map((author, i) => (
                            <li key={i}>
                                <Link to={`/author/${author.name.toLowerCase().replace(/ /g, '-')}`}>
                                    {author.name}
                                </Link>
                                <span className="count">{author.count}</span>
                            </li>
                        ))}
                    </ul>
                </div>

                <div className="stats-section">
                    <h2>Top Publishers</h2>
                    <ul className="top-list">
                        {stats.top_publishers.map((publisher, i) => (
                            <li key={i}>
                                <Link to={`/publisher/${publisher.name.toLowerCase().replace(/ /g, '-')}`}>
                                    {publisher.name}
                                </Link>
                                <span className="count">{publisher.count}</span>
                            </li>
                        ))}
                    </ul>
                </div>
            </div>

            <div className="stats-section">
                <h2>Yearly Completions</h2>
                {stats.yearly_counts.length > 0 ? (
                    <div className="year-bars">
                        {stats.yearly_counts.map(([year, count]) => (
                            <Link 
                                key={year} 
                                to={`/books?year=${year}`}
                                className="year-item"
                            >
                                <span className="year-label">{year}</span>
                                <div className="year-bar">
                                    <div 
                                        className="year-fill"
                                        style={{ 
                                            width: `${(count / stats.max_year_count) * 100}%` 
                                        }}
                                    ></div>
                                </div>
                                <span className="year-count">{count}</span>
                            </Link>
                        ))}
                    </div>
                ) : (
                    <p>No data available yet.</p>
                )}
            </div>

            <div className="stats-section">
                <h2>Monthly Distribution</h2>
                <div className="month-bars">
                    {stats.monthly_counts.map((month) => {
                        const percentage = stats.max_month_count > 0
                            ? (month.count / stats.max_month_count) * 100
                            : 0;
                        return (
                            <div key={month.index} className="month-item">
                                <span className="month-label">{month.name}</span>
                                <div className="month-bar">
                                    <div 
                                        className="month-fill"
                                        style={{ height: `${percentage}%` }}
                                    ></div>
                                </div>
                                <span className="month-count">{month.count}</span>
                            </div>
                        );
                    })}
                </div>
            </div>

            {stats.category_distribution.length > 0 && (
                <div className="stats-section">
                    <h2>Category Distribution</h2>
                    <div className="category-bars">
                        {stats.category_distribution.map(({ label, count }) => {
                            const percentage = stats.max_category_count > 0
                                ? (count / stats.max_category_count) * 100
                                : 0;
                            return (
                                <div key={label} className="category-item">
                                    <span className="category-label">{label}</span>
                                    <div className="category-bar">
                                        <div 
                                            className="category-fill"
                                            style={{ width: `${percentage}%` }}
                                        ></div>
                                    </div>
                                    <span className="category-count">{count}</span>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}
        </div>
    );
};

export default StatsPage;