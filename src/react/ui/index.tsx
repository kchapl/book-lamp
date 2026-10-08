/**
 * Material Web controls, wrapped for React.
 *
 * The custom elements are Lit-based, so two things need bridging:
 *
 * 1. Registration. Each tag only exists once its module is imported, so the
 *    side-effect imports below are load-bearing, not cosmetic.
 * 2. Events. Material Web dispatches plain DOM events (`click`, `input`,
 *    `change`, `closed`) from inside its shadow root. React's synthetic system
 *    does not reliably reach those, and its `onChange` does not match the
 *    library's `change` payloads, so every wrapper attaches a native listener
 *    to the host element with a ref instead.
 *
 * Styling stays in `static/css/`: the components read the same
 * `--md-sys-color-*` and `--md-ref-typeface-*` custom properties that
 * `tokens.css` already defines.
 */
import React, { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import Icon, { type IconName } from '../components/Icon';

import '@material/web/button/filled-button.js';
import '@material/web/button/filled-tonal-button.js';
import '@material/web/button/elevated-button.js';
import '@material/web/button/outlined-button.js';
import '@material/web/button/text-button.js';
import '@material/web/iconbutton/icon-button.js';
import '@material/web/iconbutton/filled-icon-button.js';
import '@material/web/iconbutton/filled-tonal-icon-button.js';
import '@material/web/iconbutton/outlined-icon-button.js';
import '@material/web/textfield/outlined-text-field.js';
import '@material/web/textfield/filled-text-field.js';
import '@material/web/select/outlined-select.js';
import '@material/web/select/filled-select.js';
import '@material/web/select/select-option.js';
import '@material/web/chips/chip-set.js';
import '@material/web/chips/filter-chip.js';
import '@material/web/chips/assist-chip.js';
import '@material/web/dialog/dialog.js';
import '@material/web/progress/linear-progress.js';
import '@material/web/progress/circular-progress.js';
import '@material/web/checkbox/checkbox.js';
import '@material/web/switch/switch.js';
import '@material/web/fab/fab.js';

/**
 * Attach a native listener to a Material Web host element.
 *
 * The handler is read from a ref on every dispatch, so the listener never goes
 * stale even though it is only attached once per element. There is deliberately
 * no dependency array: a re-render re-attaches, which is cheap and keeps the
 * element reference honest if React swaps the node.
 */
function useMdListener<T extends HTMLElement>(
    type: string,
    handler?: (element: T, event: Event) => void
) {
    const ref = useRef<T | null>(null);
    const handlerRef = useRef(handler);
    handlerRef.current = handler;

    useEffect(() => {
        const element = ref.current;
        if (!element) return;
        const listener = (event: Event) => handlerRef.current?.(element, event);
        element.addEventListener(type, listener);
        return () => element.removeEventListener(type, listener);
    });

    return ref;
}

/**
 * Shared props every control honours. Extending React's HTML attributes is what
 * lets callers pass `role`, `aria-*` and `id` straight through to the host
 * element, which matters because the hosts carry no implicit ARIA role of
 * their own.
 */
type MdBaseProps = React.HTMLAttributes<HTMLElement>;

/* =============================================================================
   BUTTONS
   ============================================================================= */

export type ButtonVariant = 'filled' | 'tonal' | 'elevated' | 'outlined' | 'text';

const BUTTON_TAGS: Record<ButtonVariant, string> = {
    filled: 'md-filled-button',
    tonal: 'md-filled-tonal-button',
    elevated: 'md-elevated-button',
    outlined: 'md-outlined-button',
    text: 'md-text-button',
};

export interface ButtonProps extends MdBaseProps {
    variant?: ButtonVariant;
    icon?: IconName;
    /** Navigate to an in-app route when clicked. */
    to?: string;
    onClick?: React.MouseEventHandler<HTMLElement>;
    type?: 'button' | 'submit' | 'reset';
    disabled?: boolean;
    children?: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
    variant = 'filled',
    icon,
    to,
    onClick,
    type = 'button',
    disabled,
    className,
    children,
    ...rest
}) => {
    const navigate = useNavigate();
    const ref = useMdListener<HTMLElement>('click', (element, event) => {
        if (disabled) return;
        if (to) {
            event.preventDefault();
            navigate(to);
        }
        onClick?.(event as unknown as React.MouseEvent<HTMLElement>);
    });

    const Tag = BUTTON_TAGS[variant] as React.ElementType;

    return (
        <Tag ref={ref} className={className} type={to ? 'button' : type} disabled={disabled} {...rest}>
            {icon && <Icon name={icon} slot="icon" />}
            {children}
        </Tag>
    );
};

