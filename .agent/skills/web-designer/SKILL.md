---
name: web-designer
description: Provides guidance on web page design principles, UI/UX best practices, accessibility, and modern design patterns for creating beautiful and functional web interfaces.
---

# Web Page Designer Skill

This skill enables the agent to act as a web design mentor, providing guidance on creating beautiful, accessible, and user-friendly web pages.

## Core Design Principles

### 1. Visual Hierarchy
- **Importance through Size**: Larger elements draw attention first.
- **Contrast**: Use colour, size, and spacing to create visual distinction.
- **Whitespace**: Adequate spacing prevents visual clutter and improves readability.
- **Typography Scale**: Use consistent, hierarchical font sizes (e.g., headings, body, captions).

### 2. Consistency
- **Design System**: Maintain consistent colours, fonts, spacing, and component styles throughout the site.
- **Patterns**: Reusable UI components create familiarity and reduce cognitive load.
- **Navigation**: Keep navigation patterns consistent across pages.

### 3. Accessibility First
- **Semantic HTML**: Use proper HTML elements (`<header>`, `<nav>`, `<main>`, `<article>`, `<footer>`).
- **Colour Contrast**: Ensure WCAG AA compliance (minimum 4.5:1 for normal text, 3:1 for large text).
- **Keyboard Navigation**: All interactive elements must be keyboard accessible.
- **Alt Text**: Provide descriptive alt text for images.
- **ARIA Labels**: Use ARIA attributes when semantic HTML isn't sufficient.

### 4. Responsive Design
- **Mobile-First**: Design for mobile devices first, then enhance for larger screens.
- **Breakpoints**: Use consistent breakpoints (e.g., 768px, 1024px, 1280px).
- **Flexible Layouts**: Use CSS Grid and Flexbox for adaptable layouts.
- **Touch Targets**: Ensure interactive elements are at least 44×44px for touch devices.

## Design Elements

### Colour
- **Palette**: Limit to 2-3 primary colours plus neutrals (greys, whites, blacks).
- **Meaning**: Use colour consistently (e.g., red for errors, green for success).
- **Accessibility**: Never rely solely on colour to convey information.
- **Contrast**: Test colour combinations for readability.

### Typography
- **Font Families**: Limit to 2-3 font families (one for headings, one for body).
- **Line Height**: Use 1.5-1.6 for body text, tighter for headings.
- **Line Length**: Keep lines between 50-75 characters for optimal readability.
- **Font Loading**: Use `font-display: swap` to prevent invisible text during font load.

#### Font Size Accessibility Requirements
**CRITICAL**: All text must meet minimum size requirements for accessibility:

- **Body Text**: Minimum 1rem (16px) for primary content
- **Small Text**: Minimum 0.875rem (14px) for secondary content
  - Examples: captions, labels, metadata
  - Never go below 0.875rem for any readable text
- **Micro Text**: 0.75rem-0.8rem (12px-13px) ONLY for:
  - Non-essential decorative badges
  - Uppercase labels with increased letter-spacing
  - Must have sufficient contrast (7:1 for WCAG AAA)
- **Never Use**: Font sizes below 0.75rem (12px) are not accessible

#### Font Size Scale (Book Lamp Standard)
```css
/* Headings */
h1: 2.5rem-3rem     /* Page titles */
h2: 1.75rem-2rem    /* Section headings */
h3: 1.25rem-1.5rem  /* Subsection headings */

/* Body Text */
body: 1rem          /* Default, never smaller */
large: 1.1rem-1.25rem /* Emphasis text */

/* Secondary Text */
metadata: 0.95rem   /* Book metadata, dates */
labels: 0.875rem    /* Form labels, captions */
badges: 0.8rem      /* Status badges (uppercase) */

/* AVOID */
< 0.875rem          /* Too small for general use */
< 0.75rem           /* Never use, inaccessible */
```

