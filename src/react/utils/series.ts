/**
 * A series name as a URL segment.
 *
 * A series has no record of its own: the name is free text on each Book, with
 * the punctuation real series carry ("Mistborn: Era 1", "Ada, or Ardor"). So the
 * segment is the name itself, percent-encoded, rather than a slug with the
 * spacing rules baked in — a slug could not be reversed into the name the
 * reader typed, and two names would collapse into one URL.
 *
 * Trimming and collapsing runs of whitespace keeps "The  Expanse" and
 * " The Expanse" pointing at the same page, which is how the API matches them.
 */
export const seriesSlug = (name: string): string =>
    encodeURIComponent(name.trim().replace(/\s+/g, ' '));

/** The route that shows every Book in a series. */
export const seriesPath = (name: string): string => `/series/${seriesSlug(name)}`;
