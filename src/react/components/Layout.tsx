import React, { useContext, useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { AppContext } from '../App';
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

const Layout: React.FC<LayoutProps> = ({ children }) => {
    const { theme, setTheme, syncStatus, isAuthorized, logoutUser } = useContext(AppContext);
    const [showThemeMenu, setShowThemeMenu] = useState(false);
    const [jobIndicator, setJobIndicator] = useState<string | null>(null);
    const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
    const location = useLocation();

    useEffect(() => {
        const params = new URLSearchParams(window.location.search);
        const jobId = params.get('job_id');
        if (jobId) {
            setJobIndicator(jobId);
        }
    }, [location]);

    useEffect(() => {
        // A route change always closes the mobile menu.
        setMobileMenuOpen(false);
        setShowThemeMenu(false);
    }, [location.pathname]);

    const isActive = (path: string) =>
        path === '/' ? location.pathname === '/' : location.pathname.startsWith(path);

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

                    <IconButton
                        icon={mobileMenuOpen ? 'close' : 'menu'}
                        className="mobile-menu-toggle"
                        onClick={() => setMobileMenuOpen((open) => !open)}
                        aria-label={mobileMenuOpen ? 'Close menu' : 'Open menu'}
                        aria-expanded={mobileMenuOpen}
                    />

                    <ul className={`nav-links ${mobileMenuOpen ? 'nav-open' : ''}`}>
                        {NAV_ITEMS.map((item) => (
                            <li key={item.path}>
                                <Link
                                    to={item.path}
                                    className={isActive(item.path) ? 'active' : ''}
                                    aria-current={isActive(item.path) ? 'page' : undefined}
                                >
                                    <Icon name={item.icon} size="sm" />
                                    {item.label}
                                </Link>
                            </li>
                        ))}
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
                                icon={theme === 'dark' ? 'moon' : theme === 'light' ? 'sun' : 'monitor'}
                                onClick={() => setShowThemeMenu((open) => !open)}
                                aria-label="Change theme"
                                aria-expanded={showThemeMenu}
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
                            <Button variant="text" onClick={logoutUser} aria-label="Sign out">
                                <span className="btn-label">Sign out</span>
                            </Button>
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

            {jobIndicator && (
                <div className="job-indicator" data-job-id={jobIndicator} role="status">
                    <span className="spinner" aria-hidden="true" />
                    Preparing metadata…
                </div>
            )}

            <main className="main-content">{children}</main>

            <footer className="site-footer">
                <p>Book Lamp &copy; {new Date().getFullYear()}</p>
            </footer>
        </div>
    );
};

export default Layout;
