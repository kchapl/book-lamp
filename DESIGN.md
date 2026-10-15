# Book Lamp — Design System

A portable brief for anything outside this repository that needs to draw Book
Lamp: a design tool, an agent, or a person with neither the code nor the CSS
open in front of them. Everything here is self-contained — colours as literal
values, the type scale, spacing, shape, motion, components and the rules that
are not negotiable.

**This file is an export, not an authority.** It is derived from
`docs/design-language.md` (the reference for how the app looks) and
`book_lamp/static/css/tokens.css` (the single source of truth for values). When
this file and those disagree, they win. Exported from commit `5960c51`; if the
tokens have moved since, trust the files.

The one thing the values cannot carry is the intent, so it leads.

> **Material 3 mechanics, and a reading room.** The app is built from the same
> parts as a modern Material product — tonal surfaces, elevation, state layers,
> a shape scale, motion tokens. And the collection is an exhibition: every book
> is an exhibit, mounted on a plinth with a wall label beside it, lit by the
> lamp.

## How to use this file

- **As a brief for a design tool.** Import it, or paste it, before generating
  anything. The point of the colour and type tables is that a tool can use the
  real values rather than a plausible palette.
- **As a brief for an agent.** Sections 10 and 11 are the ones that change
  outcomes: the non-negotiables, and where each value lives if you need to
  change it.
- **As a sketchpad input.** Directions that ignore section 1 will read as a
  different product, however well drawn.

## 1. The metaphor

The vocabulary below is load-bearing: components are named after it, and it is
what makes the UI specific rather than generic.

| Term | Meaning in the UI |
| --- | --- |
| **The Reading Room** | The whole app shell: header, collection, footer. |
| **Exhibit** | A single Book. Cards, list rows and the detail header are all mounts for an exhibit. |
| **Plinth** | The raised tonal panel an exhibit sits on (`surface-container-low`, elevation 1, brass hairline). |
| **Placard** | The wall label: title in serif, author, then small-caps metadata rows. |
| **Accession line** | The quiet metadata strip — year, ISBN, publisher — set in tabular figures. |
| **Condition chip** | Reading Status as a condition tag: Completed / In Progress / Abandoned. |
| **The lamp** | Brand motif. Lamp green is the primary role; brass is the secondary rule/accent. |

## 2. Colour

Material 3 roles, never raw colour names in a layout. Forest is the accent,
amber is In Progress, indigo is occasional emphasis, and the neutrals are cool —
white and grey separated by hairlines, never a stack of tonal tints and never a
warm beige. The dark theme is neutral ink, not a warm brown.

| Token (`--md-sys-color-*`) | Light | Dark |
| --- | --- | --- |
| `primary` | `#0f7a55` | `#4fd1a5` |
| `on-primary` | `#ffffff` | `#04241a` |
| `primary-container` | `#e7f3ee` | `#10352a` |
| `on-primary-container` | `#04301f` | `#a7f3d0` |
| `secondary` | `#9a5b12` | `#e3c07f` |
| `on-secondary` | `#ffffff` | `#3a2a06` |
| `secondary-container` | `#fdf0d5` | `#4a3413` |
| `on-secondary-container` | `#3a2a06` | `#f7e0b4` |
| `tertiary` | `#44506b` | `#a8b6e0` |
| `on-tertiary` | `#ffffff` | `#1c2333` |
| `tertiary-container` | `#e5e8f0` | `#2a3350` |
| `on-tertiary-container` | `#1c2333` | `#dbe3f7` |
| `error` | `#b91c1c` | `#f2b8b5` |
| `on-error` | `#ffffff` | `#601410` |
| `error-container` | `#fee2e2` | `#8c1d18` |
| `on-error-container` | `#7a271a` | `#f9dedc` |
| `surface` | `#fafafa` | `#0b0b0c` |
| `on-surface` | `#0a0a0a` | `#f4f4f5` |
| `surface-variant` | `#f4f4f5` | `#27272a` |
| `on-surface-variant` | `#52525b` | `#a1a1aa` |
| `surface-container-lowest` | `#ffffff` | `#050506` |
| `surface-container-low` | `#ffffff` | `#121214` |
| `surface-container` | `#f4f4f5` | `#17171a` |
| `surface-container-high` | `#ececee` | `#1e1e22` |
| `surface-container-highest` | `#e4e4e7` | `#26262b` |
| `outline` | `#a1a1aa` | `#71717a` |
| `outline-variant` | `#e4e4e7` | `#27272a` |
| `inverse-surface` | `#18181b` | `#f4f4f5` |
| `inverse-on-surface` | `#fafafa` | `#18181b` |
| `inverse-primary` | `#4fd1a5` | `#0f7a55` |
| `surface-tint` | `#0f7a55` | `#4fd1a5` |

