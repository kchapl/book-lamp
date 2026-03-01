import { describe, it, expect, vi, beforeEach } from 'vitest';
import { showConfirm, submitPostRequest, toggleConnection } from '../base-ui.js';

describe('base-ui', () => {
    beforeEach(() => {
        document.body.innerHTML = `
      <div id="confirm-modal" style="display: none;">
        <h2 id="modal-title"></h2>
        <p id="modal-message"></p>
        <div class="modal-actions">
          <button id="modal-confirm-btn"></button>
        </div>
      </div>
      <span id="connection-status" data-authorised="false"></span>
    `;
        // Ensure origin is set for JSDOM
        vi.stubGlobal('location', new URL('http://localhost'));
    });

    it('showConfirm displays modal and handles confirmation', () => {
        const onConfirm = vi.fn();
        showConfirm('Test Title', 'Test Msg', onConfirm);

        const modal = document.getElementById('confirm-modal');
        const title = document.getElementById('modal-title');
        const confirmBtn = document.getElementById('modal-confirm-btn');

        expect(modal?.style.display).toBe('flex');
        expect(title?.textContent).toBe('Test Title');

        confirmBtn?.click();
        expect(onConfirm).toHaveBeenCalled();
        expect(modal?.style.display).toBe('none');
    });

    it('submitPostRequest creates a form in the body', () => {
        const submitSpy = vi.spyOn(HTMLFormElement.prototype, 'submit').mockImplementation(() => { });

        // Use relative path which should be resolved against localhost
        submitPostRequest('/test-url');

        const form = document.querySelector('form');
        expect(form).not.toBeNull();
        expect(form?.action).toContain('/test-url');
        expect(form?.method).toBe('post');
        expect(submitSpy).toHaveBeenCalled();
    });

    it('toggleConnection shows confirm before logout', () => {
        const statusDot = document.getElementById('connection-status');
        statusDot?.setAttribute('data-authorised', 'true');

        toggleConnection();

        const title = document.getElementById('modal-title');
        expect(title?.textContent).toBe('Disconnect Google Sheets');
    });
});
