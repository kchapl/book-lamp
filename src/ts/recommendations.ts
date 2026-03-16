/**
 * Book Recommendations Component
 *
 * Asynchronously fetches AI-powered recommendations from /api/recommendations
 * and injects them into the #recommendations-section on the home page.
 * The dashboard renders immediately; this component loads in the background.
 */

interface Recommendation {
    id: number;
    title: string;
    author: string;
    isbn13: string;
    justification: string;
    created_at: string | null;
}

interface RecommendationsResponse {
    recommendations: Recommendation[];
    error?: string;
}

function buildSkeletonCards(count = 3): string {
    return Array.from({ length: count }, () => `
        <div class="rec-card rec-card--skeleton" aria-hidden="true">
            <div class="rec-skeleton-title"></div>
            <div class="rec-skeleton-author"></div>
            <div class="rec-skeleton-text"></div>
        </div>
    `).join('');
}

function buildRecCard(rec: Recommendation): string {
    const searchUrl = `https://openlibrary.org/search?q=${encodeURIComponent(rec.isbn13 || rec.title)}`;
    return `
        <a class="rec-card" href="${searchUrl}" target="_blank" rel="noopener noreferrer"
           id="rec-card-${rec.id}" aria-label="Recommendation: ${rec.title} by ${rec.author}">
            <div class="rec-card-inner">
                <div class="rec-sparkle" aria-hidden="true">✨</div>
                <h3 class="rec-title">${escapeHtml(rec.title)}</h3>
                <p class="rec-author">${escapeHtml(rec.author)}</p>
                <p class="rec-justification">${escapeHtml(rec.justification)}</p>
            </div>
        </a>
    `;
}

function escapeHtml(str: string): string {
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

async function loadRecommendations(): Promise<void> {
    const section = document.getElementById('recommendations-section');
    const grid = document.getElementById('recommendations-grid');
    const heading = document.getElementById('recommendations-heading');

    if (!section || !grid) return;

    // Show section with skeleton cards immediately
    section.style.display = 'block';
    grid.innerHTML = buildSkeletonCards();

    try {
        const response = await fetch('/api/recommendations');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data: RecommendationsResponse = await response.json();

        if (!data.recommendations || data.recommendations.length === 0) {
            // Hide the whole section gracefully — no error noise for users
            section.style.display = 'none';
            return;
        }

        // Animate cards in after short delay
        grid.innerHTML = data.recommendations.map(buildRecCard).join('');
        grid.querySelectorAll<HTMLElement>('.rec-card').forEach((card, i) => {
            card.style.animationDelay = `${i * 80}ms`;
            card.classList.add('rec-card--animate-in');
        });

        if (heading) {
            heading.style.display = 'block';
        }

    } catch (err) {
        // Silently hide the section — recommendations are non-critical
        console.debug('[recommendations] Could not load recommendations:', err);
        section.style.display = 'none';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    // Only run on pages that have the recommendations section
    const section = document.getElementById('recommendations-section');
    if (section) {
        loadRecommendations();
    }
});