`background` / `on-background` repeat `surface` / `on-surface`. Shadows and
scrims are `#000000`.

### Reading Status, as roles

Status is never ad-hoc colour. Each maps to a role family, and its container:

| Status | Role | Light | Dark |
| --- | --- | --- | --- |
| Completed | `primary` | `#0f7a55` | `#4fd1a5` |
| In Progress | `secondary` | `#9a5b12` | `#e3c07f` |
| Abandoned | `error` | `#b91c1c` | `#f2b8b5` |
| Planned | `tertiary` | `#44506b` | `#a8b6e0` |

## 3. Typography

Two faces, no more. **Newsreader** (serif) is the editorial voice — `display`,
`headline`, and every Book title. **Inter** (grotesque) is the instrument voice
— `title`, `body`, `label`: controls, metadata, numbers.

The MD3 scale is unchanged in size; only the display and headline families are
reassigned to the serif. Display and headline weights are 500, not 400.

| Role | Face | Size / line height | Weight | Tracking |
| --- | --- | --- | --- | --- |
| `display-large` | serif | 57 / 62 | 500 | −0.5px |
| `display-medium` | serif | 45 / 52 | 500 | −0.25px |
| `display-small` | serif | 36 / 44 | 500 | 0 |
| `headline-large` | serif | 32 / 40 | 500 | 0 |
| `headline-medium` | serif | 28 / 36 | 500 | 0 |
| `headline-small` | serif | 24 / 32 | 500 | 0 |
| `title-large` | Inter | 22 / 28 | 500 | 0 |
| `title-medium` | Inter | 16 / 24 | 500 | +0.15px |
| `title-small` | Inter | 14 / 20 | 500 | +0.1px |
| `body-large` | Inter | 16 / 24 | 400 | +0.2px |
| `body-medium` | Inter | 14 / 20 | 400 | +0.1px |
| `body-small` | Inter | 12 / 16 | 400 | +0.2px |
| `label-large` | Inter | 14 / 20 | 500 | +0.1px |
| `label-medium` | Inter | 12 / 16 | 500 | +0.5px |
| `label-small` | Inter | 11 / 16 | 500 | +0.5px |

- Placards are `label-small` in small caps with wide tracking (`0.14em`,
  `--bl-tracking-placard`) so the metadata reads as a museum label.
- Numbers that sit in columns or change in place — counts, dates, page totals —
  use `font-variant-numeric: tabular-nums` so they never jitter.

## 4. Shape

The MD3 corner scale, used deliberately.

| Token | Value | Used for |
| --- | --- | --- |
| `--md-sys-shape-corner-extra-small` | 4px | small covers and thumbnails, tooltips |
| `--md-sys-shape-corner-small` | 8px | covers, fields, category blocks |
| `--md-sys-shape-corner-medium` | 12px | exhibits, cards and tiles |
| `--md-sys-shape-corner-large` | 16px | the big mounts: panels, auth and status cards |
| `--md-sys-shape-corner-extra-large` | 20px | the modal, the hero |
| `--md-sys-shape-corner-full` | 9999px | buttons, chips, meters, pill-shaped inputs |

## 5. Space

A 4px-based scale. Page gutters come from `.page`; section rhythm from
`.section`. Nothing invents its own spacing value.

| Token | Value |
| --- | --- |
| `--bl-space-1` | 4px |
| `--bl-space-2` | 8px |
| `--bl-space-3` | 12px |
| `--bl-space-4` | 16px |
| `--bl-space-5` | 24px |
| `--bl-space-6` | 32px |
| `--bl-space-7` | 48px |
| `--bl-space-8` | 64px |

## 6. Elevation

Quiet and neutral. **Depth is carried by hairlines first**; shadow is reserved
for what genuinely floats — menus, modals, the FAB. Cards separate with a 1px
border and darken that border on hover instead of lifting.

| Token | Value |
| --- | --- |
| `--md-sys-elevation-1` | `0 1px 2px rgba(0, 0, 0, 0.05)` |
| `--md-sys-elevation-2` | `0 2px 4px rgba(0, 0, 0, 0.06), 0 4px 12px rgba(0, 0, 0, 0.05)` |
| `--md-sys-elevation-3` | `0 8px 24px rgba(0, 0, 0, 0.10), 0 2px 6px rgba(0, 0, 0, 0.06)` |
| `--md-sys-elevation-4` | `0 12px 32px rgba(0, 0, 0, 0.14), 0 4px 10px rgba(0, 0, 0, 0.08)` |
| `--md-sys-elevation-5` | `0 16px 40px rgba(0, 0, 0, 0.18)` |

