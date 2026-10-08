/**
 * The wrappers exist because React's synthetic events do not reliably cross into
 * a custom element's shadow root, and because Material Web's `change` payloads
 * differ from React's. These tests pin the bridge itself: a rendered control
 * must be a real, upgraded Material Web element that reports its value back.
 */
import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Button, Fab, FilterChip, IconButton, LinearProgress, Select, TextField } from '..';

const renderInRouter = (ui: React.ReactElement) =>
    render(<MemoryRouter>{ui}</MemoryRouter>);

describe('Material Web wrappers', () => {
    it('registers the custom elements it renders', () => {
        const { container } = renderInRouter(<Button>Save</Button>);

        const button = container.querySelector('md-filled-button');
        expect(button).toBeInTheDocument();
        // A defined custom element is upgraded; an undefined tag is just HTML.
        expect(customElements.get('md-filled-button')).toBeDefined();
        expect(button?.tagName.toLowerCase()).toBe('md-filled-button');
    });

    it('reports clicks on the host element', () => {
        const onClick = vi.fn();
        const { container } = renderInRouter(<Button onClick={onClick}>Save</Button>);

        fireEvent.click(container.querySelector('md-filled-button') as HTMLElement);

        expect(onClick).toHaveBeenCalledTimes(1);
    });

    it('does not report clicks while disabled', () => {
        const onClick = vi.fn();
        const { container } = renderInRouter(
            <Button onClick={onClick} disabled>
                Save
            </Button>
        );

        fireEvent.click(container.querySelector('md-filled-button') as HTMLElement);

        expect(onClick).not.toHaveBeenCalled();
    });

    it('reads a text field value off the host on every input', () => {
        const onValueChange = vi.fn();
        const { container } = renderInRouter(
            <TextField label="Title" value="" onValueChange={onValueChange} />
        );

        const field = container.querySelector('md-outlined-text-field') as HTMLElement & {
            value: string;
        };
        field.value = 'Piranesi';
        fireEvent.input(field);

        expect(onValueChange).toHaveBeenCalledWith('Piranesi');
    });

    it('reads a select value off the host when it changes', () => {
        const onValueChange = vi.fn();
        const { container } = renderInRouter(
            <Select label="Sort" value="" onValueChange={onValueChange}>
                <md-select-option value="title">
                    <div slot="headline">Title</div>
                </md-select-option>
            </Select>
        );

        const select = container.querySelector('md-outlined-select') as HTMLElement & {
            value: string;
        };

        // Material Web resolves `value` against its rendered options, which does
        // not complete under jsdom, so there is no value to read here. What this
        // wrapper owns is the bridge: a change event must reach the handler, and
        // the handler must report the host's current value. The text-field test
        // above covers the value actually flowing through.
        fireEvent.change(select);

        expect(onValueChange).toHaveBeenCalledTimes(1);
        expect(onValueChange).toHaveBeenCalledWith(select.value);
    });

    it('reports filter chip selection', () => {
        const onSelectedChange = vi.fn();
        const { container } = renderInRouter(
            <FilterChip label="Completed" selected={false} onSelectedChange={onSelectedChange} />
        );

        const chip = container.querySelector('md-filter-chip') as HTMLElement & {
            selected: boolean;
        };
        chip.selected = true;
        fireEvent.change(chip);

        expect(onSelectedChange).toHaveBeenCalledWith(true);
    });

    // The component families disagree about where their icon goes, and getting it
    // wrong fails silently — the element still renders, just empty. These pin the
    // contract for each family.
    it('passes the icon through the default slot for md-icon-button', () => {
        const { container } = renderInRouter(<IconButton icon="moon" aria-label="Change theme" />);

        const icon = container.querySelector('md-icon-button .icon');
        expect(icon).toBeInTheDocument();
        // md-icon-button renders `<slot>` plus a `selected` slot, but no `icon`
        // slot; an icon marked slot="icon" would never be painted.
        expect(icon).not.toHaveAttribute('slot');
    });

    it('marks the icon for the families that do have an icon slot', () => {
        const { container } = renderInRouter(
            <>
                <Button icon="search">Search</Button>
                <Fab icon="plus" label="Add book" />
            </>
        );

        expect(container.querySelector('md-filled-button .icon')).toHaveAttribute('slot', 'icon');
        expect(container.querySelector('md-fab .icon')).toHaveAttribute('slot', 'icon');
    });

    it('passes a percentage to the linear progress as a 0–1 fraction', () => {
        const { container } = renderInRouter(<LinearProgress percent={40} />);

        const progress = container.querySelector('md-linear-progress') as HTMLElement & {
            value: number;
        };
        expect(progress.value).toBeCloseTo(0.4);
    });
});
