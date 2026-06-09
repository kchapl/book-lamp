# 1. OBJECTIVE

Enhance the book-lamp "Statistics" page (renamed to "Dashboard") with additional insights, improved data visualisation, a redesigned category chart, and new metrics that provide better interactivity and value to the user.

# 2. CONTEXT SUMMARY

**Current Implementation:**
- **StatsPage.tsx**: React component displaying 8 statistics sections (overview cards, status bars, rating distribution, top authors/publishers, yearly/monthly trends, category distribution)
- **stats.css**: MD3-styled CSS for bar charts and card layouts
- **Types (index.ts)**: Stats interface with basic metrics and distributions
- **Backend**: Stats API endpoint serving aggregated data
- **Route**: Currently at `/stats` path

**Current Limitations:**
- Page named "Statistics" (less user-friendly than "Dashboard")
- Category chart uses simple horizontal bars with no interactivity
- No page count or reading duration statistics
- Monthly distribution only shows one year; no comparison view
- No interactive filtering or time period selection
- Rating distribution shows stars but no context
- Missing insight metrics (streaks, goals, reading velocity)

# 3. APPROACH OVERVIEW

Phase 1: Enhance the React component with richer statistics and interactivity
Phase 2: Redesign the category chart with a tree map / interactive bar layout
Phase 3: Add new backend data points for page counts, reading duration, streaks
Phase 4: Update TypeScript types and API to support new metrics

# 4. IMPLEMENTATION STEPS

## Step 0: Rename "Statistics" to "Dashboard"

**Goal:** Rename the page from "Statistics" to "Dashboard" for better user experience and modern conventions
**Method:** Update routes, navigation, and page content
**Reference:** `book_lamp/app.py`, `src/react/pages/StatsPage.tsx`, navigation components

**Changes:**
1. **Route**: `/stats` → `/dashboard` (add redirect from `/stats` for backwards compatibility)
2. **Navigation label**: "Statistics" → "Dashboard" in the nav menu
3. **Page title**: Change `<h1>` from "Statistics" to "Dashboard"
4. **Meta title**: Update browser tab title to "Dashboard - Book Lamp"
5. **Update tests**: Any test references to "stats" page paths
6. **Keep old route as alias**: 301 redirect from `/stats` to `/dashboard`

**Example redirect:**
```python
@app.route("/stats")
def stats_redirect():
    return redirect(url_for("dashboard"), code=301)
```

---

## Step 1: Update Stats TypeScript Interface

**Goal:** Add new fields for enhanced statistics
**Method:** Extend the `Stats` interface in `src/react/types/index.ts`
**Reference:** `src/react/types/index.ts`

Add the following new fields:
```typescript
interface Stats {
    // existing fields...
    
    // New: Page count statistics
    total_pages_read: number;
    avg_pages_per_book: number;
    
    // New: Reading duration estimates
    avg_reading_time_days: number;
    total_reading_days: number;
    
    // New: Reading streaks
    current_streak: number;
    longest_streak: number;
    
    // New: Goal tracking
    yearly_goal: number | null;
    books_this_year: number;
    goal_progress_percent: number;
    
    // New: Format distribution
    format_distribution: { label: string; count: number }[];
    
    // New: Language distribution  
    language_distribution: { label: string; count: number }[];
    
    // New: Top series
    top_series: { name: string; count: number; books: string[] }[];
    
    // New: Category breakdown with subcategories
    category_details: {
        label: string;
        count: number;
        subcategories: { name: string; count: number }[];
    }[];
    
    // New: Year-over-year comparison
    year_comparison: {
        current_year: number;
        previous_year: number;
        percentage_change: number;
    };
    
    // New: Reading pace (books per month, rolling average)
    reading_pace_monthly: number;
    reading_pace_annualised: number;
}
```

## Step 2: Backend - Calculate New Statistics

**Goal:** Compute new metrics in the backend
**Method:** Modify the stats API endpoint to calculate and return new statistics
**Reference:** `book_lamp/app.py` (stats route), `book_lamp/services/pg_storage.py`

