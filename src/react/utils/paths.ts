/**
 * Paths that name a page derived from a Book's metadata.
 *
 * Author slugs have always had one spelling on the server: lowercased, spaces
 * to hyphens, dots dropped. The Dashboard and the Book page each had their own
 * copy of that rule, and the copies disagreed on punctuation — a name with an
 * initial in it linked to a page the server could not find. The rule lives here
 * once so every call site produces the same URL.
 *
 * A publisher's page is keyed on the normalised name (its corporate suffixes
 * are stripped server-side), so the API supplies `publisher_slug` for it.
 * Applying `slug` to that value is idempotent and keeps one spelling helper.
 */

/** The server's frozen author rule, also used for publisher segments. */
export function slug(name: string): string {
    return name.toLowerCase().replace(/ /g, '-').replace(/\./g, '');
}

/** The page about one Author. */
export function authorPath(name: string): string {
    return `/author/${encodeURIComponent(slug(name))}`;
}

/** The page about one Publisher. */
export function publisherPath(nameOrSlug: string): string {
    return `/publisher/${encodeURIComponent(slug(nameOrSlug))}`;
}

/** The collection, filtered to one category label. */
export function categoryPath(label: string): string {
    return `/books?category=${encodeURIComponent(label)}`;
}
