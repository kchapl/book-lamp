/**
 * The About page reports the commit the server is running, so a reader can tell
 * which deploy they are looking at.
 */
import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import AboutPage from '../AboutPage';
import { getAppInfo } from '../../services/api';

vi.mock('../../services/api', () => ({
    getAppInfo: vi.fn(),
}));

const appInfo = vi.mocked(getAppInfo);

beforeEach(() => {
    vi.clearAllMocks();
});

describe('AboutPage', () => {
    it('shows the short commit the server reports', async () => {
        appInfo.mockResolvedValue({ version: 'abc1234' });

        render(<AboutPage />);

        expect(await screen.findByText('Version: abc1234')).toBeInTheDocument();
    });

    it('says the version is unknown when the deployment does not answer', async () => {
        appInfo.mockRejectedValue(new Error('offline'));

        render(<AboutPage />);

        expect(await screen.findByText('Version: unknown')).toBeInTheDocument();
    });
});
