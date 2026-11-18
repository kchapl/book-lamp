/**
 * Split a title the way a Book is presented, not stored.
 *
 * "Title: Subtitle" and "Title — Subtitle" are how providers separate a
 * subtitle. A colon with almost nothing before it ("Re: ...") and a bare
 * hyphen ("Spider-Man") belong to the title, so neither is split. A title
 * that glues a subtitle on with no separator cannot be split safely: cutting
 * there would take "Dune Messiah" for a subtitle of "Dune" and hide a sequel
 * behind its predecessor, so such a title is returned whole.
 *
 * The stored title is never changed: this only says which part is the heading
 * and which reads as supporting text beneath it.
 */
export interface SplitTitle {
    title: string;
    subtitle?: string;
}

const SUBTITLE_SEPARATOR = /\s*:\s*|\s+[\u2013\u2014-]\s+/;

export function splitSubtitle(rawTitle: string): SplitTitle {
    const title = rawTitle.replace(/\s+/g, ' ').trim();
    const separator = SUBTITLE_SEPARATOR.exec(title);
    if (!separator) return { title };

    const main = title.slice(0, separator.index).trim();
    const subtitle = title.slice(separator.index + separator[0].length).trim();
    if (main.length <= 3 || !subtitle) return { title };
    return { title: main, subtitle };
}