export interface IconButtonProps extends MdBaseProps {
    icon: IconName;
    variant?: 'standard' | 'filled' | 'tonal' | 'outlined';
    to?: string;
    onClick?: React.MouseEventHandler<HTMLElement>;
    disabled?: boolean;
}

const ICON_BUTTON_TAGS = {
    standard: 'md-icon-button',
    filled: 'md-filled-icon-button',
    tonal: 'md-filled-tonal-icon-button',
    outlined: 'md-outlined-icon-button',
} as const;

export const IconButton: React.FC<IconButtonProps> = ({
    icon,
    variant = 'standard',
    to,
    onClick,
    disabled,
    className,
    ...rest
}) => {
    const navigate = useNavigate();
    const ref = useMdListener<HTMLElement>('click', (element, event) => {
        if (disabled) return;
        if (to) {
            event.preventDefault();
            navigate(to);
        }
        onClick?.(event as unknown as React.MouseEvent<HTMLElement>);
    });

    const Tag = ICON_BUTTON_TAGS[variant] as React.ElementType;

    return (
        // Unlike `md-*-button` and `md-fab`, `md-icon-button` has no `icon` slot:
        // it styles `::slotted(*)` and renders the icon from its default slot. An
        // icon marked `slot="icon"` would be assigned to a slot that does not
        // exist, and so would never be painted at all.
        <Tag ref={ref} className={className} disabled={disabled} {...rest}>
            <Icon name={icon} />
        </Tag>
    );
};

/* =============================================================================
   TEXT FIELDS
   ============================================================================= */

export interface TextFieldProps extends MdBaseProps {
    label: string;
    value: string;
    onValueChange: (value: string) => void;
    type?: 'text' | 'search' | 'number' | 'email' | 'password' | 'tel' | 'url' | 'textarea';
    placeholder?: string;
    name?: string;
    required?: boolean;
    disabled?: boolean;
    supportingText?: string;
    error?: boolean;
    rows?: number;
    readonly?: boolean;
    /** Bounds for `type="number"`, forwarded to the inner input. */
    min?: number | string;
    max?: number | string;
}

export const TextField: React.FC<TextFieldProps> = ({
    label,
    value,
    onValueChange,
    type = 'text',
    placeholder,
    name,
    required,
    disabled,
    supportingText,
    error,
    rows,
    readonly,
    className,
    ...rest
}) => {
    const ref = useMdListener<HTMLElement & { value: string }>('input', (element) => {
        onValueChange(element.value);
    });

    return (
        <md-outlined-text-field
            ref={ref}
            className={className}
            label={label}
            value={value}
            type={type}
            placeholder={placeholder}
            name={name}
            required={required}
            disabled={disabled}
            supportingText={supportingText}
            error={error}
            rows={rows}
            readonly={readonly}
            {...rest}
        />
    );
};

/* =============================================================================
   SELECT
   ============================================================================= */

export interface SelectProps extends MdBaseProps {
    label: string;
    value: string;
    onValueChange: (value: string) => void;
    disabled?: boolean;
    required?: boolean;
    children?: React.ReactNode;
}

export const Select: React.FC<SelectProps> = ({
    label,
    value,
    onValueChange,
    disabled,
    required,
    className,
    children,
    ...rest
}) => {
    const ref = useMdListener<HTMLElement & { value: string }>('change', (element) => {
        onValueChange(element.value);
    });

    return (
        <md-outlined-select
            ref={ref}
            className={className}
            label={label}
            value={value}
            disabled={disabled}
            required={required}
            {...rest}
        >
            {children}
        </md-outlined-select>
    );
};

export interface SelectOptionProps {
    value: string;
    children: React.ReactNode;
}

export const SelectOption: React.FC<SelectOptionProps> = ({ value, children }) => (
    <md-select-option value={value}>
        <div slot="headline">{children}</div>
    </md-select-option>
);

