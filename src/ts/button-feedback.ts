/**
 * Button Feedback
 * Adds loading/disabled feedback for primary CTA buttons and links.
 */

export function initButtonFeedback(): void {
    const setLoading = (el: HTMLElement | HTMLButtonElement | HTMLAnchorElement): void => {
        if (!el) return;
        if (el.classList.contains('loading')) return;
        el.classList.add('loading');
        el.setAttribute('aria-busy', 'true');
        el.setAttribute('data-loading', 'true');
        try {
            (el as HTMLButtonElement).disabled = true;
        } catch (e) {
            // Ignore errors for non-button elements
        }
    };

    const handleFormSubmit = (e: Event): void => {
        const form = e.target as HTMLFormElement;
        const buttons = form.querySelectorAll<HTMLButtonElement | HTMLInputElement>(
            'button[type="submit"], input[type="submit"]'
        );
        buttons.forEach(setLoading);
    };

    const handleBodyClick = (e: MouseEvent): void => {
        const el = (e.target as HTMLElement).closest('a.btn, button.btn, .btn') as HTMLElement;
        if (!el) return;

        // If it's a link with target or external, skip
        if (el.tagName === 'A') {
            const anchor = el as HTMLAnchorElement;
            if (anchor.target && anchor.target !== '_self') return;

            try {
                const href = anchor.getAttribute('href');
                if (!href || href.startsWith('mailto:') || href.startsWith('tel:')) return;
                const url = new URL(href, window.location.origin);
                if (url.origin !== window.location.origin) return;
            } catch (err) {
                return;
            }
            setLoading(el);
            return;
        }

        // If button inside a form, let form submit handler manage it
        if (el.tagName === 'BUTTON' && (el as HTMLButtonElement).type === 'submit') return;

        setLoading(el);
    };

    const resetLoadingStates = (): void => {
        document.querySelectorAll<HTMLElement>('[data-loading="true"]').forEach((el) => {
            el.classList.remove('loading');
            el.removeAttribute('aria-busy');
            el.removeAttribute('data-loading');
            try {
                (el as HTMLButtonElement).disabled = false;
            } catch (e) {
                // Ignore
            }
        });
    };

    // Attach listeners
    document.querySelectorAll('form').forEach((f) => {
        f.addEventListener('submit', handleFormSubmit, { capture: true });
    });

    document.body.addEventListener('click', handleBodyClick);
    window.addEventListener('popstate', resetLoadingStates);
}

// Auto-init if not imported as a module (for backwards compatibility if needed, 
// though we'll use type="module" in the template)
if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initButtonFeedback);
    } else {
        initButtonFeedback();
    }
}
