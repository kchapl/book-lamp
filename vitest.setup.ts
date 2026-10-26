// jest-dom matchers (toBeInTheDocument, toHaveStyle, ...) for every test file.
import '@testing-library/jest-dom/vitest';

/**
 * jsdom implements `attachInternals()`, but only part of `ElementInternals`:
 * the form-association surface Material Web's behaviors call while a component
 * initialises (`setFormValue`, `setValidity`, and reading `validity`) is
 * missing. Without it every text field, select and button throws on upgrade.
 *
 * This fills in the shared prototype once, so it applies to every element.
 * It is an environment shim, not a stand-in for the behaviour under test: the
 * wrappers are asserted against their real events and properties below.
 */
function shimElementInternals(): void {
    if (typeof HTMLElement.prototype.attachInternals !== 'function') return;

    // attachInternals() refuses anything that is not a defined custom element,
    // so borrow the prototype from a throwaway one.
    const probeTag = 'element-internals-probe';
    if (!customElements.get(probeTag)) {
        customElements.define(probeTag, class extends HTMLElement {});
    }

    let internals: ElementInternals;
    try {
        internals = document.createElement(probeTag).attachInternals();
    } catch {
        return;
    }

    const proto = Object.getPrototypeOf(internals) as Record<string, unknown>;
    const noop = () => {};

    for (const method of ['setFormValue', 'setValidity', 'checkValidity', 'reportValidity']) {
        if (typeof proto[method] !== 'function') {
            Object.defineProperty(proto, method, {
                configurable: true,
                writable: true,
                value: method === 'checkValidity' || method === 'reportValidity' ? () => true : noop,
            });
        }
    }

    if (!proto.validity) {
        Object.defineProperty(proto, 'validity', {
            configurable: true,
            get: () => ({ valid: true }),
        });
    }

    if (!proto.states) {
        Object.defineProperty(proto, 'states', {
            configurable: true,
            get: () => new Set<string>(),
        });
    }
}

shimElementInternals();

/**
 * jsdom has no `IntersectionObserver`, and Material Web's dialog creates one
 * while it initialises to measure where it sits on screen. Without it, any
 * component that renders a dialog rejects asynchronously on first paint.
 *
 * This is a no-op observer: nothing under test depends on the callback firing.
 */
function shimIntersectionObserver(): void {
    if ('IntersectionObserver' in globalThis) return;

    class NoopIntersectionObserver {
        readonly root = null;
        readonly rootMargin = '';
        readonly thresholds: readonly number[] = [];

        observe(): void {}
        unobserve(): void {}
        disconnect(): void {}
        takeRecords(): IntersectionObserverEntry[] {
            return [];
        }
    }

    globalThis.IntersectionObserver = NoopIntersectionObserver as unknown as typeof IntersectionObserver;
}

shimIntersectionObserver();

/**
 * jsdom ships `HTMLDialogElement` but without the modal surface: `showModal`,
 * `show` and `close` are all absent. Material Web's dialog calls `showModal()`
 * while opening, and the rejection that follows is asynchronous, so a dialog
 * that renders in a test — the Reading delete confirmation — fails the run
 * through an unhandled rejection rather than at the call site.
 *
 * This fills in the three methods with the state they are expected to keep:
 * `open` tracks whether the dialog is showing, and `close()` reports it through
 * the `close` event a native dialog fires. The parts a test asserts on are the
 * light-DOM contents, which need none of the real modal behaviour.
 */
function shimDialog(): void {
    const proto = globalThis.HTMLDialogElement?.prototype as
        | (HTMLDialogElement & { showModal?: () => void; show?: () => void })
        | undefined;
    if (!proto || typeof proto.showModal === 'function') return;

    const setOpen = (dialog: HTMLDialogElement, open: boolean) => {
        if (open) {
            dialog.setAttribute('open', '');
        } else {
            dialog.removeAttribute('open');
            dialog.dispatchEvent(new Event('close'));
        }
    };

    Object.defineProperties(proto, {
        showModal: {
            configurable: true,
            writable: true,
            value(this: HTMLDialogElement) {
                setOpen(this, true);
            },
        },
        show: {
            configurable: true,
            writable: true,
            value(this: HTMLDialogElement) {
                setOpen(this, true);
            },
        },
        close: {
            configurable: true,
            writable: true,
            value(this: HTMLDialogElement) {
                setOpen(this, false);
            },
        },
    });
}

/**
 * jsdom has no Web Animations API, and Material Web's dialog animates itself
 * open and closed through `element.animate(...)`. It awaits each animation's
 * `finished` promise, so a missing method surfaces as an unhandled rejection
 * rather than a failure at the call site.
 *
 * This returns an inert animation whose `finished` promise resolves at once and
 * whose `cancel()` does nothing: nothing under test depends on the animation.
 */
function shimElementAnimate(): void {
    if (typeof Element.prototype.animate === 'function') return;

    Element.prototype.animate = function animate(): Animation {
        return {
            finished: Promise.resolve(),
            cancel: () => {},
        } as unknown as Animation;
    } as Element['animate'];
}

shimElementAnimate();

shimDialog();
