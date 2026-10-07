import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import StatsPage from '../StatsPage';
import { getStats, getBooks } from '../../services/api';

vi.mock('../../services/api', () => ({
    getStats: vi.fn(),
    getBooks: vi.fn(),
}));

const mockStats = {
    total_books: 6,
    total_authors: 4,
    total_records: 12,
    avg_rating: 4.2,
    status_counts: { Completed: 6, 'In Progress': 2, Abandoned: 2 },
    rating_distribution: [
        [5, 3],
        [4, 2],
        [3, 1],
        [2, 0],
        [1, 0],
    ],
    top_authors: [{ name: 'Ursula K. Le Guin', count: 3 }],
    top_publishers: [{ name: 'Penguin', count: 2 }],
    category_distribution: [],
    max_category_count: 1,
    yearly_counts: [['2024', 6]] as [string, number][],
    max_year_count: 6,
    monthly_counts: [{ index: 3, name: 'Mar', count: 6 }],
    max_month_count: 6,
    total_pages_read: 1800,
    avg_pages_per_book: 300,
    avg_reading_time_days: 14,
    total_reading_days: 84,
    books_this_year: 6,
    yearly_goal: null,
    format_distribution: [],
    language_distribution: [],
    top_series: [],
    category_details: [],
    year_comparison: { current_year: 2024, previous_year: 0, percentage_change: 100 },
    reading_pace_monthly: 0.5,
    reading_pace_annualised: 6,
    last_record_date: '2024-03-10',
};

const renderPage = () =>
    render(
        <MemoryRouter>
            <StatsPage />
        </MemoryRouter>
    );

beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getStats).mockResolvedValue(mockStats as never);
    vi.mocked(getBooks).mockResolvedValue({ books: [] } as never);
});

describe('StatsPage reading-status board', () => {
    it('computes status shares against every status, not just completed books', async () => {
        renderPage();

        // 6 completed, 2 in progress, 2 abandoned => 10 books carry a status.
        // Completed is 60% and In Progress is 20%; both must reflect that.
        await waitFor(() => {
            expect(screen.getByText('Completed')).toBeInTheDocument();
        });
        expect(screen.getByText('60%')).toBeInTheDocument();
        // In Progress and Abandoned are both 2 of 10 books.
        expect(screen.getAllByText('20%')).toHaveLength(2);
    });

    it('states when the collection was last updated instead of implying a live feed', async () => {
        renderPage();

        const asOf = await screen.findByTitle(/most recent reading record/i);
        expect(asOf).toHaveTextContent(/Last entry/);
        expect(asOf).toHaveTextContent(/2024/);
        expect(screen.queryByText(/streak/i)).not.toBeInTheDocument();
    });

    it('mounts the books currently in progress on the lectern', async () => {
        vi.mocked(getBooks).mockResolvedValue({
            books: [{ id: 1, title: 'The Dispossessed', author: 'A Lectern Author' }],
        } as never);

        renderPage();

        await waitFor(() => {
            expect(screen.getByText('The Dispossessed')).toBeInTheDocument();
        });
        expect(screen.getByText('A Lectern Author')).toBeInTheDocument();
    });

    it('shows an empty lectern when nothing is in progress', async () => {
        renderPage();

        await waitFor(() => {
            expect(screen.getByText(/Nothing on the lectern/)).toBeInTheDocument();
        });
    });
});
