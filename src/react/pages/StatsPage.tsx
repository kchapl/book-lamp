import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getStats, getBooks } from '../services/api';
import type { Book, Stats } from '../types';
import CategoryChart from '../components/CategoryChart';
import GoalProgress from '../components/GoalProgress';
import Icon from '../components/Icon';
import { statusClass } from '../utils/status';

const STATUS_ORDER = ['Completed', 'In Progress', 'Abandoned'] as const;

const formatNumber = (value: number | undefined | null, fallback = '—'): string =>
    value === undefined || value === null ? fallback : value.toLocaleString();

const formatDate = (iso: string | null | undefined): string => {
    if (!iso) return 'no entries yet';
    const date = new Date(`${iso}T00:00:00`);
    if (Number.isNaN(date.getTime())) return iso;
    return date.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
};

const StatsPage: React.FC = () => {
    const [stats, setStats] = useState<Stats | null>(null);
    const [currentBooks, setCurrentBooks] = useState<Book[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        loadDashboard();
    }, []);

    const loadDashboard = async () => {
        setLoading(true);
        setError(null);
        try {
            const [statsData, inProgress] = await Promise.all([
                getStats(),
                // The dashboard's hero is the books currently being read. A failure
                // here must not take down the whole board, so it is handled apart.
                getBooks({ status: 'In Progress' }).catch(() => ({ books: [] as Book[] })),
            ]);
            setStats(statsData);
            setCurrentBooks(inProgress.books || []);
        } catch (err) {
            console.error('Failed to load stats:', err);
            setError('Failed to load the dashboard');
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return <div className="loading">Loading…</div>;
    }

    if (error || !stats) {
        return (
            <div className="page">
                <p className="error-message">{error || 'Failed to load the dashboard'}</p>
            </div>
        );
    }

    const statusTotal = STATUS_ORDER.reduce((sum, status) => sum + (stats.status_counts[status] || 0), 0);
    const maxYearCount = stats.max_year_count || 1;
    const maxMonthCount = stats.max_month_count || 1;
    const maxFormatCount = stats.format_distribution?.[0]?.count || 1;
    const maxLanguageCount = stats.language_distribution?.[0]?.count || 1;
    const maxRatingCount = Math.max(...stats.rating_distribution.map(([, count]) => count), 1);
    const meterWidth = (value: number): React.CSSProperties =>
        ({ '--meter-width': `${value}%` } as React.CSSProperties);
    const barWidth = (value: number): React.CSSProperties =>
        ({ '--bar-width': `${value}%` } as React.CSSProperties);
    const columnHeight = (value: number): React.CSSProperties =>
        ({ '--column-height': `${value}%` } as React.CSSProperties);

    return (
        <div className="dashboard page">
            <header className="dashboard-hero">
                <div>
                    <p className="eyebrow">Reading room</p>
                    <h1>The collection at a glance</h1>
                    <p className="lede">
                        Every figure below is drawn from your reading records — what has been begun,
                        completed or set aside. Nothing here updates until you add a record.
                    </p>
                </div>
                <p className="as-of" title="The date of your most recent reading record">
                    <Icon name="clock" size="sm" />
                    Last entry {formatDate(stats.last_record_date)}
                </p>
            </header>

            {/* On the lectern — the reading currently under way */}
            <section className="section" aria-labelledby="lectern-heading">
                <h2 id="lectern-heading" className="section-heading">
                    On the lectern
                </h2>
                {currentBooks.length > 0 ? (
                    <div className="lectern-grid">
                        {currentBooks.map((book) => {
                            const cover = book.cover_url || book.thumbnail_url;
                            return (
                                <Link key={book.id} to={`/books/${book.id}`} className="lectern">
                                    {cover ? (
                                        <img className="lectern-cover" src={cover} alt="" loading="lazy" />
                                    ) : (
                                        <span className="lectern-placeholder" aria-hidden="true">
                                            📖
                                        </span>
                                    )}
                                    <div className="lectern-body">
                                        <span className="status-badge status-in-progress">In Progress</span>
                                        <h3>{book.title}</h3>
                                        <p>{book.author || 'Unknown author'}</p>
                                    </div>
                                </Link>
                            );
                        })}
                    </div>
                ) : (
                    <div className="empty-state">
                        <Icon name="bookmark" size="lg" />
                        <h2>Nothing on the lectern</h2>
                        <p>
                            No book is currently in progress. Start one from your reading list and it
                            will appear here.
                        </p>
                        <Link to="/reading-list" className="btn btn-outline">
                            Open the reading list
                        </Link>
                    </div>
                )}
            </section>

            {/* Reading status board */}
            <section className="section" aria-labelledby="status-heading">
                <h2 id="status-heading" className="section-heading">
                    Reading status
                </h2>
                <p className="board-note">
                    {statusTotal} {statusTotal === 1 ? 'book carries' : 'books carry'} a reading status.
                    Books still on the reading list, or not yet begun, are not counted here.
                </p>
                <div className="status-board">
                    {STATUS_ORDER.map((status) => {
                        const count = stats.status_counts[status] || 0;
                        const share = statusTotal > 0 ? (count / statusTotal) * 100 : 0;
                        return (
                            <Link
                                key={status}
                                to={`/books?status=${encodeURIComponent(status)}`}
                                className={`status-card ${statusClass(status).replace('status-', 'is-')}`}
                            >
                                <div className="status-card-top">
                                    <span className="status-card-name">{status}</span>
                                    <span className="status-card-value numeric">{count}</span>
                                </div>
                                <div className="meter" role="presentation">
                                    <div className="meter-fill" style={meterWidth(share)} />
                                </div>
                                <span className="status-card-share">
                                    <span className="numeric">{`${share.toFixed(0)}%`}</span>
                                    <span>of books with a status</span>
                                </span>
                            </Link>
                        );
                    })}
                </div>
            </section>

            {/* Key figures */}
            <section className="section" aria-labelledby="figures-heading">
                <h2 id="figures-heading" className="section-heading">
                    Key figures
                </h2>
                <div className="stat-tiles">
                    <div className="stat-tile">
                        <span className="stat-tile-value numeric">
                            {stats.avg_rating ? stats.avg_rating.toFixed(1) : '—'}
                        </span>
                        <span className="stat-tile-label">Average rating</span>
                    </div>
                    <div className="stat-tile">
                        <span className="stat-tile-value numeric">
                            {formatNumber(stats.total_pages_read, '—')}
                        </span>
                        <span className="stat-tile-label">Pages read</span>
                    </div>
                    <div className="stat-tile">
                        <span className="stat-tile-value numeric">{stats.books_this_year ?? 0}</span>
                        <span className="stat-tile-label">Completed this year</span>
                    </div>
                    <div className="stat-tile">
                        <span className="stat-tile-value numeric">
                            {stats.avg_reading_time_days ? stats.avg_reading_time_days.toFixed(0) : '—'}
                        </span>
                        <span className="stat-tile-label">Avg days per book</span>
                    </div>
                    <div className="stat-tile">
                        <span className="stat-tile-value numeric">{stats.total_authors ?? 0}</span>
                        <span className="stat-tile-label">Authors read</span>
                    </div>
                    <div className="stat-tile">
                        <span className="stat-tile-value numeric">
                            {stats.reading_pace_monthly ? stats.reading_pace_monthly.toFixed(1) : '—'}
                        </span>
                        <span className="stat-tile-label">Books per month</span>
                    </div>
                </div>
            </section>

            <div className="dashboard-grid">
                {stats.yearly_goal ? (
                    <section className="panel" aria-labelledby="goal-heading">
                        <h2 id="goal-heading" className="panel-title">
                            {new Date().getFullYear()} reading goal
                        </h2>
                        <GoalProgress current={stats.books_this_year || 0} goal={stats.yearly_goal} />
                    </section>
                ) : (
                    <section className="panel" aria-labelledby="pace-heading">
                        <h2 id="pace-heading" className="panel-title">
                            Reading pace
                        </h2>
                        <p className="text-muted">
                            {stats.reading_pace_annualised
                                ? `At your current pace you read about ${Math.round(
                                      stats.reading_pace_annualised
                                  )} books a year.`
                                : 'Not enough completed books yet to estimate a pace.'}
                        </p>
                        <div className="stat-tiles">
                            <div className="stat-tile">
                                <span className="stat-tile-value numeric">{stats.total_reading_days ?? 0}</span>
                                <span className="stat-tile-label">Days spent reading</span>
                            </div>
                            <div className="stat-tile">
                                <span className="stat-tile-value numeric">
                                    {stats.avg_pages_per_book ? stats.avg_pages_per_book.toFixed(0) : '—'}
                                </span>
                                <span className="stat-tile-label">Avg pages / book</span>
                            </div>
                        </div>
                    </section>
                )}

                <section className="panel span-2" aria-labelledby="months-heading">
                    <h2 id="months-heading" className="panel-title">
                        Completions by month
                        <span className="panel-note">all years</span>
                    </h2>
                    {maxMonthCount > 1 || stats.monthly_counts.some((m) => m.count > 0) ? (
                        <div className="column-chart">
                            {stats.monthly_counts.map((month) => (
                                <div key={month.index} className="column" title={`${month.name}: ${month.count}`}>
                                    <span className="column-value numeric">{month.count || ''}</span>
                                    <div className="column-track">
                                        <div
                                            className="column-fill"
                                            style={columnHeight((month.count / maxMonthCount) * 100)}
                                        />
                                    </div>
                                    <span className="column-label">{month.name}</span>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <p className="no-data">No completions recorded yet.</p>
                    )}
                </section>
            </div>

            <div className="dashboard-grid">
                <section className="panel" aria-labelledby="years-heading">
                    <h2 id="years-heading" className="panel-title">
                        Completions by year
                    </h2>
                    {stats.yearly_counts.length > 0 ? (
                        <div className="column-chart">
                            {stats.yearly_counts.map(([year, count]) => (
                                <Link key={year} to={`/books?year=${year}`} className="column" title={`${year}: ${count}`}>
                                    <span className="column-value numeric">{count}</span>
                                    <div className="column-track">
                                        <div
                                            className="column-fill"
                                            style={columnHeight((count / maxYearCount) * 100)}
                                        />
                                    </div>
                                    <span className="column-label">{year}</span>
                                </Link>
                            ))}
                        </div>
                    ) : (
                        <p className="no-data">No completions recorded yet.</p>
                    )}
                </section>

                <section className="panel" aria-labelledby="ratings-heading">
                    <h2 id="ratings-heading" className="panel-title">
                        Ratings
                    </h2>
                    <div className="bar-list">
                        {stats.rating_distribution.map(([rating, count]) => (
                            <div key={rating} className="bar-row">
                                <span className="bar-label rating-stars">
                                    {'★'.repeat(rating)}
                                    {'☆'.repeat(5 - rating)}
                                </span>
                                <div className="bar-track">
                                    <div className="bar-fill" style={barWidth((count / maxRatingCount) * 100)} />
                                </div>
                                <span className="bar-value numeric">{count}</span>
                            </div>
                        ))}
                    </div>
                </section>
            </div>

            <div className="dashboard-grid">
                <section className="panel" aria-labelledby="authors-heading">
                    <h2 id="authors-heading" className="panel-title">
                        Most-read authors
                    </h2>
                    {stats.top_authors.length > 0 ? (
                        <ol className="ranked-list">
                            {stats.top_authors.map((author, index) => (
                                <li key={author.name}>
                                    <span className="rank-index numeric">{index + 1}</span>
                                    <Link
                                        to={`/author/${author.name.toLowerCase().replace(/ /g, '-')}`}
                                        className="rank-name"
                                    >
                                        {author.name}
                                    </Link>
                                    <span className="rank-count">{author.count}</span>
                                </li>
                            ))}
                        </ol>
                    ) : (
                        <p className="no-data">No completed books yet.</p>
                    )}
                </section>

                <section className="panel" aria-labelledby="publishers-heading">
                    <h2 id="publishers-heading" className="panel-title">
                        Most-read publishers
                    </h2>
                    {stats.top_publishers.length > 0 ? (
                        <ol className="ranked-list">
                            {stats.top_publishers.map((publisher, index) => (
                                <li key={publisher.name}>
                                    <span className="rank-index numeric">{index + 1}</span>
                                    <Link
                                        to={`/publisher/${publisher.name.toLowerCase().replace(/ /g, '-')}`}
                                        className="rank-name"
                                    >
                                        {publisher.name}
                                    </Link>
                                    <span className="rank-count">{publisher.count}</span>
                                </li>
                            ))}
                        </ol>
                    ) : (
                        <p className="no-data">No completed books yet.</p>
                    )}
                </section>
            </div>

            {(stats.category_distribution?.length ?? 0) > 0 && (
                <section className="section" aria-labelledby="subjects-heading">
                    <h2 id="subjects-heading" className="section-heading">
                        Subjects
                    </h2>
                    <div className="panel">
                        {stats.category_details && stats.category_details.length > 0 ? (
                            <CategoryChart
                                categories={stats.category_details}
                                maxCount={stats.max_category_count}
                            />
                        ) : (
                            <div className="bar-list">
                                {stats.category_distribution.map(({ label, count }) => (
                                    <Link
                                        key={label}
                                        to={`/books?category=${encodeURIComponent(label)}`}
                                        className="bar-row"
                                    >
                                        <span className="bar-label">{label}</span>
                                        <div className="bar-track">
                                            <div
                                                className="bar-fill"
                                                style={barWidth((count / stats.max_category_count) * 100)}
                                            />
                                        </div>
                                        <span className="bar-value numeric">{count}</span>
                                    </Link>
                                ))}
                            </div>
                        )}
                    </div>
                </section>
            )}

            <div className="dashboard-grid">
                {stats.top_series && stats.top_series.length > 0 && (
                    <section className="panel" aria-labelledby="series-heading">
                        <h2 id="series-heading" className="panel-title">
                            Series
                        </h2>
                        <ol className="ranked-list">
                            {stats.top_series.map((series, index) => (
                                <li key={series.name}>
                                    <span className="rank-index numeric">{index + 1}</span>
                                    <span className="rank-name">{series.name}</span>
                                    <span className="rank-count">{series.count}</span>
                                </li>
                            ))}
                        </ol>
                    </section>
                )}

                {stats.format_distribution && stats.format_distribution.length > 0 && (
                    <section className="panel" aria-labelledby="formats-heading">
                        <h2 id="formats-heading" className="panel-title">
                            Formats
                        </h2>
                        <div className="bar-list">
                            {stats.format_distribution.map(({ label, count }) => (
                                <div key={label} className="bar-row">
                                    <span className="bar-label">{label}</span>
                                    <div className="bar-track">
                                        <div className="bar-fill" style={barWidth((count / maxFormatCount) * 100)} />
                                    </div>
                                    <span className="bar-value numeric">{count}</span>
                                </div>
                            ))}
                        </div>
                    </section>
                )}

                {stats.language_distribution && stats.language_distribution.length > 0 && (
                    <section className="panel" aria-labelledby="languages-heading">
                        <h2 id="languages-heading" className="panel-title">
                            Languages
                        </h2>
                        <div className="bar-list">
                            {stats.language_distribution.slice(0, 6).map(({ label, count }) => (
                                <div key={label} className="bar-row">
                                    <span className="bar-label">{label}</span>
                                    <div className="bar-track">
                                        <div className="bar-fill" style={barWidth((count / maxLanguageCount) * 100)} />
                                    </div>
                                    <span className="bar-value numeric">{count}</span>
                                </div>
                            ))}
                        </div>
                    </section>
                )}
            </div>
        </div>
    );
};

export default StatsPage;
