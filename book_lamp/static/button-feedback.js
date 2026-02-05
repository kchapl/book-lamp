// Adds loading/disabled feedback for primary CTA buttons and links
(function () {
    function setLoading(el) {
        if (!el) return;
        if (el.classList.contains('loading')) return;
        el.classList.add('loading');
        el.setAttribute('aria-busy', 'true');
        el.setAttribute('data-loading', 'true');
        try { el.disabled = true; } catch (e) {}
    }

    function handleFormSubmit(e) {
        var form = e.target;
        // find submit buttons within form
        var buttons = form.querySelectorAll('button[type="submit"], input[type="submit"]');
        buttons.forEach(setLoading);
    }

    function handleBodyClick(e) {
        var el = e.target.closest('a.btn, button.btn, .btn');
        if (!el) return;

        // If it's a link with target or external, skip
        if (el.tagName === 'A') {
            if (el.target && el.target !== '_self') return;
            // external link (different origin) - skip
            try {
                var href = el.getAttribute('href');
                if (!href || href.startsWith('mailto:') || href.startsWith('tel:')) return;
                var url = new URL(href, window.location.origin);
                if (url.origin !== window.location.origin) return;
            } catch (err) {
                // ignore bad URLs
                return;
            }
            setLoading(el);
            return; // allow navigation to continue
        }

        // If button inside a form, let form submit handler manage it
        if (el.tagName === 'BUTTON' && el.type === 'submit') return;

        // For JS-handled buttons, mark loading and prevent double clicks
        setLoading(el);
    }

    document.addEventListener('DOMContentLoaded', function () {
        // Attach submit listener to all forms to mark submit buttons as loading
        document.querySelectorAll('form').forEach(function (f) {
            f.addEventListener('submit', handleFormSubmit, { capture: true });
        });

        // Global click handler for .btn elements to show immediate feedback
        document.body.addEventListener('click', handleBodyClick);

        // If navigation cancels (e.g. SPA), observe and clear loading state on popstate
        window.addEventListener('popstate', function () {
            document.querySelectorAll('[data-loading="true"]').forEach(function (el) {
                el.classList.remove('loading');
                el.removeAttribute('aria-busy');
                el.removeAttribute('data-loading');
                try { el.disabled = false; } catch (e) {}
            });
        });
    });
})();
