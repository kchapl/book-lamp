# Book Lamp — Visual Language

This document is the single reference for how Book Lamp looks. Anything visual
should be traceable to a token or component named here. If a new colour, face or
shape is needed, add it here first, then use it.

The two sentences to hold in mind:

- **Material 3 mechanics** — tonal surfaces, elevation, state layers, a shape
  scale, motion tokens. The app is built from the same parts as a modern
  Material product.
- **The reading room** — the collection is an exhibition. Every book is an
  exhibit, mounted on a plinth with a wall label beside it, lit by the lamp.

## 1. The metaphor

| Term | Meaning in the UI |
| --- | --- |
| **The Reading Room** | The whole app shell: header, collection, footer. |
| **Exhibit** | A single Book. Cards, list rows and the detail header are all mounts for an exhibit. |
| **Plinth** | The raised tonal panel an exhibit sits on (`surface-container-low`, elevation 1, brass hairline). |
| **Placard** | The wall label: title in serif, author, then small-caps metadata rows. |
| **Accession line** | The quiet metadata strip — year, ISBN, publisher — set in tabular figures. |
| **Condition chip** | Reading Status rendered as a condition tag: Completed / In Progress / Abandoned. |
| **The lamp** | Brand motif. Lamp green is the primary role; brass is the secondary rule/accent. |

## 2. Colour

Colour is defined once, as Material 3 roles, in `static/css/tokens.css`. Nothing
else defines colour values.

- **Lamp green** (`primary`) — the banker's-lamp shade. Brand, primary actions,
  progress, Completed.
- **Brass** (`secondary`) — the metal. Rules, frames, In Progress, secondary
  actions.
- **Oxblood** (`tertiary`) — book cloth. Occasional emphasis, highlight surfaces.
- **Error** — reserved for destructive actions and genuine failures only.
- **Paper** (`surface*`) — warm off-white paper, never pure grey. Dark theme is
  ink, not black.

Contrast targets: body text ≥ 4.5:1, large text and UI borders ≥ 3:1. Status is
never carried by colour alone — every condition chip has a text label.

## 3. Typography

Two faces, no more.

- **Fraunces** (serif) — `display`, `headline`, and every Book title. This is the
  museum voice: wall labels and exhibit names.
- **Roboto** (sans) — `title`, `body`, `label`. This is the instrument voice:
  controls, metadata, numbers.

The MD3 type scale is unchanged in size; only the display and headline families
are reassigned to the serif. Labels are frequently set in small caps with wide
tracking (`label-small` + `--bl-tracking-placard`) to read as placards.

Numbers that sit in columns or change in place (counts, dates, page totals) use
`font-variant-numeric: tabular-nums` so they never jitter.

## 4. Shape, elevation and space

- **Shape** follows the MD3 corner scale (`--md-sys-shape-corner-*`). Exhibits
  use `corner-medium`; the big mounts use `corner-large`; buttons and chips are
  `full`.
- **Elevation** is warm-tinted shadow, not grey. Level 1 is the plinth; level 2
  is a card lifting on hover; level 3 is a modal.
- **Space** uses the `--bl-space-*` scale (4 → 64). Page gutters come from
  `.page`; section rhythm from `.section`.

## 5. Motion

Motion is deliberately small: the data changes at most daily, so the interface
does not pretend to be live.

- Hover lifts one elevation level over `short2`/`standard`.
- Progress meters fill once on mount (`bar-grow`), not continuously.
- Everything respects `prefers-reduced-motion`.

## 6. Honesty about freshness

Reading Statuses change when a book is begun, completed or abandoned — at most
daily. The Dashboard therefore states its freshness plainly with an **as-of**
line ("Last entry MMM D, YYYY") rather than implying a live feed. There are no
streaks, no live counters and no auto-refreshing numbers.

## 7. Components

Defined in `static/css/components.css`:

| Component | Class | Notes |
| --- | --- | --- |
| Button | `.btn` + `.btn-primary` / `.btn-tonal` / `.btn-outline` / `.btn-text` / `.btn-danger` | `--btn-*` custom properties drive the variants. |
| Icon button | `.btn-icon` | 48px target, circular state layer. |
| Floating action button | `.fab` | A screen's primary action, fixed bottom-right; one per screen. |
| Chip | `.chip`, `.chip-status` | Filter chips and condition chips. |
| Field | `.field`, `.field-input`, `.field-label` | Labels above, warm container, brass focus ring. |
| Exhibit | `.exhibit` | The book card. Plinth + framed cover + placard. |
| Placard | `.placard`, `.placard-row` | Wall-label metadata. |
| Meter | `.meter`, `.meter-fill` | Status and rating bars. |
| Panel | `.panel` | A tonal section mount on the Dashboard. |
| Skeleton | `.skeleton-*` | Shimmer placeholders in the plinth's own shape. |
| Empty state | `.empty-state` | Dashed mount, one clear action. |
| Modal | `.modal-overlay`, `.modal` | Scrim + raised surface. |

## 8. Layout

- `.app-container` — the Reading Room frame (header, main, footer).
- `.page` — centred content column, max 1100px.
- `.site-header` — sticky, tonal, brass hairline bottom edge.

Breakpoints: 1100px (grid reflow), 900px (dashboard grid stacks), 640px (mobile
nav and single column). Touch targets stay ≥ 44px.
