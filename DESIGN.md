# Design Specification: Personal Reading Tracker

## 1. Introduction
This document outlines the design system and visual language for the **Personal Reading Tracker** (The Editorial Archive). The goal is to create a digital space that feels as intentional and tactile as a well-curated private library.

## 2. Design System: The Editorial Archive

### Creative North Star: "The Modern Scholar"
This design system moves beyond the utility of a standard tracker to create an "Editorial Archive"—a space that feels as intentional and tactile as a well-curated private library. We are departing from the "app-like" density of traditional Material Design 3 in favor of a high-end, spacious layout that mimics the experience of reading a premium physical journal.

The system is defined by **intentional asymmetry**, **monochromatic depth**, and **typographic authority**. We reject the "flat" web; instead, we treat the screen as a series of stacked, high-quality paper stocks. The goal is to induce a state of "flow" for the reader, where the UI recedes and the content (the books) becomes the primary architecture.

---

### 2. Colors: The Tonal Palette
The palette is rooted in the "Book-Paper" off-white (`#faf9f3`) and "Deep Teal" (`#003331`). This high-contrast pairing provides a sophisticated, studious foundation that is easy on the eyes for long-form reading and logging.

#### The "No-Line" Rule
**Explicit Instruction:** Designers are prohibited from using 1px solid borders to define sections. Layout boundaries must be achieved exclusively through background color shifts.
*   **The Transition:** Use `surface` as your base. Transition to `surface-container-low` for secondary sidebars or `surface-container-high` for featured content areas. 

