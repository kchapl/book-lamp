import React from 'react';

/**
 * The app's icon set: inline SVG on a 24px grid, drawn in `currentColor`.
 *
 * One component, one visual voice — no icon font to download and no emoji
 * standing in for UI. New icons are added to the map below.
 */
export type IconName =
    | 'lamp'
    | 'home'
    | 'books'
    | 'bookmark'
    | 'history'
    | 'chart'
    | 'clock'
    | 'sun'
    | 'moon'
    | 'monitor'
    | 'check'
    | 'alert'
    | 'plus'
    | 'search'
    | 'grip'
    | 'star'
    | 'arrow-left'
    | 'close'
    | 'menu';

const PATHS: Record<IconName, React.ReactNode> = {
    lamp: (
        <>
            <path d="M6 3h12l3 8H3l3-8Z" />
            <path d="M10 11h4v7a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-7Z" />
            <path d="M8 21h8v-1.4H8V21Z" />
        </>
    ),
    home: <path d="M12 3 3 10v11h6v-6h6v6h6V10l-9-7Z" />,
    books: (
        <>
            <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H11v18H6.5A2.5 2.5 0 0 0 4 23.5v-18Z" />
            <path d="M13 3h4.5A2.5 2.5 0 0 1 20 5.5v18A2.5 2.5 0 0 0 17.5 21H13V3Z" />
        </>
    ),
    bookmark: <path d="M6 3h12a1 1 0 0 1 1 1v17l-7-4-7 4V4a1 1 0 0 1 1-1Z" />,
    history: (
        <>
            <path d="M13 3a9 9 0 1 0 8.5 6.1l-2 .7A7 7 0 1 1 13 5c1.9 0 3.6.8 4.9 2H15v2h6V3h-2v2.1A9 9 0 0 0 13 3Z" />
            <path d="M12 8h2v4.5l3.2 1.9-1 1.7L12 13.6V8Z" />
        </>
    ),
    chart: <path d="M4 20V10h4v10H4Zm6 0V4h4v16h-4Zm6 0v-7h4v7h-4Z" />,
    clock: (
        <>
            <path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm0 18a8 8 0 1 1 0-16 8 8 0 0 1 0 16Z" />
            <path d="M11 7h2v5.2l4 2.4-1 1.7-5-3V7Z" />
        </>
    ),
    sun: (
        <>
            <circle cx="12" cy="12" r="4.2" />
            <path d="M12 1.5 13.4 3.2v2.6L12 4.7 10.6 5.8V3.2L12 1.5ZM12 22.5 10.6 20.8v-2.6L12 19.3l1.4-1.1v2.6L12 22.5ZM1.5 12l1.7-1.4h2.6L4.7 12l1.1 1.4H3.2L1.5 12ZM22.5 12l-1.7 1.4h-2.6l1.1-1.4-1.1-1.4h2.6L22.5 12Z" />
        </>
    ),
    moon: <path d="M20.5 14.3A8.6 8.6 0 0 1 9.7 3.5a9 9 0 1 0 10.8 10.8Z" />,
    monitor: (
        <>
            <path d="M3 4h18v11H3V4Zm2 2v7h14V6H5Z" />
            <path d="M8 17h8v2H8v-2Z" />
        </>
    ),
    check: <path d="M9.6 16.2 5.4 12l-1.4 1.4 5.6 5.6 12-12-1.4-1.4-10.6 10.6Z" />,
    alert: (
        <>
            <path d="M12 2 1 21h22L12 2Zm0 4.2L19.6 19H4.4L12 6.2Z" />
            <path d="M11 10h2v5h-2v-5Zm0 6.5h2v2h-2v-2Z" />
        </>
    ),
    plus: <path d="M11 5h2v6h6v2h-6v6h-2v-6H5v-2h6V5Z" />,
    search: (
        <>
            <path d="M15.5 14h-.8l-.3-.3a6.5 6.5 0 1 0-.7.7l.3.3v.8l5 5 1.5-1.5-5-5Zm-6 0a4.5 4.5 0 1 1 0-9 4.5 4.5 0 0 1 0 9Z" />
        </>
    ),
    grip: (
        <>
            <circle cx="9" cy="6" r="1.6" />
            <circle cx="15" cy="6" r="1.6" />
            <circle cx="9" cy="12" r="1.6" />
            <circle cx="15" cy="12" r="1.6" />
            <circle cx="9" cy="18" r="1.6" />
            <circle cx="15" cy="18" r="1.6" />
        </>
    ),
    star: <path d="m12 2.5 2.9 6 6.6.9-4.8 4.6 1.2 6.5-5.9-3.2-5.9 3.2 1.2-6.5L2.5 9.4l6.6-.9 2.9-6Z" />,
    'arrow-left': <path d="M20 11H7.8l5.6-5.6L12 4l-8 8 8 8 1.4-1.4L7.8 13H20v-2Z" />,
    close: <path d="m19 6.4L17.6 5 12 10.6 6.4 5 5 6.4 10.6 12 5 17.6 6.4 19 12 13.4 17.6 19 19 17.6 13.4 12 19 6.4Z" />,
    menu: <path d="M3 6h18v2H3V6Zm0 5h18v2H3v-2Zm0 5h18v2H3v-2Z" />,
};

interface IconProps {
    name: IconName;
    className?: string;
    size?: 'sm' | 'md' | 'lg';
    title?: string;
    /** Slot name, for handing the icon to a Material Web component. */
    slot?: string;
}

const Icon: React.FC<IconProps> = ({ name, className, size = 'md', title, slot }) => {
    const classes = ['icon', size !== 'md' ? `icon-${size}` : '', className].filter(Boolean).join(' ');
    return (
        <span className={classes} slot={slot} aria-hidden={title ? undefined : true} role={title ? 'img' : undefined}>
            {title && <span className="sr-only">{title}</span>}
            <svg viewBox="0 0 24 24" fill="currentColor" focusable="false" aria-hidden="true">
                {PATHS[name]}
            </svg>
        </span>
    );
};

export default Icon;