#### Readability Guidelines
- **Contrast Ratio**: Minimum 4.5:1 for normal text, 3:1 for large text (18pt+)
- **Letter Spacing**: Increase for uppercase text (0.05em-0.1em)
- **Font Weight**: Use 400-600 for body, 600-700 for headings
- **Responsive Sizing**: Text should scale appropriately on mobile devices


### Spacing
- **Consistent Scale**: Use a spacing scale (e.g., 4px, 8px, 16px, 24px, 32px).
- **Vertical Rhythm**: Maintain consistent vertical spacing between elements.
- **Padding vs Margin**: Use padding for internal spacing, margin for external spacing.

### Imagery
- **Purpose**: Every image should serve a purpose (informative, decorative, or functional).
- **Optimization**: Compress images and use appropriate formats (WebP, AVIF when supported).
- **Responsive Images**: Use `srcset` and `sizes` for responsive images.
- **Lazy Loading**: Implement lazy loading for images below the fold.

## UI/UX Best Practices

### User Experience
- **Clear Navigation**: Users should always know where they are and how to get where they want to go.
- **Feedback**: Provide immediate feedback for user actions (hover states, loading indicators, success/error messages).
- **Error Prevention**: Design forms and interactions to prevent errors before they occur.
- **Progressive Disclosure**: Show information progressively to avoid overwhelming users.

### Interaction Design
- **Hover States**: All interactive elements should have clear hover states.
- **Focus States**: Visible focus indicators are essential for keyboard navigation.
- **Loading States**: Show loading indicators for async operations.
- **Empty States**: Design helpful empty states that guide users.

### Forms
- **Labels**: Every input must have an associated label.
- **Placeholders**: Use placeholders as hints, not replacements for labels.
- **Validation**: Provide inline validation feedback.
- **Error Messages**: Clear, actionable error messages near the relevant field.

## Modern Design Patterns

### Component-Based Design
- **Reusability**: Design components that can be reused across pages.
- **Composition**: Build complex interfaces from simple components.
- **Variants**: Use consistent variants (primary, secondary, disabled states).

### CSS Architecture
- **Separation (CRITICAL)**: serve all CSS from dedicated `.css` files in `book_lamp/static/`. **Avoid inline `<style>` blocks in HTML templates at all costs.**
- **Naming**: Use consistent naming conventions (BEM, utility classes, or component-based).
- **Specificity**: Keep CSS specificity low to avoid conflicts.
- **Variables**: Use CSS custom properties for theming and consistency.

### Performance
- **Critical CSS**: Inline critical CSS for above-the-fold content.
- **Minification**: Minify CSS and JavaScript for production.
- **Unused CSS**: Remove unused CSS to reduce file size.
- **Animations**: Use CSS transforms and opacity for performant animations.

## Design Tools and Workflow

### Design Process
1. **Research**: Understand users, goals, and constraints.
2. **Wireframing**: Create low-fidelity layouts to establish structure.
3. **Prototyping**: Build interactive prototypes to test interactions.
4. **Visual Design**: Apply colours, typography, and imagery.
5. **Implementation**: Translate designs to code with attention to detail.

### CSS Frameworks
- **When to Use**: Consider frameworks for rapid prototyping or consistent design systems.
- **Customisation**: Ensure frameworks can be customised to match brand identity.
- **Bundle Size**: Be mindful of framework size and only include what's needed.

## Common Patterns

### Navigation
- **Sticky Navigation**: Consider sticky headers for long pages.
- **Breadcrumbs**: Use breadcrumbs for deep navigation hierarchies.
- **Mobile Menu**: Design clear, accessible mobile navigation patterns.

### Cards
- **Consistent Padding**: Use consistent padding within cards.
- **Shadows**: Subtle shadows help cards stand out from backgrounds.
- **Hover Effects**: Add subtle hover effects for interactive cards.

### Buttons
- **Hierarchy**: Primary, secondary, and tertiary button styles.
- **States**: Normal, hover, active, disabled, and loading states.
- **Size**: Consistent button sizes for similar actions.