New calculations to add:
- **Total pages**: Sum `page_count` across all completed books
- **Reading streaks**: Track consecutive months with reading activity
- **Yearly goal**: Retrieve from user settings or default to null
- **Format/language distribution**: Group by `physical_format` and `language` fields
- **Top series**: Group books by `series` field
- **Year-over-year comparison**: Compare current year completions to previous year

## Step 3: Redesign Category Chart

**Goal:** Replace horizontal bar chart with interactive tree map / zoomable visualization
**Method:** Create a new `CategoryChart` component with the following features:
**Reference:** `src/react/pages/StatsPage.tsx`

**Category Chart Improvements:**

1. **Treemap Layout** (recommended):
   - Rectangular areas proportional to book count
   - Click to zoom into subcategories
   - Colour-coded by main BISAC category
   - Hover tooltips showing book count and percentage

2. **Alternative: Interactive Bar Chart**:
   - Horizontal bars with larger hit areas
   - Expand/collapse for subcategories
   - Sortable by count or alphabetically
   - "Show top N" with "Show all" toggle

3. **Additional Features**:
   - Filter by year/time period
   - Search/filter within categories
   - Click category to see books in that category
   - Breadcrumb navigation for drill-down

**Proposed Component Structure:**
```tsx
const CategoryChart: React.FC<{
    categories: CategoryDetail[];
    onCategoryClick: (category: string) => void;
}> = ({ categories, onCategoryClick }) => {
    // Use CSS grid for treemap, or library like recharts
    // Add animation on hover/selection
}
```

## Step 4: Add Time Period Selector

**Goal:** Allow users to filter statistics by time period
**Method:** Add dropdown/tabs for "This Year", "Last Year", "All Time", "Custom Range"
**Reference:** `src/react/pages/StatsPage.tsx`

Add state:
```typescript
const [timePeriod, setTimePeriod] = useState<'year' | 'lastYear' | 'all'>('year');
```

Update API call to include `?period=year|lastYear|all`

## Step 5: Enhance Existing Visualisations

**Goal:** Improve readability and interactivity of existing charts
**Method:** Update each section with better tooltips, animations, and context

**Yearly Completions Chart:**
- Add trend line overlay
- Show percentage change from previous year
- Highlight current year

**Monthly Distribution:**
- Add year selector (compare multiple years)
- Overlay bars for year-over-year comparison
- Mark current month

**Rating Distribution:**
- Add average rating indicator
- Show percentage vs absolute count
- Interactive: click to see books with that rating

**Top Authors/Publishers:**
- Add "Show more" / pagination
- Click to see all books by that author/publisher

## Step 6: Add New Statistic Cards

**Goal:** Display key metrics at a glance
**Method:** Expand the overview section with new cards
**Reference:** `src/react/pages/StatsPage.tsx`

New cards:
1. **Total Pages Read** - with average per book
2. **Reading Streak** - current streak with fire icon 🔥
3. **Goal Progress** - circular progress indicator (if goal set)
4. **Reading Pace** - books per month, annualised

## Step 7: Update CSS Styling

**Goal:** Modernise the stats page visual design
**Method:** Update `stats.css` with:
**Reference:** `book_lamp/static/stats.css`

- Consistent card styling with hover states
- Better responsive layout (mobile-first)
- Animation improvements (staggered reveals)
- Dark mode refinements
- Improved tooltip styling

# 5. TESTING AND VALIDATION

**Success Criteria:**
1. Page renamed from "Statistics" to "Dashboard" with correct route `/dashboard`
2. Old route `/stats` redirects to `/dashboard` (301)
3. All existing stats continue to display correctly
4. New metrics are calculated and shown without errors
5. Category chart displays correctly with hover interactions
6. Time period selector filters data appropriately
7. Charts are responsive on mobile and desktop
8. No console errors during page load
9. Performance: page loads in < 2 seconds with 1000+ books

**Validation Approach:**
1. Run `npm run build` to ensure no TypeScript errors
2. Test with different data volumes (empty, small, large library)
3. Verify all interactive elements work (hover, click, filter)
4. Check responsive layout at multiple breakpoints
5. Test with both light and dark themes
6. Verify `/stats` redirects correctly to `/dashboard`
7. Test navigation links from other pages
