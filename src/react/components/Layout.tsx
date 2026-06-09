import React, { useContext, useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { AppContext } from '../App';

interface LayoutProps {
    children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
    const { theme, setTheme, syncStatus } = useContext(AppContext);
    const [showThemeMenu, setShowThemeMenu] = useState(false);
    const [jobIndicator, setJobIndicator] = useState<string | null>(null);
    const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
    const location = useLocation();

    useEffect(() => {
        // Check for job_id in URL params
        const params = new URLSearchParams(window.location.search);
        const jobId = params.get('job_id');
        if (jobId) {
            setJobIndicator(jobId);
        }
    }, [location]);

    const navItems = [
        { path: '/', label: 'Home' },
        { path: '/books', label: 'My Books' },
        { path: '/reading-list', label: 'Reading List' },
        { path: '/history', label: 'History' },
        { path: '/stats', label: 'Statistics' },
    ];

    return (
        <div className="app-container">
            <header className="site-header">
                <nav className="main-nav">
                    <Link to="/" className="logo">
                        Book Lamp
                    </Link>
                    {/* Mobile menu toggle button */}
                    <button
                        className="mobile-menu-toggle btn-icon"
                        onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                        aria-label={mobileMenuOpen ? 'Close menu' : 'Open menu'}
                        aria-expanded={mobileMenuOpen}
                    >
                        {mobileMenuOpen ? '✕' : '☰'}
                    </button>
                    <ul className={`nav-links ${mobileMenuOpen ? 'nav-open' : ''}`}>
                        {navItems.map((item) => (
                            <li key={item.path}>
                                <Link
                                    to={item.path}
                                    className={location.pathname === item.path ? 'active' : ''}
                                    onClick={() => setMobileMenuOpen(false)}
                                >
                                    {item.label}
                                </Link>
                            </li>
                        ))}
                    </ul>
                    <div className="nav-actions">
                        {syncStatus === 'ok' && (
                            <span className="sync-badge" title="Sync OK">
                                ✓
                            </span>
                        )}
                        {syncStatus === 'error' && (
                            <span className="sync-badge sync-error" title="Sync Error">
                                ⚠
                            </span>
                        )}
                        <div className="theme-selector">
                            <button
                                className="btn-icon"
                                onClick={() => setShowThemeMenu(!showThemeMenu)}
                                aria-label="Change theme"
                            >
                                {theme === 'dark' ? '🌙' : theme === 'light' ? '☀️' : '💻'}
                            </button>
                            {showThemeMenu && (
                                <div className="theme-menu">
                                    <button
                                        className={`btn btn-text ${theme === 'light' ? 'active' : ''}`}
                                        onClick={() => {
                                            setTheme('light');
                                            setShowThemeMenu(false);
                                        }}
                                    >
                                        Light
                                    </button>
                                    <button
                                        className={`btn btn-text ${theme === 'dark' ? 'active' : ''}`}
                                        onClick={() => {
                                            setTheme('dark');
                                            setShowThemeMenu(false);
                                        }}
                                    >
                                        Dark
                                    </button>
                                    <button
                                        className={`btn btn-text ${theme === 'system' ? 'active' : ''}`}
                                        onClick={() => {
                                            setTheme('system');
                                            setShowThemeMenu(false);
                                        }}
                                    >
                                        System
                                    </button>
                                </div>
                            )}
                        </div>
                        <Link to="/books/new" className="btn btn-primary">
                            + Add Book
                        </Link>
                    </div>
                </nav>
            </header>

            {jobIndicator && (
                <div className="job-indicator" data-job-id={jobIndicator}>
                    <span className="spinner"></span>
                    Processing...
                </div>
            )}

            <main className="main-content">{children}</main>

            <footer className="site-footer">
                <p>
                    Book Lamp &copy; {new Date().getFullYear()}
                </p>
            </footer>
        </div>
    );
};

export default Layout;