/* =============================================================================
   CHIPS
   ============================================================================= */

export interface FilterChipProps {
    label: string;
    selected: boolean;
    onSelectedChange?: (selected: boolean) => void;
    disabled?: boolean;
    className?: string;
}

export const FilterChip: React.FC<FilterChipProps> = ({
    label,
    selected,
    onSelectedChange,
    disabled,
    className,
}) => {
    const ref = useMdListener<HTMLElement & { selected: boolean }>('change', (element) => {
        onSelectedChange?.(element.selected);
    });

    return (
        <md-filter-chip
            ref={ref}
            className={className}
            label={label}
            selected={selected}
            disabled={disabled}
        />
    );
};

/* =============================================================================
   DIALOG
   ============================================================================= */

export interface DialogProps {
    open: boolean;
    onClose: () => void;
    headline: string;
    className?: string;
    children?: React.ReactNode;
    actions?: React.ReactNode;
}

export const Dialog: React.FC<DialogProps> = ({
    open,
    onClose,
    headline,
    className,
    children,
    actions,
}) => {
    const ref = useMdListener<HTMLElement & { open: boolean }>('closed', () => onClose());

    useEffect(() => {
        const dialog = ref.current as (HTMLElement & { open: boolean; show?: () => void }) | null;
        if (!dialog) return;
        if (open && !dialog.open) dialog.show?.();
        if (!open && dialog.open) dialog.open = false;
    });

    return (
        <md-dialog ref={ref} className={className} open={open}>
            <div slot="headline">{headline}</div>
            {children}
            {actions && <div slot="actions">{actions}</div>}
        </md-dialog>
    );
};

/* =============================================================================
   PROGRESS
   ============================================================================= */

export interface LinearProgressProps extends React.HTMLAttributes<HTMLElement> {
    /** Completion as a percentage, 0–100. Material Web wants a 0–1 fraction. */
    percent?: number;
    indeterminate?: boolean;
}

export const LinearProgress: React.FC<LinearProgressProps> = ({
    percent,
    indeterminate,
    className,
    ...rest
}) => (
    <md-linear-progress
        className={className}
        value={percent === undefined ? undefined : Math.min(Math.max(percent, 0), 100) / 100}
        indeterminate={indeterminate}
        {...rest}
    />
);

export interface CircularProgressProps extends React.HTMLAttributes<HTMLElement> {
    indeterminate?: boolean;
    value?: number;
    size?: 'small' | 'medium' | 'large';
}

export const CircularProgress: React.FC<CircularProgressProps> = ({
    indeterminate = true,
    value,
    className,
    ...rest
}) => (
    <md-circular-progress
        className={className}
        indeterminate={indeterminate}
        value={value}
        {...rest}
    />
);

/* =============================================================================
   CHECKBOX & SWITCH
   ============================================================================= */

export interface CheckboxProps extends MdBaseProps {
    checked: boolean;
    onCheckedChange: (checked: boolean) => void;
    disabled?: boolean;
}

export const Checkbox: React.FC<CheckboxProps> = ({
    checked,
    onCheckedChange,
    disabled,
    className,
    ...rest
}) => {
    const ref = useMdListener<HTMLElement & { checked: boolean }>('change', (element) => {
        onCheckedChange(element.checked);
    });

    return <md-checkbox ref={ref} className={className} checked={checked} disabled={disabled} {...rest} />;
};

/* =============================================================================
   FLOATING ACTION BUTTON
   ============================================================================= */

export interface FabProps extends MdBaseProps {
    icon: IconName;
    /** Present makes it an extended FAB with a visible label. */
    label?: string;
    to?: string;
    onClick?: React.MouseEventHandler<HTMLElement>;
    size?: 'small' | 'medium' | 'large';
}

export const Fab: React.FC<FabProps> = ({ icon, label, to, onClick, size, className, ...rest }) => {
    const navigate = useNavigate();
    const ref = useMdListener<HTMLElement>('click', (element, event) => {
        if (to) {
            event.preventDefault();
            navigate(to);
        }
        onClick?.(event as unknown as React.MouseEvent<HTMLElement>);
    });

    return (
        <md-fab ref={ref} className={className} label={label} size={size} {...rest}>
            <Icon name={icon} slot="icon" />
        </md-fab>
    );
};
