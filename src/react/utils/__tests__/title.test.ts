import { describe, expect, it } from 'vitest';
import { splitSubtitle } from '../title';

describe('splitSubtitle', () => {
    it('takes a subtitle off after a colon', () => {
        expect(splitSubtitle('A History of England in 100 Places: From Stonehenge to the Gherkin')).toEqual({
            title: 'A History of England in 100 Places',
            subtitle: 'From Stonehenge to the Gherkin',
        });
    });

    it('takes a subtitle off after a spaced dash', () => {
        expect(splitSubtitle('The Spy in the Archive — A Novel')).toEqual({
            title: 'The Spy in the Archive',
            subtitle: 'A Novel',
        });
    });

    it('collapses whitespace before splitting', () => {
        expect(splitSubtitle('  The  Last  King :   A Life ')).toEqual({
            title: 'The Last King',
            subtitle: 'A Life',
        });
    });

    it('leaves a title with no separator whole', () => {
        expect(splitSubtitle('Piranesi')).toEqual({ title: 'Piranesi' });
    });

    it.each(['Re: Zero', '10:04', 'Spider-Man'])(
        'refuses to split %s, which carries its separator as part of the title',
        (title) => {
            expect(splitSubtitle(title)).toEqual({ title });
        }
    );

    it('refuses a separator with nothing after it', () => {
        expect(splitSubtitle('Colon:')).toEqual({ title: 'Colon:' });
    });
});
