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
