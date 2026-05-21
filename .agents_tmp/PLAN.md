# 1. OBJECTIVE
Replace the current vanilla TypeScript frontend with a React implementation that is functionally identical to the existing application.

# 2. CONTEXT SUMMARY

## Current Architecture
- **Backend:** Flask with Jinja2 server-side templates
- **Frontend:** Vanilla TypeScript compiled to static JS files
- **Data Flow:** Server-rendered HTML with inline JS for interactivity
- **TypeScript Source:** `src/ts/` with compiled output to `book_lamp/static/`

## Current Pages/Features
| Page | Template | Key Interactions |
|------|----------|------------------|
| Home | `home.html` | Google One Tap auth, AI recommendations async load |
| Books | `books.html` | Search, filters, sorting, category filtering |
| History | `history.html` | Filter by status/rating/sort, inline edit records |
| Book Detail | `book_detail.html` | Edit book, add reading records, inline record edit |
| Reading List | `reading_list.html` | Drag-and-drop reorder |
| Add Book | `add_book.html` | Barcode scanner, ISBN lookup, manual entry |
| Import Books | `import_books.html` | CSV upload |
| Stats | `stats.html` | Static data display with links |
| Author/Publisher | `author.html`, `publisher.html` | Static data display |
| About | `about.html` | Static content |
| Base | `base.html` | Navigation, theme selector, settings, job indicator, modals |

## Key Interactive Components
1. **Navigation/Theme** - Theme switching with API persistence
2. **Job Indicator** - Polls `/api/jobs/<job_id>` for background job progress
3. **Recommendations** - Async fetch from `/api/recommendations`
4. **Barcode Scanner** - Uses `html5-qrcode` library
5. **Reading List Reorder** - Drag-and-drop with POST to save order
6. **Confirm Modals** - Global confirmation dialogs
7. **Button Feedback** - Loading states on form submission
8. **Sync Health Badge** - Polls `/api/sync/diagnostics`

# 3. APPROACH OVERVIEW

## Architecture Decision: Full React SPA

Replace all Jinja2 templates with a React Single Page Application (SPA) that communicates with the Flask backend via REST API endpoints. All existing URLs are preserved using React Router.

**Key Benefits:**
- Modern React architecture with component reusability
- Client-side routing for seamless navigation
- Shared state management across pages
- Better developer experience with React ecosystem

**Migration Strategy:**
1. Flask remains backend - serve JSON APIs + static assets
2. New React app in `src/react/` compiled by Vite to `book_lamp/static/react/`
3. Single `index.html` served by Flask (SPA entry point)
4. React Router handles all frontend routes
5. Existing API endpoints (`/api/*`) continue to work

# 4. IMPLEMENTATION STEPS

## Phase 1: Project Setup
1. **Install React and build tools**
   - Add React 18, React DOM, React Router DOM v6
   - Add Vite + TypeScript plugin for React
   - Add @dnd-kit for drag-and-drop functionality
   - Preserve existing CSS files for styling

2. **Configure Vite build system**
   - Create `vite.config.ts` with Flask static output path
   - Set `base: '/static/react/'` for asset paths
   - Configure proxy for API calls during development
   - Output to `book_lamp/static/react/`

3. **Create Flask SPA entry point**
   - Create `book_lamp/templates/index.html` (single React entry point)
   - Update Flask to serve index.html for non-API routes (SPA fallback)
   - Remove individual page template routes or keep for API-only mode

## Phase 2: Core Infrastructure
4. **Implement React Router and layout**
   - Create `src/react/App.tsx` with React Router
   - Implement `Layout` component (navigation, theme, settings, job indicator)
   - Port theme switching with API persistence
   - Add sync health badge polling

5. **Build API service layer**
   - Create `src/react/services/api.ts` with typed fetch wrappers
   - Add auth service for Google One Tap
   - Add job polling service for background tasks
   - Create TypeScript types matching API responses

6. **Implement shared components**
   - `ConfirmModal` - reusable confirmation dialog
   - `JobIndicator` - background job progress display
   - `Button` - with loading states
   - `StatusBadge` - reading status display
   - `BookCard` - book thumbnail with metadata

## Phase 3: Page Implementation

7. **Implement Home page** (`/`)
   - Google One Tap auth integration
   - Async recommendations loading with skeleton cards
   - Feature cards section
   - Unauthorised state with sign-in prompt

8. **Implement Books page** (`/books`, `/books?search=&status=&year=&category=`)
   - Book grid display with lazy loading images
   - Search form with query persistence
   - Filter controls (status, year, month, category, rating)
   - Sort dropdown
   - Category dropdown
   - Empty states for no results and empty bookshelf

9. **Implement Book Detail page** (`/books/:id`)
   - Book cover and metadata display
   - Edit mode toggle for book information
   - Reading records list with inline edit
   - Add reading record form
   - Delete book with confirmation

10. **Implement History page** (`/history`)
    - Reading history list grouped by book
    - Filter controls (status, min rating, sort)
    - Year filter with clear option
    - Inline record editing
    - Recommendations section (same as Home)

11. **Implement Reading List page** (`/reading-list`)
    - Draggable book list with @dnd-kit
    - Drag handle visual feedback
    - Reorder persistence on drop
    - Start Reading / Remove actions
    - Empty state

12. **Implement Add Book page** (`/books/new`)
    - ISBN input with barcode scanner button
    - Barcode scanner using html5-qrcode library
    - Manual entry toggle
    - Title, author, publisher, year fields
    - Add to reading list checkbox

13. **Implement Import Books page** (`/books/import`)
    - CSV file upload form
    - Fetch metadata checkbox
    - Info box with Libib export instructions

14. **Implement Stats page** (`/stats`)
    - Quick stats cards (total books, authors, records, avg rating)
    - Reading progress bars by status
    - Rating distribution bars
    - Top authors list
    - Top publishers list
    - Yearly completion timeline
    - Monthly completion timeline
    - Category distribution chart

15. **Implement Author page** (`/author/:slug`)
    - Author name header with book counts
    - Read books section
    - Reading list books section
    - Unread books from Open Library section
    - Add to reading list forms

16. **Implement Publisher page** (`/publisher/:slug`)
    - Publisher name header
    - Book grid display

17. **Implement About page** (`/about`)
    - App description
    - Version display

## Phase 4: Authentication & API Integration

18. **Implement authentication flow**
    - Google One Tap integration in Login page
    - Session handling
    - Protected route wrapper component
    - Unauthorised redirect page

19. **Connect API endpoints**
    - Review existing API routes in app.py
    - Create additional JSON endpoints if needed for SPA data fetching
    - Ensure all CRUD operations work via fetch

## Phase 5: Testing & Polish

20. **Update TypeScript configuration**
    - Extend `tsconfig.json` for React JSX
    - Configure path aliases

21. **Write React component tests**
    - Test all page components
    - Test shared components
    - Test API service functions

22. **Ensure existing Flask tests pass**
    - Run existing pytest suite
    - Update tests if API contracts changed

23. **Update documentation**
    - Update GEMINI.md with new frontend architecture
    - Update README with React build instructions

# 5. TESTING AND VALIDATION
- All existing Flask tests continue to pass
- New React component tests for all pages
- Manual testing checklist for each feature:
  - [ ] Authentication flow (Google One Tap)
  - [ ] Book CRUD operations
  - [ ] Reading history filtering
  - [ ] Reading list reordering
  - [ ] Barcode scanning
  - [ ] CSV import
  - [ ] Theme switching
  - [ ] Background job progress
  - [ ] Recommendations loading
