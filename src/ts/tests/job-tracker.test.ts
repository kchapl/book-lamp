import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { JobTracker } from '../job-tracker.js';

describe('JobTracker', () => {
    beforeEach(() => {
        vi.useFakeTimers();
        localStorage.clear();
        vi.stubGlobal('fetch', vi.fn());
        vi.stubGlobal('location', { reload: vi.fn() });
    });

    afterEach(() => {
        vi.useRealTimers();
        vi.unstubAllGlobals();
    });

    it('starts polling on start', async () => {
        const tracker = new JobTracker('test-job');
        const fetchMock = vi.mocked(fetch);
        fetchMock.mockResolvedValueOnce({
            ok: true,
            json: () => Promise.resolve({ status: 'pending', progress: 0 })
        } as Response);

        tracker.start();

        expect(fetchMock).toHaveBeenCalledWith('/api/jobs/test-job');
        expect(localStorage.getItem(JobTracker.STORAGE_KEY)).toBe('test-job');
    });

    it('stops polling and reloads on completion', async () => {
        const onComplete = vi.fn();
        const tracker = new JobTracker('test-job', { onComplete });
        const fetchMock = vi.mocked(fetch);

        // Initial check
        fetchMock.mockResolvedValueOnce({
            ok: true,
            json: () => Promise.resolve({ status: 'completed', progress: 100 })
        } as Response);

        tracker.start();
        await vi.runOnlyPendingTimersAsync();

        expect(onComplete).toHaveBeenCalled();
        expect(localStorage.getItem(JobTracker.STORAGE_KEY)).toBeNull();

        // Auto-refresh logic (setTimeout 2000)
        vi.advanceTimersByTime(2000);
        expect(location.reload).toHaveBeenCalled();
    });

    it('handles job failure', async () => {
        const onError = vi.fn();
        const tracker = new JobTracker('test-job', { onError });
        const fetchMock = vi.mocked(fetch);

        fetchMock.mockResolvedValueOnce({
            ok: true,
            json: () => Promise.resolve({ status: 'failed', error: 'Something went wrong' })
        } as Response);

        tracker.start();
        await vi.runOnlyPendingTimersAsync();

        expect(onError).toHaveBeenCalledWith('Something went wrong');
        expect(localStorage.getItem(JobTracker.STORAGE_KEY)).toBeNull();
    });
});
