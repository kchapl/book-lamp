import { describe, it, expect, vi, beforeEach } from 'vitest';
import { JobIndicator } from '../job-indicator.js';

describe('JobIndicator', () => {
    beforeEach(() => {
        document.body.innerHTML = `
      <div id="job-indicator" style="display: none;">
        <div id="job-progress-bar">
           <div id="job-progress-fill" style="width: 0%;"></div>
        </div>
        <div id="job-status-text"></div>
      </div>
      <div class="messages"></div>
    `;
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
            ok: true,
            json: () => Promise.resolve({ status: 'running', progress: 45, function_name: 'import_books' })
        }));
    });

    it('updates DOM on status change', async () => {
        const indicator = new JobIndicator('test-job');

        // Simulate start
        indicator.start();

        // Wait for the async check to complete
        // We need to wait for multiple microtasks because check() has multiple awaits
        await vi.waitFor(() => {
            const progressFill = document.getElementById('job-progress-fill');
            if (progressFill?.style.width !== '45%') throw new Error('Not updated yet');
        });

        const statusText = document.getElementById('job-status-text');
        const indicatorContainer = document.getElementById('job-indicator');

        expect(statusText?.textContent).toBe('Importing books...');
        expect(indicatorContainer?.style.display).toBe('block');
    });

    it('shows success alert on completion', async () => {
        vi.mocked(fetch).mockResolvedValueOnce({
            ok: true,
            json: () => Promise.resolve({
                status: 'completed',
                progress: 100,
                result: 'Imported 5 books'
            })
        } as Response);

        const indicator = new JobIndicator('test-job', { autoRefresh: false });
        indicator.start();

        await vi.waitFor(() => {
            if (!document.querySelector('.alert.success')) throw new Error('Alert not found');
        });

        const alert = document.querySelector('.alert.success');
        expect(alert?.textContent).toContain('Imported 5 books');
    });
});
