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

describe('Layout account menu', () => {
    const renderLayout = (isAuthorized = true) => {
        const logoutUser = vi.fn();
        const utils = render(
            <MemoryRouter>
                <AppContext.Provider
                    value={{
                        theme: 'system',
                        setTheme: vi.fn(),
                        isAuthorized,
                        setIsAuthorized: vi.fn(),
                        googleClientId: null,
                        syncStatus: 'ok',
                        logoutUser,
                    }}
                >
                    <Layout><div>Reading room</div></Layout>
                </AppContext.Provider>
            </MemoryRouter>
        );
        return { ...utils, logoutUser };
    };

    const trigger = (container: HTMLElement) =>
        container.querySelector('md-text-button[aria-label="Account"]') as HTMLElement | null;
    const exportItem = (container: HTMLElement) =>
        container.querySelector('md-text-button[aria-label="Export my data as CSV"]') as HTMLElement | null;
    const signOutItem = (container: HTMLElement) =>
        container.querySelector('md-text-button[aria-label="Sign out"]') as HTMLElement | null;

    const openMenu = (container: HTMLElement) => {
        fireEvent.click(trigger(container) as HTMLElement);
    };

    it('keeps the export out of the nav until the account menu is open', () => {
        const { container } = renderLayout();

        expect(exportItem(container)).not.toBeInTheDocument();

        openMenu(container);

        expect(exportItem(container)).toBeInTheDocument();
    });

    it('downloads the CSV from the account menu', () => {
        const { container } = renderLayout();
        openMenu(container);

        fireEvent.click(exportItem(container) as HTMLElement);

        expect(locationAssign).toHaveBeenCalledWith('/api/export/csv');
    });

    it('signs out from the account menu', () => {
        const { container, logoutUser } = renderLayout();
        openMenu(container);

        fireEvent.click(signOutItem(container) as HTMLElement);

        expect(logoutUser).toHaveBeenCalledTimes(1);
    });

    it('reports whether the menu is open on its trigger', () => {
        const { container } = renderLayout();

        expect(trigger(container)).toHaveAttribute('aria-haspopup', 'menu');
        expect(trigger(container)).toHaveAttribute('aria-expanded', 'false');

        openMenu(container);

        expect(trigger(container)).toHaveAttribute('aria-expanded', 'true');
    });

    it('closes the account menu on Escape', () => {
        const { container } = renderLayout();
        openMenu(container);

        fireEvent.keyDown(document, { key: 'Escape' });

        expect(exportItem(container)).not.toBeInTheDocument();
        expect(trigger(container)).toHaveAttribute('aria-expanded', 'false');
    });

    it('closes the account menu when the reader clicks elsewhere', () => {
        const { container } = renderLayout();
        openMenu(container);

        fireEvent.mouseDown(document.body);

        expect(exportItem(container)).not.toBeInTheDocument();
    });

    it('offers signed-out visitors no account menu, export or sign out', () => {
        const { container } = renderLayout(false);

        expect(trigger(container)).not.toBeInTheDocument();
        expect(exportItem(container)).not.toBeInTheDocument();
        expect(signOutItem(container)).not.toBeInTheDocument();
    });
});
