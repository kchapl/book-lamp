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
export function submitPostRequest(urlStr: string, data: Record<string, string> = {}): void {
    try {
        const url = new URL(urlStr, window.location.origin);
        if ((url.protocol === 'http:' || url.protocol === 'https:') &&
            url.origin === window.location.origin) {
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = url.toString();

            // Add hidden inputs for each data field
            Object.entries(data).forEach(([key, value]) => {
                const input = document.createElement('input');
                input.type = 'hidden';
                input.name = key;
                input.value = value;
                form.appendChild(input);
            });

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
            alert.style.transition = 'opacity 0.5s ease';
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

    // 3. Settings Dropdown Logic
    const settingsToggle = document.getElementById('settings-toggle');
    const settingsDropdown = document.getElementById('settings-dropdown');
    
    if (settingsToggle && settingsDropdown) {
        settingsToggle.addEventListener('click', (e) => {
            e.stopPropagation();
            settingsDropdown.classList.toggle('show');
        });

        // Close dropdown when clicking outside
        window.addEventListener('click', (e) => {
            if (!settingsToggle.contains(e.target as Node) && !settingsDropdown.contains(e.target as Node)) {
                settingsDropdown.classList.remove('show');
            }
        });
    }

    // 4. Theme Switching Logic
    const themeRadios = document.querySelectorAll<HTMLInputElement>('input[name="theme"]');
    themeRadios.forEach(radio => {
        radio.addEventListener('change', () => {
            const theme = radio.value;
            
            // Apply theme immediately for better UX
            const html = document.documentElement;
            if (theme === 'system') {
                html.setAttribute('data-theme', 'system');
            } else {
                html.setAttribute('data-theme', theme);
            }

            // Persist theme choice to Google Sheets
            fetch('/api/settings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ theme: theme }),
            }).catch(err => console.error('Failed to save theme setting:', err));
        });
    });

    // 5. Global exposing of functions that might be called from templates
    // Note: We'll also update the templates to use modern event listeners where possible
    initSyncHealthBadge();
    (window as any).showConfirm = showConfirm;
    (window as any).closeModal = closeModal;
    (window as any).submitPostRequest = submitPostRequest;
    (window as any).toggleConnection = toggleConnection;
}

function initSyncHealthBadge(): void {
    const badge = document.getElementById('sync-health-badge');
    const statusDot = document.getElementById('connection-status');
    if (!badge || !statusDot) return;

    const isAuthorised = statusDot.getAttribute('data-authorised') === 'true';
    if (!isAuthorised) {
        badge.classList.add('hidden');
        return;
    }

    const render = (mode: 'ok' | 'warning' | 'error', text: string): void => {
        badge.classList.remove('hidden', 'sync-ok', 'sync-warning', 'sync-error');
        if (mode === 'ok') badge.classList.add('sync-ok');
        if (mode === 'warning') badge.classList.add('sync-warning');
        if (mode === 'error') badge.classList.add('sync-error');
        badge.textContent = text;
    };

    const poll = async (): Promise<void> => {
        try {
            const resp = await fetch('/api/sync/diagnostics');
            if (!resp.ok) {
                badge.classList.add('hidden');
                return;
            }

            const data = await resp.json();
            if (!data || data.enabled === false) {
                badge.classList.add('hidden');
                return;
            }

            const failed = Number(data?.outbox?.failed ?? 0);
            const pending = Number(data?.outbox?.pending ?? 0);
            if (failed > 0) {
                render('error', `Sync issues: ${failed}`);
            } else if (pending > 0) {
                render('warning', `Syncing ${pending}`);
            } else {
                render('ok', 'Synced');
            }
        } catch {
            badge.classList.add('hidden');
        }
    };

    void poll();
    window.setInterval(() => {
        void poll();
    }, 15000);
}

// Auto-init for consistency
if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initBaseUI);
    } else {
        initBaseUI();
    }
}
