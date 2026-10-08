/**
 * JSX types for the @material/web custom elements we render.
 *
 * The package ships TypeScript for its classes but no React bindings, so React
 * does not know these tags exist. We augment `React.JSX.IntrinsicElements`
 * (React 19 declares the JSX namespace inside the `react` module) with a
 * permissive prop shape: Material Web attributes are not described by React's
 * `HTMLAttributes`, and the index signature keeps us from restating every
 * attribute the library supports.
 */
import type * as React from 'react';

type MdElementProps = React.HTMLAttributes<HTMLElement> & Record<string, unknown>;

declare module 'react' {
    namespace JSX {
        interface IntrinsicElements {
            'md-filled-button': MdElementProps;
            'md-filled-tonal-button': MdElementProps;
            'md-elevated-button': MdElementProps;
            'md-outlined-button': MdElementProps;
            'md-text-button': MdElementProps;

            'md-icon-button': MdElementProps;
            'md-filled-icon-button': MdElementProps;
            'md-filled-tonal-icon-button': MdElementProps;
            'md-outlined-icon-button': MdElementProps;

            'md-outlined-text-field': MdElementProps;
            'md-filled-text-field': MdElementProps;
            'md-outlined-select': MdElementProps;
            'md-filled-select': MdElementProps;
            'md-select-option': MdElementProps;

            'md-chip-set': MdElementProps;
            'md-filter-chip': MdElementProps;
            'md-assist-chip': MdElementProps;
            'md-input-chip': MdElementProps;

            'md-dialog': MdElementProps;
            'md-divider': MdElementProps;
            'md-checkbox': MdElementProps;
            'md-switch': MdElementProps;
            'md-radio': MdElementProps;

            'md-linear-progress': MdElementProps;
            'md-circular-progress': MdElementProps;

            'md-fab': MdElementProps;
            'md-extended-fab': MdElementProps;

            'md-list': MdElementProps;
            'md-list-item': MdElementProps;
            'md-icon': MdElementProps;
        }
    }
}
