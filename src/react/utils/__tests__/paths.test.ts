import { describe, expect, it } from 'vitest';
import { authorPath, categoryPath, publisherPath, slug } from '../paths';

describe('path helpers', () => {
    it('drops the dots in initials, as the author page does', () => {
        expect(slug('Ursula K. Le Guin')).toBe('ursula-k-le-guin');
        expect(authorPath('Ursula K. Le Guin')).toBe('/author/ursula-k-le-guin');
    });

    it('keeps non-ASCII letters and encodes the segment', () => {
        expect(authorPath('Gabriel García Márquez')).toBe(
            `/author/${encodeURIComponent('gabriel-garcía-márquez')}`
        );
    });

    it('survives the punctuation a publisher name carries', () => {
        expect(publisherPath('harper-&-row')).toBe('/publisher/harper-%26-row');
    });

    it('builds a category filter that keeps ampersands and slashes', () => {
        expect(categoryPath('Business & Economics')).toBe(
            '/books?category=Business%20%26%20Economics'
        );
        expect(categoryPath('Science / Nature')).toBe('/books?category=Science%20%2F%20Nature');
    });
});
