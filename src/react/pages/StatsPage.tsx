import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getStats } from '../services/api';
import type { Stats } from '../types';
import CategoryChart from '../components/CategoryChart';
import TimePeriodSelector, { TimePeriod } from '../components/TimePeriodSelector';
import GoalProgress from '../components/GoalProgress';

const StatsPage: React.FC = () => {
    const [stats, setStats] = useState<Stats | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [timePeriod, setTimePeriod] = useState<TimePeriod>('year');

    useEffect(() => {
        loadStats();
    }, [timePeriod]);

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

    const formatNumber = (num: number | undefined): string => {
        if (num === undefined || num === null) return '0';
        return num.toLocaleString();
    };

    const getChangeIndicator = (change: number | undefined): { text: string; className: string } => {
        if (change === undefined) return { text: '', className: '' };
        if (change > 0) return { text: `+${change}%`, className: 'positive' };
        if (change < 0) return { text: `${change}%`, className: 'negative' };
        return { text: '0%', className: 'neutral' };
    };

    const yearChange = getChangeIndicator(stats.year_comparison?.percentage_change);

    return (
        <div className="stats-page">
            <div className="stats-header">
                <h1>Dashboard</h1>
                <TimePeriodSelector value={timePeriod} onChange={setTimePeriod} />
            </div>

            {/* Overview Cards */}
            <div className="stats-overview">
                <div className="stat-card">
                    <span className="stat-value">{formatNumber(stats.total_books)}</span>
                    <span className="stat-label">Books Completed</span>
                </div>
                <div className="stat-card">
                    <span className="stat-value">{stats.avg_rating?.toFixed(1) || '0.0'}</span>
                    <span className="stat-label">Average Rating</span>
                </div>
                <div className="stat-card highlight">
                    <span className="stat-value">{formatNumber(stats.total_pages_read)}</span>
                    <span className="stat-label">Pages Read</span>
                </div>
                <div className="stat-card">
                    <span className="stat-value">{stats.avg_pages_per_book?.toFixed(0) || '0'}</span>
                    <span className="stat-label">Avg Pages/Book</span>
                </div>
            </div>

            {/* Year-over-Year Comparison & Streak */}
            <div className="stats-row">
                <div className="stat-card wide">
                    <div className="streak-card">
                        <div className="streak-icon">🔥</div>
                        <div className="streak-info">
                            <span className="streak-value">{stats.current_streak || 0}</span>
                            <span className="streak-label">Month Streak</span>
                        </div>
                        <div className="streak-divider"></div>
                        <div className="streak-info">
                            <span className="streak-value">{stats.longest_streak || 0}</span>
                            <span className="streak-label">Longest Streak</span>
                        </div>
                    </div>
                </div>
                <div className="stat-card wide">
                    <div className="year-comparison">
                        <div className="comparison-main">
                            <span className="comparison-value">{stats.books_this_year || 0}</span>
                            <span className="comparison-label">Books This Year</span>
                        </div>
                        <div className={`comparison-change ${yearChange.className}`}>
                            {yearChange.text} vs last year
                        </div>
                        {stats.yearly_goal && (
                            <GoalProgress
                                current={stats.books_this_year || 0}
                                goal={stats.yearly_goal}
                            />
                        )}
                    </div>
                </div>
            </div>

            {/* Reading Pace */}
            <div className="stats-overview">
                <div className="stat-card">
                    <span className="stat-value">{stats.reading_pace_monthly?.toFixed(1) || '0'}</span>
                    <span className="stat-label">Books/Month</span>
                </div>
                <div className="stat-card">
                    <span className="stat-value">{stats.reading_pace_annualised?.toFixed(0) || '0'}</span>
                    <span className="stat-label">Books/Year (Pace)</span>
                </div>
                <div className="stat-card">
                    <span className="stat-value">{formatNumber(stats.total_reading_days)}</span>
                    <span className="stat-label">Total Reading Days</span>
                </div>
                <div className="stat-card">
                    <span className="stat-value">{stats.avg_reading_time_days?.toFixed(0) || '0'}</span>
                    <span className="stat-label">Avg Days/Book</span>
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

            {/* Top Series */}
            {stats.top_series && stats.top_series.length > 0 && (
                <div className="stats-section">
                    <h2>Top Series</h2>
                    <ul className="top-list">
                        {stats.top_series.map((series, i) => (
                            <li key={i}>
                                <span className="series-name">{series.name}</span>
                                <span className="count">{series.count} books</span>
                            </li>
                        ))}
                    </ul>
                </div>
            )}

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

            {/* Format Distribution */}
            {stats.format_distribution && stats.format_distribution.length > 0 && (
                <div className="stats-section">
                    <h2>Format Distribution</h2>
                    <div className="format-bars">
                        {stats.format_distribution.map(({ label, count }) => {
                            const maxFormatCount = stats.format_distribution?.[0]?.count || 1;
                            const percentage = (count / maxFormatCount) * 100;
                            return (
                                <div key={label} className="format-item">
                                    <span className="format-label">{label}</span>
                                    <div className="format-bar">
                                        <div 
                                            className="format-fill"
                                            style={{ width: `${percentage}%` }}
                                        ></div>
                                    </div>
                                    <span className="format-count">{count}</span>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}

            {/* Category Distribution with Interactive Treemap */}
            {(stats.category_distribution?.length ?? 0) > 0 && (
                <div className="stats-section">
                    <h2>Category Distribution</h2>
                    {stats.category_details && stats.category_details.length > 0 ? (
                        <CategoryChart
                            categories={stats.category_details}
                            maxCount={stats.max_category_count}
                        />
                    ) : (
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
                    )}
                </div>
            )}

            {/* Language Distribution */}
            {stats.language_distribution && stats.language_distribution.length > 0 && (
                <div className="stats-section">
                    <h2>Language Distribution</h2>
                    <div className="language-bars">
                        {stats.language_distribution.slice(0, 5).map(({ label, count }) => {
                            const maxLangCount = stats.language_distribution?.[0]?.count || 1;
                            const percentage = (count / maxLangCount) * 100;
                            return (
                                <div key={label} className="language-item">
                                    <span className="language-label">{label}</span>
                                    <div className="language-bar">
                                        <div 
                                            className="language-fill"
                                            style={{ width: `${percentage}%` }}
                                        ></div>
                                    </div>
                                    <span className="language-count">{count}</span>
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