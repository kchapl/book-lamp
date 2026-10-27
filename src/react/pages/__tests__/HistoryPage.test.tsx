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
import { render, waitFor } from '@testing-library/react';
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

/** The group headings, in the order the log draws them. */
const groupTitles = (container: HTMLElement) =>
    [...container.querySelectorAll('.group-title')].map((heading) => heading.textContent);

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
