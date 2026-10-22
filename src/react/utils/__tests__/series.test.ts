/**
 * Series links.
 *
 * A series has no id, so its name is its identity in the URL. These pin the two
 * properties the API depends on: punctuation survives the round trip, and
 * spellings that differ only in spacing or case produce the same segment.
 */
import { describe, expect, it } from 'vitest';
import { seriesPath, seriesSlug } from '../series';

describe('seriesSlug', () => {
    it('encodes punctuation a real series name carries', () => {
        expect(seriesSlug('Mistborn: Era 1')).toBe('Mistborn%3A%20Era%201');
        expect(seriesSlug('Ada, or Ardor')).toBe('Ada%2C%20or%20Ardor');
        expect(seriesSlug("The Hitchhiker's Guide")).toBe("The%20Hitchhiker's%20Guide");
        expect(seriesSlug('Dune & Messiah')).toBe('Dune%20%26%20Messiah');
    });

    it('flattens the spacing and trimming the API normalises', () => {
        expect(seriesSlug('  The   Expanse ')).toBe(seriesSlug('The Expanse'));
    });

    it('builds the route the page is mounted on', () => {
        expect(seriesPath('The Expanse')).toBe('/series/The%20Expanse');
    });
});
