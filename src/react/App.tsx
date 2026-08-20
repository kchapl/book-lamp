import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import HomePage from './pages/HomePage';
import BooksPage from './pages/BooksPage';
import BookDetailPage from './pages/BookDetailPage';
import AddBookPage from './pages/AddBookPage';
import ImportBooksPage from './pages/ImportBooksPage';
import HistoryPage from './pages/HistoryPage';
import ReadingListPage from './pages/ReadingListPage';
import StatsPage from './pages/StatsPage';
import AuthorPage from './pages/AuthorPage';
import PublisherPage from './pages/PublisherPage';
import AboutPage from './pages/AboutPage';
import UnauthorisedPage from './pages/UnauthorisedPage';
import { getSyncDiagnostics } from './services/api';

export interface AppContextType {
    theme: 'light' | 'dark' | 'system';
    setTheme: (theme: 'light' | 'dark' | 'system') => void;
    isAuthorized: boolean;
    syncStatus: 'ok' | 'error' | 'checking';
}

export const AppContext = React.createContext<AppContextType>({
    theme: 'system',
    setTheme: () => {},
    isAuthorized: false,
    syncStatus: 'checking',
});

function App() {
    const [theme, setTheme] = useState<'light' | 'dark' | 'system'>('system');
    const [isAuthorized, setIsAuthorized] = useState(false);
    const [syncStatus, setSyncStatus] = useState<'ok' | 'error' | 'checking'>('checking');

    useEffect(() => {
        // Check authorization status
        const storedTheme = localStorage.getItem('theme') as 'light' | 'dark' | 'system' | null;
        if (storedTheme && ['light', 'dark', 'system'].includes(storedTheme)) {
            setTheme(storedTheme);
        }

        // Check sync status
        const checkSync = async () => {
            try {
                const diagnostics = await getSyncDiagnostics();
                setSyncStatus(diagnostics.status === 'ok' ? 'ok' : 'error');
            } catch {
                setSyncStatus('error');
            }
        };

        checkSync();
        const interval = setInterval(checkSync, 60000);
        return () => clearInterval(interval);
    }, []);

    useEffect(() => {
        const root = document.documentElement;
        if (theme === 'dark') {
            root.setAttribute('data-theme', 'dark');
        } else if (theme === 'light') {
            root.removeAttribute('data-theme');
        } else {
            const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            if (prefersDark) {
                root.setAttribute('data-theme', 'dark');
            } else {
                root.removeAttribute('data-theme');
            }
        }
    }, [theme]);

    const handleThemeChange = (newTheme: 'light' | 'dark' | 'system') => {
        setTheme(newTheme);
        localStorage.setItem('theme', newTheme);
    };

    return (
        <AppContext.Provider
            value={{
                theme,
                setTheme: handleThemeChange,
                isAuthorized,
                syncStatus,
            }}
        >
            <BrowserRouter>
                <Layout>
                    <Routes>
                        <Route path="/" element={<HomePage />} />
                        <Route path="/books" element={<BooksPage />} />
                        <Route path="/books/new" element={<AddBookPage />} />
                        <Route path="/books/import" element={<ImportBooksPage />} />
                        <Route path="/books/:bookId" element={<BookDetailPage />} />
                        <Route path="/history" element={<HistoryPage />} />
                        <Route path="/reading-list" element={<ReadingListPage />} />
                        <Route path="/dashboard" element={<StatsPage />} />
                        <Route path="/stats" element={<Navigate to="/dashboard" replace />} />
                        <Route path="/author/:authorSlug" element={<AuthorPage />} />
                        <Route path="/publisher/:publisherSlug" element={<PublisherPage />} />
                        <Route path="/about" element={<AboutPage />} />
                        <Route path="/unauthorised" element={<UnauthorisedPage />} />
                        <Route path="*" element={<Navigate to="/" replace />} />
                    </Routes>
                </Layout>
            </BrowserRouter>
        </AppContext.Provider>
    );
}

export default App;