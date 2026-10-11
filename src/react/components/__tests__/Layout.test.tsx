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
