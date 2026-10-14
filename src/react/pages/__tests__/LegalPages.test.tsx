/**
 * The pages the Google OAuth consent screen links to.
 *
 * An app published to production must supply a homepage, a privacy policy and
 * terms, and the consent screen's checker arrives as an anonymous visitor — so
 * two halves matter: the wording states the data practices the link exists to
 * disclose, and each page is reachable at its own path with no session.
 */
import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import App from '../../App';
import PrivacyPage from '../PrivacyPage';
import TermsPage from '../TermsPage';

function response(body: unknown, status = 200) {
    return {
        ok: status >= 200 && status < 300,
        status,
        statusText: '',
        headers: { get: () => null },
        json: async () => body,
    } as unknown as Response;
}

beforeEach(() => {
    // jsdom implements no matchMedia, and App's theme effect reads it.
    window.matchMedia = ((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: () => {},
        removeListener: () => {},
        addEventListener: () => {},
        removeEventListener: () => {},
        dispatchEvent: () => false,
    })) as unknown as typeof window.matchMedia;

    vi.stubGlobal(
        'fetch',
        vi.fn(async (input: RequestInfo | URL) => {
            const url = String(input);

            if (url.includes('/api/sync/diagnostics')) {
                return response({ status: 'unauthenticated', message: '' });
            }
            if (url.includes('/api/auth/status')) {
                return response({ is_authenticated: false, user: null, google_client_id: 'test-client-id' });
            }
            return response({}, 404);
        })
    );
});

afterEach(() => {
    vi.unstubAllGlobals();
});

describe('the privacy policy', () => {
    it('states the Google data use and the Limited Use commitment', () => {
        render(<PrivacyPage />);

        expect(screen.getByRole('heading', { name: 'Privacy Policy' })).toBeInTheDocument();
        expect(screen.getByText(/Google API Services User Data Policy/)).toBeInTheDocument();
        expect(screen.getByText(/Limited Use requirements/)).toBeInTheDocument();
    });

    it('says where the recommendations feature sends the reader\'s books', () => {
        render(<PrivacyPage />);

        expect(screen.getByText(/language-model provider/)).toBeInTheDocument();
    });
});

describe('the terms', () => {
    it('links to the privacy policy', () => {
        render(<TermsPage />);

        expect(screen.getByRole('heading', { name: 'Terms of Service' })).toBeInTheDocument();
        expect(screen.getByRole('link', { name: 'Privacy Policy' })).toHaveAttribute('href', '/privacy');
    });
});

describe('reaching them without a session', () => {
    it.each([
        ['/privacy', 'Privacy Policy'],
        ['/terms', 'Terms of Service'],
    ])('serves %s to an anonymous visitor', async (path, heading) => {
        window.history.replaceState({}, '', path);

        render(<App />);

        await waitFor(() => expect(screen.getByRole('heading', { name: heading })).toBeInTheDocument());
    });
});