Shadows are cast in `--bl-shadow-color` (`0, 0, 0`). The ladder as used: 1 and
2 carry resting mounts and their hover lift — plinths, framed covers. 3 is
reserved for what genuinely floats above the page: modals, and the FAB, which
rises to 4 on hover. Nothing uses 5.

## 7. Motion

Deliberately small, because the data changes at most daily and the interface
does not pretend to be live.

- **Easing** — `emphasized` `cubic-bezier(0.2, 0, 0, 1)` and `standard`
  `cubic-bezier(0.2, 0, 0.2, 1)`, with decelerate/accelerate variants at
  `cubic-bezier(0, 0, 0.2, 1)` and `cubic-bezier(0.3, 0, 1, 1)`.
- **Durations** — `short1` 50ms, `short2` 100ms, `medium1` 200ms, `medium2`
  300ms, `long1` 400ms, `long2` 500ms, `extra-long1` 600ms. Hover transitions
  sit at `short2`–`medium1`.
- **State layers** — hover `0.08`, focus `0.12`, pressed `0.12`, dragged
  `0.16`.
- Progress meters fill once on mount (`bar-grow`), never continuously.
- Everything respects `prefers-reduced-motion`.

## 8. Components

Classes live in `book_lamp/static/css/components.css`.

| Component | Class | Notes |
| --- | --- | --- |
| Button | `.btn` + `.btn-primary` / `.btn-tonal` / `.btn-outline` / `.btn-text` / `.btn-danger` | `--btn-*` custom properties drive the variants. |
| Icon button | `.btn-icon` | 48px target, circular state layer. |
| Floating action button | `.fab`, `.fab-slot` | A screen's primary action; a pill that sticks to the foot of the page column. One per screen. |
| Chip | `.chip`, `.status-badge` | Filter chips; condition chips add `.status-completed` / `.status-in-progress` / `.status-abandoned` / `.status-planned`. Uppercase `label-small` with a dot in `currentColor`. |
| Field | `.field`, `.field-input`, `.field-label` | Labels above; neutral container, hairline border, primary focus ring. 48px minimum height. |
| Exhibit | `.exhibit` | The book card. Plinth + framed cover + placard. |
| Placard | `.placard`, `.placard-row` | Wall-label metadata. |
| Meter | `.meter`, `.meter-fill` | Status and rating bars. |
| Panel | `.panel` | A tonal section mount on the Dashboard. |
| Skeleton | `.skeleton-*` | Shimmer placeholders in the plinth's own shape. |
| Empty state | `.empty-state` | Dashed mount, one clear action. |
| Modal | `.modal-overlay`, `.modal` | Scrim + raised surface. |

Interactive controls also exist as Material Web custom elements —
`md-filled-button`, `md-outlined-text-field`, `md-filter-chip`, `md-dialog`,
`md-fab` and so on — wrapped for React in `src/react/ui/index.tsx`. They read
the same custom properties above, so a design made from those tokens should land
in either.

## 9. Layout

- `.app-container` — the Reading Room frame: header, main, footer.
- `.page` — centred content column, max **1100px**.
- `.site-header` — sticky, tonal, brass hairline along its bottom edge.

Breakpoints: **1100px** (grid reflow), **900px** (dashboard grid stacks),
**640px** (mobile nav, single column). Touch targets stay **≥ 44px**.

## 10. Non-negotiables

1. **Colour is defined once.** No layout, component or tool introduces a colour
   value. New colour, face or shape is added to `docs/design-language.md` first,
   then to `tokens.css`, then used.
2. **Contrast.** Body text ≥ 4.5:1; large text and UI borders ≥ 3:1.
3. **Status is never carried by colour alone.** Every condition chip has a text
   label.
4. **Neutral surfaces.** No warm beige, no tonal tint stacks. Dark theme is
   neutral ink, not warm brown.
5. **Hairlines before shadows.** If something is not genuinely floating, it does
   not get a shadow.
6. **One FAB per screen**, and only where there is a single primary action.
7. **Two faces, MD3 sizes.** No third typeface, no size invented for a
   particular screen.
8. **No fake liveness.** No streaks, no live counters, no auto-refreshing
   numbers. Freshness is stated with an as-of line ("Last entry MMM D, YYYY").
9. **Tabular figures** wherever numbers sit in columns or change in place.
10. **Motion stays small**, and `prefers-reduced-motion` is honoured.

## 11. Where this comes from

| Value or rule | Lives in |
| --- | --- |
| Colour, type, shape, space, elevation, motion, state layers | `book_lamp/static/css/tokens.css` |
| The metaphor, and the rules above | `docs/design-language.md` |
| Component classes and their look | `book_lamp/static/css/components.css`, `pages.css`, `base.css` |
| React wrappers for Material Web controls | `src/react/ui/index.tsx` |
| Routes and page inventory | `src/react/App.tsx` |

Changing a value means changing it there, not here.
