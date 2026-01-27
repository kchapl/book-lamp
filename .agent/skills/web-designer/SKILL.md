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
- **Separation**: Keep CSS in dedicated files, avoid inline styles.
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

### Design Review Checklist
- [ ] Visual hierarchy is clear
- [ ] Colour contrast meets WCAG AA standards
- [ ] All interactive elements are keyboard accessible
- [ ] Responsive design works across breakpoints
- [ ] Typography is readable and consistent
- [ ] Images have appropriate alt text
- [ ] Forms have proper labels and validation
- [ ] Loading and error states are designed
- [ ] Focus indicators are visible

### Browser Testing
- Test in multiple browsers (Chrome, Firefox, Safari, Edge).
- Test on real devices when possible.
- Use browser DevTools for responsive testing.

## Integration with Book Lamp

When designing pages for Book Lamp:
- **Consistency**: Follow existing design patterns in `book_lamp/static/base.css` and `books.css`.
- **Separation**: Keep CSS in dedicated files in `book_lamp/static/`.
- **Templates**: Work with Jinja2 templates in `book_lamp/templates/`.
- **British English**: Use British English in UI text (e.g., "Colour", "Organise").
- **Accessibility**: Ensure all new pages meet accessibility standards.

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
