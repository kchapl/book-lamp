/**
 * Base UI Components
 * Methods for confirm modals, connections, and basic page-level logic.
 */

/**
 * Shows a confirmation modal before an action.
 */
export function showConfirm(title: string, message: string, onConfirm: () => void): void {
    const modal = document.getElementById('confirm-modal');
    if (!modal) return;

    const titleEl = document.getElementById('modal-title');
    const messageEl = document.getElementById('modal-message');
    if (titleEl) titleEl.textContent = title;
    if (messageEl) messageEl.textContent = message;

    const confirmBtn = document.getElementById('modal-confirm-btn');
    if (confirmBtn) {
        const newConfirmBtn = confirmBtn.cloneNode(true);
        confirmBtn.parentNode?.replaceChild(newConfirmBtn, confirmBtn);

        newConfirmBtn.addEventListener('click', () => {
            onConfirm();
            closeModal();
        });
    }

    modal.style.display = 'flex';
}

/**
 * Closes the confirmation modal.
 */
export function closeModal(): void {
    const modal = document.getElementById('confirm-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

/**
 * Submits a POST request to a given URL via a dynamically created form.
 */
export function submitPostRequest(urlStr: string): void {
    try {
        const url = new URL(urlStr, window.location.origin);
        if ((url.protocol === 'http:' || url.protocol === 'https:') &&
            url.origin === window.location.origin) {
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = url.toString();
            document.body.appendChild(form);
            form.submit();
        }
    } catch (e) {
        console.error('Failed to submit request:', e);
    }
}

/**
 * Toggles the Google Sheets connection status.
 */
export function toggleConnection(): void {
    const statusDot = document.getElementById('connection-status');
    if (!statusDot) return;

    const isAuthorised = statusDot.getAttribute('data-authorised') === 'true';
    if (isAuthorised) {
        showConfirm(
            'Disconnect Google Sheets',
            'Are you sure you want to disconnect? You will need to re-authorise to access your data.',
            () => { window.location.href = '/logout'; }
        );
    } else {
        showConfirm(
            'Authorise Google Sheets',
            'Would you like to authorise Google Sheets to store your reading data?',
            () => { window.location.href = '/connect'; }
        );
    }
}

/**
 * Initialises page-level UI logic such as alert auto-hiding.
 */
export function initBaseUI(): void {
    // 1. Alert Auto-hide Logic
    const alerts = document.querySelectorAll<HTMLElement>('.alert');
    alerts.forEach((alert) => {
        setTimeout(() => {
            alert.style.opacity = '0';
            alert.style.transform = 'translateY(-10px)';
            alert.style.transition = 'all 0.5s ease';
            setTimeout(() => alert.remove(), 500);
        }, 10000);
    });

    // 2. Click-outside modal listener
    window.addEventListener('click', (event: MouseEvent) => {
        const modal = document.getElementById('confirm-modal');
        if (event.target === modal) {
            closeModal();
        }
    });

    // 3. Global exposing of functions that might be called from templates
    // Note: We'll also update the templates to use modern event listeners where possible
    (window as any).showConfirm = showConfirm;
    (window as any).closeModal = closeModal;
    (window as any).submitPostRequest = submitPostRequest;
    (window as any).toggleConnection = toggleConnection;
}

// Auto-init for consistency
if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initBaseUI);
    } else {
        initBaseUI();
    }
}