### Modals and Overlays
- **Focus Management**: Trap focus within modals.
- **Escape Key**: Allow closing modals with Escape key.
- **Backdrop**: Use semi-transparent backdrop to focus attention.

## Testing and Validation

### Lighthouse Accessibility Standards

**Google Lighthouse** is the primary tool for ensuring accessibility compliance. All pages should score **90+** on accessibility.

#### Running Lighthouse Tests

**Option 1: Chrome DevTools** (Recommended for development)
1. Open Chrome DevTools (F12)
2. Navigate to "Lighthouse" tab
3. Select "Accessibility" category
4. Choose "Desktop" or "Mobile" device
5. Click "Analyze page load"
6. Review and fix all issues

**Option 2: Command Line** (For CI/CD)
```bash
# Install Lighthouse
npm install -g lighthouse

# Run accessibility audit
lighthouse http://localhost:5000 --only-categories=accessibility --view

# Run for specific page
lighthouse http://localhost:5000/books --only-categories=accessibility --output html --output-path ./lighthouse-report.html
```

**Option 3: PageSpeed Insights** (For production)
- Visit: https://pagespeed.web.dev/
- Enter your production URL
- Review accessibility score and recommendations

#### Lighthouse Accessibility Checklist

**Critical Issues (Must Fix)**
- [ ] **Colour Contrast**: All text meets WCAG AA (4.5:1 for normal, 3:1 for large)
- [ ] **Form Labels**: Every `<input>`, `<select>`, `<textarea>` has an associated `<label>`
- [ ] **Alt Text**: All `<img>` elements have descriptive `alt` attributes
- [ ] **Button Names**: All buttons have accessible names (text content or `aria-label`)
- [ ] **Link Names**: All links have descriptive text (avoid "click here")
- [ ] **HTML Lang**: `<html>` element has `lang` attribute (`<html lang="en">`)
- [ ] **Document Title**: Every page has a unique, descriptive `<title>`
- [ ] **Heading Order**: Headings follow logical order (h1 → h2 → h3, no skipping)
- [ ] **Landmark Regions**: Use semantic HTML (`<header>`, `<nav>`, `<main>`, `<footer>`)

**Important Issues (Should Fix)**
- [ ] **Focus Indicators**: All interactive elements have visible focus states
- [ ] **Skip Links**: Provide "skip to main content" link for keyboard users
- [ ] **ARIA Labels**: Use ARIA attributes where semantic HTML isn't sufficient
- [ ] **Touch Targets**: Interactive elements are at least 48×48px (44×44px minimum)
- [ ] **Viewport Meta**: Include `<meta name="viewport">` for responsive design
- [ ] **Font Sizes**: All text meets minimum size requirements (see Typography section)
- [ ] **List Structure**: Use `<ul>`, `<ol>`, `<li>` for lists, not `<div>` with bullets

**Best Practices**
- [ ] **Keyboard Navigation**: All functionality available via keyboard (Tab, Enter, Escape)
- [ ] **Error Messages**: Form validation errors are clear and associated with fields
- [ ] **Loading States**: Indicate loading/processing states to users
- [ ] **Modal Focus**: Trap focus within modals, restore on close
- [ ] **Disabled States**: Clearly indicate disabled interactive elements

#### Common Lighthouse Failures and Fixes

**1. Background and Foreground Colours Do Not Have Sufficient Contrast**
```css
/* ❌ WRONG - Insufficient contrast */
.text-muted {
    color: #666;  /* 3.2:1 on white background */
}

/* ✅ CORRECT - Meets WCAG AA */
.text-muted {
    color: #6b7280;  /* 4.6:1 on white background */
}
```

