import { describe, it, expect, vi, beforeEach } from 'vitest';
import { saveOrder } from '../reading-list.js';

describe('reading-list', () => {
    beforeEach(() => {
        document.body.innerHTML = `
      <div id="reading-list-container" data-reorder-url="/api/reorder">
        <div class="draggable-item" data-book-id="1">Book 1</div>
        <div class="draggable-item" data-book-id="2">Book 2</div>
      </div>
    `;
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }));
    });

    it('saveOrder collects IDs and sends reorder request', async () => {
        const list = document.getElementById('reading-list-container')!;

        saveOrder(list, '/api/reorder');

        expect(fetch).toHaveBeenCalledWith('/api/reorder', expect.objectContaining({
            method: 'POST',
            body: JSON.stringify({ book_ids: [1, 2] })
        }));
    });
});