#### Surface Hierarchy & Nesting
Treat the UI as physical layers.
*   **The Foundation:** `surface` (#faf9f3)
*   **The Inset:** Use `surface-container-highest` (#e3e3dd) for recessed areas like search bars or metadata chips.
*   **The Lift:** Place a `surface-container-lowest` (#ffffff) card on top of a `surface-container-low` (#f5f4ee) background to create a "floating paper" effect without a single drop shadow.

#### The "Glass & Gradient" Rule
To elevate the experience, use **Glassmorphism** for floating headers or navigation bars. Use `surface` at 80% opacity with a 20px backdrop-blur. 
*   **Signature Textures:** For main CTAs, do not use flat colors. Apply a subtle linear gradient from `primary` (#003331) to `primary_container` (#004b49) at a 135-degree angle to add a "leather-bound" depth to the interaction.

---

### 3. Typography: The Editorial Scale
We use a pairing of **Manrope** (Display/Headline) for a contemporary, architectural feel and **Inter** (Body/Labels) for maximum legibility.

*   **Display (Manrope):** Use `display-lg` (3.5rem) with tight letter spacing (-0.02em) for "Current Read" titles. This creates an authoritative, magazine-style header.
*   **Headlines (Manrope):** `headline-md` (1.75rem) should be used for section titles (e.g., "Your Library").
*   **Body (Inter):** `body-lg` (1rem) is the workhorse. Increase line-height to 1.6 to ensure a "studious" reading pace.
*   **Labels (Inter):** `label-md` (0.75rem) in `on_surface_variant` (#3f4948) should be used for metadata like "ISBN" or "Page Count."

---

### 4. Elevation & Depth: Tonal Layering
In this system, "Elevation" is a color property, not a shadow property.

*   **The Layering Principle:** Stacking tiers (e.g., a `surface_container_lowest` card on a `surface_dim` background) creates natural prominence.
*   **Ambient Shadows:** If a floating action button (FAB) or a modal requires a shadow, it must be an "Ambient Glow." Use a 24px blur, 4% opacity, using the `on_surface` (#1b1c19) color. It should look like a soft atmospheric occlusion, not a dark smudge.
*   **The "Ghost Border" Fallback:** For input fields only, if a boundary is required, use `outline_variant` (#bfc8c7) at 20% opacity. 
*   **Glassmorphism:** Use for "Currently Reading" overlays. A semi-transparent `surface` layer allows book cover art to softly bleed through the UI, integrating the content with the system.

---

### 5. Components

#### Cards & Lists
*   **The Rule:** No dividers. Separate list items using 16px of vertical whitespace or a subtle toggle between `surface` and `surface-container-low`.
*   **Book Cards:** Large-format, using `md` (0.75rem) corner radius. The book cover should be the hero, with typography left-aligned and asymmetric.

#### Buttons
*   **Primary:** High-contrast `primary` (#003331) with `on_primary` (#ffffff) text. Use `full` (pill) roundedness for high-level actions (e.g., "Add New Book").
*   **Tertiary:** Text-only with `primary` color. Use for low-emphasis actions like "View All."

#### Chips
*   **Filter Chips:** Use `secondary_container` (#d2e3e2) with `on_secondary_container` (#566665). No borders. When selected, shift to `primary`.

#### Input Fields
*   **Style:** Minimalist. No "box" or \"line.\" Use a `surface_container_highest` (#e3e3dd) background with a `sm` (0.25rem) radius. Label sits above in `label-md`.

#### Reading Progress Bar
*   **Custom Component:** A thin, high-contrast bar. Track: `surface_variant`. Progress: `tertiary` (#49220a). The deep burnt orange of the tertiary color acts as a "bookmark" highlight against the teals.

---

### 6. Do's and Don'ts

#### Do
*   **Do** use extreme whitespace (32px+) to separate major sections.
*   **Do** use `tertiary` colors sparingly as "highlights" for progress or notifications.
*   **Do** ensure all "Book Paper" backgrounds (`surface`) maintain their warmth; avoid shifting toward pure white (#ffffff) except for the highest-level cards.

#### Don't
*   **Don't** use 1px dividers or lines. If you feel the need for a line, use a 4px gap of a different surface tone instead.
*   **Don't** use standard Material shadows (Level 1-5). Use tonal layering first, ambient shadows second.
*   **Don't** center-align long-form text. Maintain a "Left-Flush" editorial alignment to keep the "Modern Scholar" aesthetic.
*   **Don't** use high-saturation teals. Stick to the muted, sophisticated tones of the `primary` and `secondary` tokens.

---

## 3. Design Tokens (Folio Modern)

### Typography
- **Primary Font:** Manrope (Display, Headline)
- **Secondary Font:** Inter (Body, Label)
- **Headline Font:** Manrope
- **Body Font:** Inter
- **Label Font:** Inter

### Shape & Spacing
- **Roundness:** `ROUND_EIGHT` (Default 0.75rem)
- **Spacing Scale:** 2

### Color Palette (Tonal Groupings)
| Token | HEX Color | Usage |
| :--- | :--- | :--- |
| **Primary** | `#003331` | Brand color, main CTAs |
| **On Primary** | `#ffffff` | Text on primary |
| **Primary Container** | `#004b49` | Deep leather depth, signatures |
| **Secondary** | `#516160` | Muted secondary elements |
| **Tertiary** | `#49220a` | "Bookmark" orange, progress bars |
| **Background** | `#faf9f3` | Main "Paper" surface |
| **Surface** | `#faf9f3` | Base layer |
| **Surface Container Highest** | `#e3e3dd` | Recessed areas (search bars, etc.) |
| **Surface Container Lowest** | `#ffffff` | Floating cards (highest lift) |
| **Outline** | `#707978` | Tertiary borders (if absolutely needed) |

---

## 4. Project Screens
The following screens have been identified in the project:
1. **Home/Library Overview** (`40039fcce5bb4f538f0d4556e5e5e221`)
2. **Current Reading Detail** (`4e0be67b81ab4892b478e6136466e6f7`)
3. **Book List / Search Results** (`a732e98baf024403addf75ca3652d6bc`)
4. **Settings / Metadata Editor** (`dcb2fc242f404a039b66258d8c047928`)

---
*Created using Stitch MCP analysis of 'Personal Reading Tracker'.*
