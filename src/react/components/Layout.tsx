import React, { useContext, useState, useEffect, useRef } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { AppContext } from '../App';
import { fetchCovers, getJobStatus } from '../services/api';
import { useRefreshCollection } from '../hooks/useCollectionRevision';
import Icon, { IconName } from './Icon';
import { Button, IconButton } from '../ui';

interface LayoutProps {
    children: React.ReactNode;
}

const NAV_ITEMS: { path: string; label: string; icon: IconName }[] = [
    { path: '/', label: 'Home', icon: 'home' },
    { path: '/books', label: 'My Books', icon: 'books' },
    { path: '/reading-list', label: 'Reading List', icon: 'bookmark' },
    { path: '/history', label: 'History', icon: 'history' },
    { path: '/dashboard', label: 'Dashboard', icon: 'chart' },
];

const THEME_OPTIONS: { value: 'light' | 'dark' | 'system'; label: string; icon: IconName }[] = [
    { value: 'light', label: 'Light', icon: 'sun' },
    { value: 'dark', label: 'Dark', icon: 'moon' },
    { value: 'system', label: 'System', icon: 'monitor' },
];

/** A background job the layout is reporting on, wherever the reader is. */
interface BackgroundJob {
    id: string;
    progress: number;
    result: string | null;
    error: string | null;
    done: boolean;
    /** Whether the run wrote collection data a page may be showing. */
    refreshesCollection: boolean;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
    const { theme, setTheme, syncStatus, isAuthorized, logoutUser } = useContext(AppContext);
    const [showThemeMenu, setShowThemeMenu] = useState(false);
    const [showAccountMenu, setShowAccountMenu] = useState(false);
    const [job, setJob] = useState<BackgroundJob | null>(null);
    const refreshCollection = useRefreshCollection();
    const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
    const location = useLocation();
    const accountRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const params = new URLSearchParams(window.location.search);
        const jobId = params.get('job_id');
        if (jobId) {
            setJob({
                id: jobId,
                progress: 0,
                result: null,
                error: null,
                done: false,
                refreshesCollection: false,
            });
        }
    }, [location]);

    // A job started by a redirect (an import, a backfill) reports through the
    // same strip, so the reader sees it finish wherever the redirect landed.
    useEffect(() => {
        const jobId = job?.id;
        if (!jobId) return;
        const refreshesCollection = job?.refreshesCollection ?? false;

        let cancelled = false;
        let timer: number | undefined;

        const poll = async () => {
            try {
                const status = await getJobStatus(jobId);
                if (cancelled) return;
                const done = status.status === 'completed' || status.status === 'failed';
                setJob({
                    id: jobId,
                    refreshesCollection,
                    progress: status.progress ?? 0,
                    result: status.result ?? null,
                    error: status.status === 'failed' ? status.error || 'The job failed' : null,
                    done,
                });
                if (!done) timer = window.setTimeout(poll, 1000);
            } catch (err) {
                if (!cancelled) {
                    setJob({
                        id: jobId,
                        refreshesCollection,
                        progress: 0,
                        result: null,
                        error: err instanceof Error ? err.message : 'Could not check the job',
                        done: true,
                    });
                }
            }
        };

        poll();
        return () => {
            cancelled = true;
            if (timer !== undefined) window.clearTimeout(timer);
        };
    }, [job?.id, job?.refreshesCollection]);

    // The run changed the collection while a page may be showing it: My Books
    // keeps its cards, so the page has to refetch to show the new covers.
    useEffect(() => {
        if (!job?.done || !job.refreshesCollection || job.error) return;
        refreshCollection();
    }, [job?.id, job?.done, job?.refreshesCollection, job?.error, refreshCollection]);

    useEffect(() => {
        if (!job?.done) return;
        // The report is feedback, not a fixture: it goes away on its own.
        const timer = window.setTimeout(() => setJob(null), 10000);
        return () => window.clearTimeout(timer);
    }, [job?.id, job?.done]);

    /** A general utility, so it lives in the menu rather than on a page. */
    const fillMissingCovers = async () => {
        setShowAccountMenu(false);
        try {
            const { job_id } = await fetchCovers([]);
            setJob({
                id: job_id,
                progress: 0,
                result: null,
                error: null,
                done: false,
                refreshesCollection: true,
            });
        } catch (err) {
            setJob({
                id: '',
                progress: 0,
                result: null,
                error: err instanceof Error ? err.message : 'Could not start the cover lookup',
                done: true,
                refreshesCollection: false,
            });
        }
    };

    useEffect(() => {
        // A route change always closes the mobile menu and its dropdowns.
        setMobileMenuOpen(false);
        setShowThemeMenu(false);
        setShowAccountMenu(false);
    }, [location.pathname]);

    useEffect(() => {
        if (!showAccountMenu) return;

        // A dropdown that ignores Escape or a click elsewhere traps a reader in
        // it, so both close the account menu from anywhere on the page.
        const onPointerDown = (event: MouseEvent) => {
            if (!accountRef.current?.contains(event.target as Node)) {
                setShowAccountMenu(false);
            }
        };
        const onKeyDown = (event: KeyboardEvent) => {
            if (event.key === 'Escape') setShowAccountMenu(false);
        };

        document.addEventListener('mousedown', onPointerDown);
        document.addEventListener('keydown', onKeyDown);
        return () => {
            document.removeEventListener('mousedown', onPointerDown);
            document.removeEventListener('keydown', onKeyDown);
        };
    }, [showAccountMenu]);

    const isActive = (path: string) =>
        path === '/' ? location.pathname === '/' : location.pathname.startsWith(path);

    // `/` matches only itself and no two entries share a prefix, so the first
    // entry that matches is the one to mark current.
    const activeNavPath = NAV_ITEMS.find((item) => isActive(item.path))?.path;

    return (
        <div className="app-container">
            <header className="site-header">
                <nav className="main-nav" aria-label="Primary">
                    <Link to="/" className="logo">
                        <span className="logo-mark" aria-hidden="true">
                            <Icon name="lamp" size="sm" />
                        </span>
                        Book Lamp
                    </Link>

                    {/* ARIA wants "true"/"false", and React writes a bare
                        boolean to a custom element as an empty attribute, which
                        is neither to a screen reader: these three toggles state
                        their state as strings for that reason. */}
                    <IconButton
                        icon={mobileMenuOpen ? 'close' : 'menu'}
                        className="mobile-menu-toggle"
                        onClick={() => setMobileMenuOpen((open) => !open)}
                        aria-label={mobileMenuOpen ? 'Close menu' : 'Open menu'}
                        aria-expanded={mobileMenuOpen ? 'true' : 'false'}
                    />

                    <ul className={`nav-links ${mobileMenuOpen ? 'nav-open' : ''}`}>
                        {NAV_ITEMS.map((item) => {
                            const active = item.path === activeNavPath;
                            return (
                                <li key={item.path}>
                                    <Link
                                        to={item.path}
                                        className={active ? 'active' : ''}
                                        aria-current={active ? 'page' : undefined}
                                    >
                                        <Icon name={item.icon} size="sm" />
                                        {item.label}
                                    </Link>
                                </li>
                            );
                        })}
                    </ul>

                    <div className="nav-actions">
                        {syncStatus === 'error' && (
                            <span
                                className="sync-badge"
                                role="img"
                                title="Sync problem — check storage"
                                aria-label="Sync problem"
                            />
                        )}

                        <div className="theme-selector">
                            <IconButton
                                icon="contrast"
                                onClick={() => {
                                    setShowThemeMenu((open) => !open);
                                    setShowAccountMenu(false);
                                }}
                                aria-label="Change theme"
                                aria-expanded={showThemeMenu ? 'true' : 'false'}
                                aria-haspopup="menu"
                            />
                            {showThemeMenu && (
                                <div className="theme-menu" role="menu">
                                    {THEME_OPTIONS.map((option) => (
                                        <Button
                                            key={option.value}
                                            variant="text"
                                            icon={option.icon}
                                            className={theme === option.value ? 'active' : undefined}
                                            role="menuitemradio"
                                            aria-checked={theme === option.value}
                                            onClick={() => {
                                                setTheme(option.value);
                                                setShowThemeMenu(false);
                                            }}
                                        >
                                            <span>{option.label}</span>
                                        </Button>
                                    ))}
                                </div>
                            )}
                        </div>

                        {isAuthorized ? (
                            <div className="account-selector" ref={accountRef}>
                                <Button
                                    variant="text"
                                    aria-label="Account"
                                    aria-haspopup="menu"
                                    aria-expanded={showAccountMenu ? 'true' : 'false'}
                                    onClick={() => {
                                        setShowAccountMenu((open) => !open);
                                        setShowThemeMenu(false);
                                    }}
                                >
                                    Account
                                </Button>
                                {showAccountMenu && (
                                    <div className="account-menu" role="menu" aria-label="Account">
                                        <Button
                                            variant="text"
                                            role="menuitem"
                                            aria-label="Fill in missing book covers"
                                            onClick={fillMissingCovers}
                                        >
                                            Fill missing covers
                                        </Button>
                                        <Button
                                            variant="text"
                                            role="menuitem"
                                            aria-label="Export my data as CSV"
                                            onClick={() => {
                                                setShowAccountMenu(false);
                                                window.location.assign('/api/export/csv');
                                            }}
                                        >
                                            Export CSV
                                        </Button>
                                        <Button
                                            variant="text"
                                            role="menuitem"
                                            aria-label="Sign out"
                                            onClick={() => {
                                                setShowAccountMenu(false);
                                                logoutUser();
                                            }}
                                        >
                                            Sign out
                                        </Button>
                                    </div>
                                )}
                            </div>
                        ) : (
                            <Button variant="outlined" to="/unauthorised">
                                Sign in
                            </Button>
                        )}
                    </div>
                </nav>
            </header>

            {mobileMenuOpen && (
                <div
                    className="mobile-menu-backdrop"
                    onClick={() => setMobileMenuOpen(false)}
                    aria-hidden="true"
                />
            )}

            {job && (
                <div className="job-indicator" data-job-id={job.id} role="status">
                    {job.result || job.error ? (
                        <span>{job.error ?? job.result}</span>
                    ) : (
                        <>
                            <span className="spinner" aria-hidden="true" />
                            {job.progress > 0 ? `Working… ${job.progress}%` : 'Working…'}
                        </>
                    )}
                </div>
            )}

            <main className="main-content">{children}</main>

            <footer className="site-footer">
                <p>
                    Book Lamp &copy; {new Date().getFullYear()} ·{' '}
                    <Link to="/about">About</Link>
                </p>
            </footer>
        </div>
    );
};

export default Layout;