**2. Form Elements Do Not Have Associated Labels**
```html
<!-- ❌ WRONG - No label -->
<input type="text" name="title" placeholder="Book title">

<!-- ✅ CORRECT - Explicit label -->
<label for="book-title">Book Title</label>
<input type="text" id="book-title" name="title">

<!-- ✅ ALSO CORRECT - Implicit label -->
<label>
    Book Title
    <input type="text" name="title">
</label>
```

**3. Image Elements Do Not Have Alt Attributes**
```html
<!-- ❌ WRONG - No alt text -->
<img src="cover.jpg">

<!-- ✅ CORRECT - Descriptive alt -->
<img src="cover.jpg" alt="Cover of Pride and Prejudice by Jane Austen">

<!-- ✅ CORRECT - Decorative image -->
<img src="decoration.svg" alt="" role="presentation">
```

**4. Buttons Do Not Have an Accessible Name**
```html
<!-- ❌ WRONG - Icon-only button with no label -->
<button onclick="deleteBook()">🗑️</button>

<!-- ✅ CORRECT - With aria-label -->
<button onclick="deleteBook()" aria-label="Delete book">🗑️</button>

<!-- ✅ CORRECT - With title (also shows tooltip) -->
<button onclick="deleteBook()" title="Delete book">🗑️</button>
```

**5. Heading Elements Are Not in Sequentially Descending Order**
```html
<!-- ❌ WRONG - Skips h2 -->
<h1>Book Details</h1>
<h3>Description</h3>

<!-- ✅ CORRECT - Logical order -->
<h1>Book Details</h1>
<h2>Description</h2>
```

#### Book Lamp Specific Accessibility Checks

**Templates to Audit**
- [ ] `base.html` - Navigation, footer, modal
- [ ] `index.html` - Landing page
- [ ] `books.html` - Book list/grid
- [ ] `book_detail.html` - Book details, reading records
- [ ] `history.html` - Reading history
- [ ] `stats.html` - Statistics page
- [ ] `search.html` - Search results
- [ ] `import.html` - Import form

**Common Patterns to Verify**
```html
<!-- ✅ Book cards have proper structure -->
<article class="book-card">
    <a href="/books/123">
        <img src="cover.jpg" alt="Cover of [Book Title]">
    </a>
    <h2><a href="/books/123">[Book Title]</a></h2>
    <p class="author">by [Author Name]</p>
</article>

<!-- ✅ Forms have proper labels -->
<form>
    <div class="form-group">
        <label for="status">Status</label>
        <select id="status" name="status" required>
            <option value="In Progress">In Progress</option>
        </select>
    </div>
</form>

<!-- ✅ Icon buttons have accessible names -->
<button type="button" class="btn-icon" 
        onclick="setEditMode(true)" 
        title="Edit Book" 
        aria-label="Edit book">✏️</button>
```

### Design Review Checklist
- [ ] Visual hierarchy is clear
- [ ] Colour contrast meets WCAG AA standards (4.5:1 minimum)
- [ ] All interactive elements are keyboard accessible
- [ ] Responsive design works across breakpoints (mobile, tablet, desktop)
- [ ] Typography is readable and meets minimum sizes
- [ ] Images have appropriate alt text
- [ ] Forms have proper labels and validation
- [ ] Loading and error states are designed
- [ ] Focus indicators are visible (not `outline: none` without replacement)
- [ ] Touch targets are at least 44×44px
- [ ] Lighthouse accessibility score is 90+

### Browser Testing
- Test in multiple browsers (Chrome, Firefox, Safari, Edge).
- Test on real devices when possible.
- Use browser DevTools for responsive testing.
- Test keyboard navigation (Tab, Shift+Tab, Enter, Escape).
- Test with screen reader (NVDA on Windows, VoiceOver on Mac).

### Automated Testing Tools
- **Lighthouse**: Built into Chrome DevTools
- **axe DevTools**: Browser extension for detailed accessibility testing
- **WAVE**: Web accessibility evaluation tool (browser extension)
- **Pa11y**: Command-line accessibility testing tool
- **Contrast Checker**: https://webaim.org/resources/contrastchecker/

