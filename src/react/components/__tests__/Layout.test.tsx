import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Layout from '../Layout';
import { AppContext } from '../../App';

const locationAssign = vi.fn();

beforeEach(() => {
    locationAssign.mockReset();
    vi.stubGlobal('location', { ...window.location, assign: locationAssign });
});

afterEach(() => {
    vi.unstubAllGlobals();
});

describe('Layout navigation', () => {
    const renderLayout = (path = '/') =>
        render(
            <MemoryRouter initialEntries={[path]}>
                <AppContext.Provider
                    value={{
                        theme: 'system',
                        setTheme: vi.fn(),
                        isAuthorized: true,
                        setIsAuthorized: vi.fn(),
                        googleClientId: null,
                        syncStatus: 'ok',
                        logoutUser: vi.fn(),
                    }}
                >
                    <Layout><div>Reading room</div></Layout>
                </AppContext.Provider>
            </MemoryRouter>
        );

    it('offers an Add Book entry point on every page', () => {
        const { container } = renderLayout();

        const addBook = container.querySelector('nav[aria-label="Primary"] a[href="/books/new"]');

        expect(addBook).toBeInTheDocument();
        expect(addBook).toHaveTextContent(/add book/i);
    });

    it('marks only the most specific nav entry current on the Add Book page', () => {
        // `/books/new` sits under `/books`; both used to match, so both links
        // claimed the page.
        const { container } = renderLayout('/books/new');

        const current = container.querySelectorAll('nav[aria-label="Primary"] a[aria-current="page"]');

        expect(current).toHaveLength(1);
        expect(current[0]).toHaveAttribute('href', '/books/new');
    });
});

describe('Layout data export', () => {
    it('offers an authenticated reader a CSV export action', () => {
        const { container } = render(
            <MemoryRouter>
                <AppContext.Provider
                    value={{
                        theme: 'system',
                        setTheme: vi.fn(),
                        isAuthorized: true,
                        setIsAuthorized: vi.fn(),
                        googleClientId: null,
                        syncStatus: 'ok',
                        logoutUser: vi.fn(),
                    }}
                >
                    <Layout><div>Reading room</div></Layout>
                </AppContext.Provider>
            </MemoryRouter>
        );

        fireEvent.click(container.querySelector('md-text-button[aria-label="Export my data as CSV"]') as HTMLElement);

        expect(locationAssign).toHaveBeenCalledWith('/api/export/csv');
    });

    it('does not offer a private data export to signed-out visitors', () => {
        const { container } = render(
            <MemoryRouter>
                <AppContext.Provider
                    value={{
                        theme: 'system',
                        setTheme: vi.fn(),
                        isAuthorized: false,
                        setIsAuthorized: vi.fn(),
                        googleClientId: null,
                        syncStatus: 'checking',
                        logoutUser: vi.fn(),
                    }}
                >
                    <Layout><div>Reading room</div></Layout>
                </AppContext.Provider>
            </MemoryRouter>
        );

        expect(container.querySelector('md-text-button[aria-label="Export my data as CSV"]')).not.toBeInTheDocument();
    });
});
