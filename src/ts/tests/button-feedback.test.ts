import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { initButtonFeedback } from '../button-feedback.js';

describe('button-feedback', () => {
    const preventNavigation = (e: MouseEvent) => {
        if ((e.target as HTMLElement).closest('a')) {
            e.preventDefault();
        }
    };

    beforeEach(() => {
        document.body.innerHTML = `
      <form id="test-form">
        <button type="submit" id="submit-btn" class="btn">Submit</button>
      </form>
      <button type="button" id="toggle-btn" class="btn">Toggle</button>
      <button type="button" id="post-btn" class="btn" data-feedback="true">Post</button>
      <a href="/books" id="link-btn" class="btn">Books</a>
      <a href="https://external.com" id="ext-link" class="btn">External</a>
    `;
        document.body.addEventListener('click', preventNavigation);
        initButtonFeedback();
    });

    afterEach(() => {
        document.body.removeEventListener('click', preventNavigation);
        document.body.innerHTML = '';
    });

    it('sets loading state on form submit', () => {
        const form = document.getElementById('test-form') as HTMLFormElement;
        const btn = document.getElementById('submit-btn') as HTMLButtonElement;

        form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));

        expect(btn.classList.contains('loading')).toBe(true);
        expect(btn.getAttribute('aria-busy')).toBe('true');
        expect(btn.disabled).toBe(true);
    });

    it('sets loading state on internal link click', () => {
        const link = document.getElementById('link-btn') as HTMLAnchorElement;

        link.click();

        expect(link.classList.contains('loading')).toBe(true);
        expect(link.getAttribute('data-loading')).toBe('true');
    });

    it('does NOT set loading on external link click', () => {
        const link = document.getElementById('ext-link') as HTMLAnchorElement;

        link.click();

        expect(link.classList.contains('loading')).toBe(false);
    });

    it('does NOT set loading on plain buttons', () => {
        const button = document.getElementById('toggle-btn') as HTMLButtonElement;

        button.click();

        expect(button.classList.contains('loading')).toBe(false);
        expect(button.disabled).toBe(false);
    });

    it('sets loading on plain buttons that opt in to feedback', () => {
        const button = document.getElementById('post-btn') as HTMLButtonElement;

        button.click();

        expect(button.classList.contains('loading')).toBe(true);
        expect(button.disabled).toBe(true);
    });

    it('resets loading state on popstate', () => {
        const btn = document.getElementById('submit-btn') as HTMLButtonElement;
        btn.classList.add('loading');
        btn.setAttribute('data-loading', 'true');
        btn.disabled = true;

        window.dispatchEvent(new PopStateEvent('popstate'));

        expect(btn.classList.contains('loading')).toBe(false);
        expect(btn.disabled).toBe(false);
    });
});
