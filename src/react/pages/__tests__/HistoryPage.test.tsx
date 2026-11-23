/**
 * The Reading Log's grouping.
 *
 * The log arrives from the API already in the order the chosen sort asked for,
 * and the page groups it by Book for display. Keying those groups by title
 * enqueued integer-like titles first — a Book called "1983" was drawn above a
 * newer Reading whatever the sort — and folded two Books that share a title into
 * one group. These tests pin the order, the separation, and the grouping.
 */
import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import HistoryPage from '../HistoryPage';
import { getHistory } from '../../services/api';
import type { Reading } from '../../types';

vi.mock('../../services/api', () => ({
    getHistory: vi.fn(),
}));

const history = vi.mocked(getHistory);

/** A Reading as the API returns it, with only what a test cares about set. */
function reading(overrides: Partial<Reading> & { id: number; book_id: number }): Reading {
    return {
        status: 'Completed',
        start_date: '2024-01-01',
        ...overrides,
    };
}

/** A history response carrying no filters, as the page only renders the log. */
const response = (records: Reading[]) => ({
    history: records,
    statuses: [],
    filters: { status: '', min_rating: 0, year: '', sort: 'date_desc' },
});

const renderPage = () =>
    render(
        <MemoryRouter initialEntries={['/history']}>
            <HistoryPage />
        </MemoryRouter>
    );

/** The exhibits' headings, in the order the log draws them. */
const groupTitles = (container: HTMLElement) =>
    [...container.querySelectorAll('.history-group .exhibit-title')].map((heading) => heading.textContent);

/** The readings drawn under each group heading. */
const recordCounts = (container: HTMLElement) =>
    [...container.querySelectorAll('.history-group')].map(
        (group) => group.querySelectorAll('.history-record').length
    );

beforeEach(() => {
    vi.clearAllMocks();
});

describe('HistoryPage grouping', () => {
    it('keeps the API order when a title looks like a number', async () => {
        history.mockResolvedValue(
            response([
                reading({ id: 1, book_id: 10, book_title: 'A Recent Book', start_date: '2026-10-01' }),
                reading({ id: 2, book_id: 11, book_title: '1983', start_date: '2019-07-01' }),
            ])
        );

        const { container } = renderPage();

        await waitFor(() => expect(groupTitles(container)).toHaveLength(2));
        expect(groupTitles(container)).toEqual(['A Recent Book', '1983']);
    });

    it('keeps two Books that share a title apart', async () => {
        history.mockResolvedValue(
            response([
                reading({ id: 1, book_id: 10, book_title: 'Collected Poems' }),
                reading({ id: 2, book_id: 11, book_title: 'Collected Poems' }),
            ])
        );

        const { container } = renderPage();

        await waitFor(() => expect(groupTitles(container)).toHaveLength(2));
        expect(groupTitles(container)).toEqual(['Collected Poems', 'Collected Poems']);
        expect(recordCounts(container)).toEqual([1, 1]);
    });

    it('mounts a Book as an exhibit with its stored details and formatted dates', async () => {
        history.mockResolvedValue(
            response([
                reading({
                    id: 1,
                    book_id: 10,
                    book_title: 'Piranesi: A Novel',
                    book_title_main: 'Piranesi',
                    book_subtitle: 'A Novel',
                    book_author: 'Susanna Clarke',
                    book_publication_year: 2020,
                    latest_status: 'Completed',
                    status: 'Completed',
                    start_date: '2024-03-01',
                    end_date: '2024-03-20',
                }),
            ])
        );

        const { container } = renderPage();

        await waitFor(() =>
            expect(screen.getByRole('heading', { name: 'Piranesi' })).toBeTruthy()
        );
        expect(screen.getByText('A Novel')).toBeTruthy();
        expect(screen.getByText('Susanna Clarke')).toBeTruthy();
        expect(container.querySelector('.history-book .exhibit-accession')?.textContent).toBe('2020');
        // The Reading row states the status; the exhibit above it does not repeat it.
        expect(container.querySelector('.history-book .exhibit-meta')).toBeNull();
        expect(container.querySelector('.history-record .status-badge')?.textContent).toBe('Completed');

        const dates = container.querySelector('.history-record .dates')?.textContent ?? '';
        expect(dates).toContain('Mar');
        expect(dates).not.toContain('2024-03-01');
    });

    it("states each Reading's status only on its own row", async () => {
        history.mockResolvedValue(
            response([
                reading({ id: 1, book_id: 10, book_title: 'Dune', status: 'In Progress', latest_status: 'In Progress' }),
                reading({ id: 2, book_id: 10, book_title: 'Dune', status: 'Completed', latest_status: 'In Progress' }),
            ])
        );

        const { container } = renderPage();

        await waitFor(() => expect(groupTitles(container)).toHaveLength(1));
        expect(container.querySelector('.history-book .exhibit-meta')).toBeNull();
        const rowStatuses = [...container.querySelectorAll('.history-record .status-badge')].map(
            (badge) => badge.textContent
        );
        expect(rowStatuses).toEqual(['In Progress', 'Completed']);
    });

    it("gathers one Book's Readings under a single heading", async () => {
        history.mockResolvedValue(
            response([
                reading({ id: 1, book_id: 10, book_title: 'Dune', status: 'Completed' }),
                reading({ id: 2, book_id: 10, book_title: 'Dune', status: 'In Progress' }),
            ])
        );

        const { container } = renderPage();

        await waitFor(() => expect(groupTitles(container)).toHaveLength(1));
        expect(groupTitles(container)).toEqual(['Dune']);
        expect(recordCounts(container)).toEqual([2]);
    });
});
