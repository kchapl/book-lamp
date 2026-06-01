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

    // Close mobile menu on route change
    useEffect(() => {
        setMobileMenuOpen(false);
    }, [location.pathname]);

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
                        <span className="logo-icon">📖</span>
                        <span className="logo-text">Book Lamp</span>
                    </Link>

                    {/* Desktop Navigation */}
                    <ul className="nav-links desktop-only">
                        {navItems.map((item) => (
                            <li key={item.path}>
                                <Link
                                    to={item.path}
                                    className={location.pathname === item.path ? 'active' : ''}
                                >
                                    {item.label}
                                </Link>
                            </li>
                        ))}
                    </ul>

                    <div className="nav-actions">
                        {/* Sync Status Indicator */}
                        <div className="sync-indicator" title={`Sync ${syncStatus}`}>
                            {syncStatus === 'ok' && (
                                <span className="sync-badge sync-ok">
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                        <polyline points="20 6 9 17 4 12"></polyline>
                                    </svg>
                                </span>
                            )}
                            {syncStatus === 'error' && (
                                <span className="sync-badge sync-error">
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                        <circle cx="12" cy="12" r="10"></circle>
                                        <line x1="12" y1="8" x2="12" y2="12"></line>
                                        <line x1="12" y1="16" x2="12.01" y2="16"></line>
                                    </svg>
                                </span>
                            )}
                        </div>

                        {/* Theme Selector */}
                        <div className="theme-selector">
                            <button
                                className="btn-icon"
                                onClick={() => setShowThemeMenu(!showThemeMenu)}
                                aria-label="Change theme"
                            >
                                {theme === 'dark' ? (
                                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                        <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
                                    </svg>
                                ) : theme === 'light' ? (
                                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                        <circle cx="12" cy="12" r="5"></circle>
                                        <line x1="12" y1="1" x2="12" y2="3"></line>
                                        <line x1="12" y1="21" x2="12" y2="23"></line>
                                        <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
                                        <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
                                        <line x1="1" y1="12" x2="3" y2="12"></line>
                                        <line x1="21" y1="12" x2="23" y2="12"></line>
                                        <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
                                        <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
                                    </svg>
                                ) : (
                                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                        <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>
                                        <line x1="8" y1="21" x2="16" y2="21"></line>
                                        <line x1="12" y1="17" x2="12" y2="21"></line>
                                    </svg>
                                )}
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

                        {/* Desktop Add Book Button */}
                        <Link to="/books/new" className="btn btn-primary desktop-only">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <line x1="12" y1="5" x2="12" y2="19"></line>
                                <line x1="5" y1="12" x2="19" y2="12"></line>
                            </svg>
                            Add Book
                        </Link>

                        {/* Mobile Menu Toggle */}
                        <button
                            className="btn-icon mobile-menu-toggle mobile-only"
                            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                            aria-label="Toggle menu"
                            aria-expanded={mobileMenuOpen}
                        >
                            {mobileMenuOpen ? (
                                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                    <line x1="18" y1="6" x2="6" y2="18"></line>
                                    <line x1="6" y1="6" x2="18" y2="18"></line>
                                </svg>
                            ) : (
                                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                    <line x1="3" y1="12" x2="21" y2="12"></line>
                                    <line x1="3" y1="6" x2="21" y2="6"></line>
                                    <line x1="3" y1="18" x2="21" y2="18"></line>
                                </svg>
                            )}
                        </button>
                    </div>
                </nav>

                {/* Mobile Navigation Menu */}
                {mobileMenuOpen && (
                    <div className="mobile-nav">
                        <ul>
                            {navItems.map((item) => (
                                <li key={item.path}>
                                    <Link
                                        to={item.path}
                                        className={location.pathname === item.path ? 'active' : ''}
                                    >
                                        {item.label}
                                    </Link>
                                </li>
                            ))}
                        </ul>
                        <Link to="/books/new" className="btn btn-primary mobile-nav-cta">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <line x1="12" y1="5" x2="12" y2="19"></line>
                                <line x1="5" y1="12" x2="19" y2="12"></line>
                            </svg>
                            Add Book
                        </Link>
                    </div>
                )}
            </header>

            {jobIndicator && (
                <div className="job-indicator" data-job-id={jobIndicator}>
                    <span className="spinner"></span>
                    Processing...
                </div>
            )}

            <main className="main-content">{children}</main>

            <footer className="site-footer">
                <div className="footer-content">
                    <p className="footer-brand">Book Lamp</p>
                    <p className="footer-copyright">&copy; {new Date().getFullYear()} — A personal reading companion</p>
                </div>
            </footer>
        </div>
    );
};

export default Layout;