### Lighthouse Performance Standards

**Target Score: 90+** for all pages. Performance directly impacts user experience and SEO.

#### Performance Metrics

**Core Web Vitals** (Google ranking factors):
- **LCP (Largest Contentful Paint)**: < 2.5s (Good)
  - Measures loading performance
  - Optimize images, reduce server response time
- **FID (First Input Delay)**: < 100ms (Good)
  - Measures interactivity
  - Minimize JavaScript execution time
- **CLS (Cumulative Layout Shift)**: < 0.1 (Good)
  - Measures visual stability
  - Reserve space for images, avoid layout shifts

**Other Key Metrics**:
- **FCP (First Contentful Paint)**: < 1.8s
- **TTI (Time to Interactive)**: < 3.8s
- **Speed Index**: < 3.4s
- **Total Blocking Time**: < 200ms

#### Performance Optimization Checklist

**Images**
- [ ] Use modern formats (WebP, AVIF) with fallbacks
- [ ] Compress images (TinyPNG, ImageOptim)
- [ ] Use appropriate sizes (don't serve 2000px images for 200px display)
- [ ] Implement lazy loading for below-fold images
- [ ] Provide `width` and `height` attributes to prevent CLS
- [ ] Use `srcset` for responsive images

**CSS**
- [ ] Minify CSS files for production
- [ ] Remove unused CSS
- [ ] Inline critical CSS for above-the-fold content
- [ ] Use CSS containment for complex layouts
- [ ] Avoid `@import` (use `<link>` instead)

**JavaScript**
- [ ] Minify JavaScript files
- [ ] Defer non-critical JavaScript
- [ ] Use `async` or `defer` attributes on script tags
- [ ] Code-split large bundles
- [ ] Remove unused JavaScript
- [ ] Avoid long-running scripts

**Fonts**
- [ ] Use `font-display: swap` to prevent invisible text
- [ ] Preconnect to font origins (`<link rel="preconnect">`)
- [ ] Subset fonts to include only needed characters
- [ ] Use system fonts when appropriate

**Caching**
- [ ] Set appropriate cache headers
- [ ] Use service workers for offline support
- [ ] Implement browser caching for static assets
- [ ] Use CDN for static resources

**Server**
- [ ] Enable compression (gzip, brotli)
- [ ] Minimize server response time (< 200ms)
- [ ] Use HTTP/2 or HTTP/3
- [ ] Implement proper caching strategies

#### Book Lamp Performance Tips

```html
<!-- ✅ Optimize images -->
<img src="cover.webp" 
     alt="Book cover" 
     width="300" 
     height="450"
     loading="lazy">

<!-- ✅ Preconnect to external resources -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>

<!-- ✅ Defer non-critical JavaScript -->
<script src="/static/analytics.js" defer></script>

<!-- ✅ Use font-display swap -->
@font-face {
    font-family: 'Outfit';
    font-display: swap;
    src: url('outfit.woff2') format('woff2');
}
```

### Lighthouse Best Practices Standards

**Target Score: 90+** for security, reliability, and modern web standards.

#### Best Practices Checklist

**Security**
- [ ] Use HTTPS for all pages
- [ ] No mixed content (HTTP resources on HTTPS pages)
- [ ] Set secure headers (CSP, X-Frame-Options, etc.)
- [ ] Use `rel="noopener"` for external links with `target="_blank"`
- [ ] Avoid deprecated APIs and features

**Browser Compatibility**
- [ ] Avoid browser errors in console
- [ ] Use feature detection, not browser detection
- [ ] Provide fallbacks for modern features
- [ ] Test in multiple browsers

**Modern Standards**
- [ ] Use HTTPS
- [ ] Avoid document.write()
- [ ] Use passive event listeners for scroll/touch
- [ ] Avoid synchronous XMLHttpRequest
- [ ] Use proper DOCTYPE (`<!DOCTYPE html>`)

**Images**
- [ ] Use appropriate aspect ratios
- [ ] Avoid oversized images
- [ ] Use correct image formats
- [ ] Provide alt text for all images

**JavaScript**
- [ ] Avoid `eval()` and similar unsafe patterns
- [ ] Use strict mode (`'use strict';`)
- [ ] Handle errors gracefully
- [ ] Avoid memory leaks

#### Common Best Practices Issues

```html
<!-- ❌ WRONG - Opens security vulnerability -->
<a href="https://external-site.com" target="_blank">Link</a>

<!-- ✅ CORRECT - Secure external link -->
<a href="https://external-site.com" target="_blank" rel="noopener noreferrer">Link</a>

<!-- ❌ WRONG - Mixed content on HTTPS -->
<script src="http://example.com/script.js"></script>

<!-- ✅ CORRECT - Use HTTPS or protocol-relative -->
<script src="https://example.com/script.js"></script>

<!-- ❌ WRONG - Deprecated API -->
document.write('<p>Content</p>');

<!-- ✅ CORRECT - Use DOM manipulation -->
const p = document.createElement('p');
p.textContent = 'Content';
document.body.appendChild(p);
```

### Lighthouse SEO Standards

**Target Score: 90+** for search engine visibility and discoverability.

#### SEO Checklist

**Document Structure**
- [ ] Every page has a unique, descriptive `<title>` (50-60 characters)
- [ ] Every page has a `<meta name="description">` (150-160 characters)
- [ ] HTML has `lang` attribute (`<html lang="en">`)
- [ ] Viewport meta tag is present and valid
- [ ] Document uses legible font sizes (≥ 12px, preferably ≥ 14px)

**Content**
- [ ] Page has a single `<h1>` element
- [ ] Headings follow logical hierarchy (h1 → h2 → h3)
- [ ] Links have descriptive text (avoid "click here")
- [ ] Images have descriptive alt text
- [ ] Content is unique and valuable

**Technical SEO**
- [ ] Page is crawlable (no `noindex`, robots.txt allows)
- [ ] Page is mobile-friendly
- [ ] HTTPS is used
- [ ] Canonical URLs are set (if needed)
- [ ] Structured data is valid (if used)
- [ ] No broken links (404s)

**Performance** (SEO factor)
- [ ] Page loads quickly (< 3s)
- [ ] Core Web Vitals are good
- [ ] Mobile performance is optimized

#### Book Lamp SEO Implementation

```html
<!-- ✅ Complete SEO head section -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    
    <!-- Unique title for each page -->
    <title>Pride and Prejudice by Jane Austen - Book Lamp</title>
    
    <!-- Descriptive meta description -->
    <meta name="description" content="Track your reading of Pride and Prejudice by Jane Austen. View book details, reading history, and personal notes in Book Lamp.">
    
    <!-- Open Graph for social sharing -->
    <meta property="og:title" content="Pride and Prejudice - Book Lamp">
    <meta property="og:description" content="Track your reading progress and history">
    <meta property="og:type" content="website">
    
    <!-- Favicon -->
    <link rel="icon" type="image/png" href="/static/favicon.png">
</head>
```

**Page-Specific SEO Examples**:

```python
# In Flask routes, set unique titles and descriptions
@app.route('/books/<int:book_id>')
def book_detail(book_id):
    book = storage.get_book_by_id(book_id)
    return render_template('book_detail.html', 
        book=book,
        page_title=f"{book['title']} by {book['author']} - Book Lamp",
        page_description=f"View details and reading history for {book['title']} by {book['author']}"
    )
```

```html
<!-- In base.html template -->
<title>{% block title %}Book Lamp - Track Your Reading{% endblock %}</title>
<meta name="description" content="{% block description %}Organize and track your personal book collection with Book Lamp{% endblock %}">

<!-- In book_detail.html -->
{% block title %}{{ page_title }}{% endblock %}
{% block description %}{{ page_description }}{% endblock %}
```

#### SEO Content Guidelines

**Title Tag Best Practices**:
- Include primary keyword
- Keep under 60 characters
- Make it unique per page
- Include brand name (Book Lamp)
- Format: `Primary Keyword - Secondary | Brand`

**Meta Description Best Practices**:
- Summarize page content
- Include call-to-action
- Keep under 160 characters
- Make it compelling and unique
- Include relevant keywords naturally

**Heading Structure**:
```html
<!-- ✅ CORRECT - Logical hierarchy -->
<h1>Book Details: Pride and Prejudice</h1>
<h2>About This Book</h2>
<h3>Author Information</h3>
<h3>Publication Details</h3>
<h2>Reading History</h2>
<h3>Current Reading Status</h3>
```

### Lighthouse Score Targets

**Production Standards** (all pages should meet):
- **Performance**: 90+ (85+ acceptable for complex pages)
- **Accessibility**: 95+ (90+ minimum)
- **Best Practices**: 95+ (90+ minimum)
- **SEO**: 95+ (90+ minimum)

**How to Check All Categories**:
```bash
# Run complete Lighthouse audit
lighthouse http://localhost:5000 --view

# Run for production
lighthouse https://your-domain.com --view

# Generate report for all pages
lighthouse http://localhost:5000 --output html --output-path ./reports/home.html
lighthouse http://localhost:5000/books --output html --output-path ./reports/books.html
lighthouse http://localhost:5000/history --output html --output-path ./reports/history.html
```


## Integration with Book Lamp

When designing pages for Book Lamp:
- **Consistency**: Follow existing design patterns in `book_lamp/static/base.css` and `books.css`.
- **Separation**: Keep CSS in dedicated files in `book_lamp/static/`.
- **Templates**: Work with Jinja2 templates in `book_lamp/templates/`.
- **British English**: All language shown in the UI MUST be in **British English** (e.g., "Colour", "Organise", "Authorise", "Catalogue").
- **Accessibility**: All new pages MUST meet accessibility standards and score 90+ in Lighthouse audits.

### Book Lamp Visual Language

#### Colour Palette
- **Primary**: `#6366f1` (Indigo) - Used for primary actions and accents
- **Primary Light**: `#818cf8` - Hover states and highlights
- **Background**: `#0f172a` (Dark slate) - Main background
- **Card Background**: `rgba(30, 41, 59, 0.7)` - Semi-transparent card backgrounds
- **Text**: `#f8fafc` (Off-white) - Primary text colour
- **Text Muted**: `#94a3b8` (Slate grey) - Secondary text and labels
- **Glass**: `rgba(255, 255, 255, 0.05)` - Glassmorphism effect
- **Glass Border**: `rgba(255, 255, 255, 0.1)` - Subtle borders

#### Typography
- **Headings**: 'Playfair Display', serif - Elegant, classical feel for titles
- **Body**: 'Outfit', sans-serif - Clean, modern readability
- **Font Loading**: Fonts loaded from Google Fonts with preconnect for performance

#### Visual Effects
- **Glassmorphism**: Semi-transparent backgrounds with backdrop blur for cards and navigation
- **Gradients**: Radial gradients in background for depth and visual interest
- **Shadows**: Layered shadows for elevation and depth (e.g., `0 25px 50px -12px rgba(0, 0, 0, 0.5)`)
- **Border Radius**: Generous border radius (12px-24px) for modern, friendly appearance
- **Transitions**: Smooth transitions (0.2s-0.3s) for interactive elements

### Edit Mode Pattern

Book Lamp uses a consistent **view/edit mode toggle pattern** for managing content:

#### View Mode (Default)
- **Display**: Shows content in read-only format with full styling
- **Controls**: Edit (✏️) and Delete (🗑️) icon buttons positioned at **bottom right** of content cards
- **Icon Styling**: Uses `.btn-icon` class - transparent background, subtle hover states
- **Visual Indicator**: No special indicator needed; this is the default state

#### Edit Mode (Activated)
- **Activation**: Click the edit icon (✏️) to enter edit mode
- **Display**: Form inputs replace static content using `.edit-input` and `.edit-textarea` classes
- **Controls**: Save and Cancel buttons replace the edit/delete icons at **bottom right**
- **Button Styling**: 
  - Save: `.btn-save` - Green background (`#10b981`)
  - Cancel: `.btn-cancel` - Transparent with border
- **Data Attributes**: Use `data-edit-mode="true"` on container to toggle visibility

#### Implementation Classes
```css
.view-only { /* Visible by default */ }
.edit-only { display: none; }

[data-edit-mode="true"] .view-only { display: none !important; }
[data-edit-mode="true"] .edit-only { display: block !important; }
```

#### Icon Positioning Rules
1. **Bottom Right Placement**: Edit and delete icons always appear at the bottom right of their content card
2. **Horizontal Layout**: Icons arranged horizontally with 0.5rem gap
3. **Border Separation**: Icons separated from content with top border and padding
4. **Consistent Sizing**: Icons use 1.1rem font-size with 0.4rem padding

### Deletion Confirmation Pattern

**All deletion operations MUST use a confirmation modal** to prevent accidental data loss:

#### Confirmation Modal
- **Component**: Custom modal in `base.html` with ID `confirm-modal`
- **Function**: `showConfirm(title, message, onConfirm)` - Global function for confirmations
- **Styling**: Dark background (`#1e293b`), glassmorphism effect, smooth animation
- **Actions**: Cancel (secondary) and Delete (danger red `#ef4444`) buttons

#### Usage Pattern
```javascript
// DO use confirmation modal
function deleteRecord(recordId, deleteUrl) {
    showConfirm(
        'Delete Record',
        'Remove this reading record from your history?',
        () => submitPostRequest(deleteUrl)
    );
}

// DON'T use browser confirm()
function deleteRecord(recordId, deleteUrl) {
    if (confirm('Delete?')) { // ❌ WRONG - not consistent with design
        submitPostRequest(deleteUrl);
    }
}
```

#### Confirmation Messages
- **Title**: Short, action-oriented (e.g., "Delete Book", "Delete Record")
- **Message**: Clear consequences, use "Remove" or "Delete" consistently
- **Tone**: Informative but not alarming; explain what will be deleted
- **Examples**:
  - Books: "Permanently remove this book and all its reading history? This cannot be undone."
  - Records: "Remove this reading record from your history?"

### Form Input Styling

All form inputs in edit mode use consistent styling:

```css
.edit-input, select.edit-input {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid var(--glass-border);
    border-radius: 8px;
    color: white;
    padding: 0.5rem;
}

select.edit-input option {
    background: #1e293b;  /* Dark background for dropdown options */
    color: white;
    padding: 0.5rem;
}
```

**Important**: Always style `select` option elements to ensure visibility against dark backgrounds.

### Data Attribute Pattern

To avoid quote nesting issues in HTML attributes, use data attributes for dynamic values:

```html
<!-- ✅ CORRECT - Using data attributes -->
<button type="button" class="btn-icon"
    data-record-id="{{ record.id }}"
    data-delete-url="{{ url_for('delete_reading_record', record_id=record.id) }}"
    onclick="deleteRecord(this.dataset.recordId, this.dataset.deleteUrl)">
    🗑️
</button>

<!-- ❌ WRONG - Quote nesting causes IDE errors -->
<button onclick="deleteRecord('{{ record.id }}', '{{ url_for(...) }}')">
```

## Resources and References

- **WCAG Guidelines**: https://www.w3.org/WAI/WCAG21/quickref/
- **WebAIM Contrast Checker**: https://webaim.org/resources/contrastchecker/
- **MDN Web Docs**: https://developer.mozilla.org/
- **A11y Project**: https://www.a11yproject.com/
