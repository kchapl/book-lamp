/**
 * A signal that a background run wrote collection data a page is showing.
 *
 * The covers run finishes after the reader started it, often while My Books is
 * still open: the report in the job strip says what happened, but the cards keep
 * their old covers until the page refetches. Pages take the revision as a fetch
 * dependency, so the run reaching its end refreshes what it changed.
 */
import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';

interface CollectionRevision {
    revision: number;
    refresh: () => void;
}

// The default is a no-op, so a page or a layout rendered on its own works
// without a provider and simply never hears about a background run.
const CollectionRevisionContext = createContext<CollectionRevision>({
    revision: 0,
    refresh: () => {},
});

export const CollectionRevisionProvider: React.FC<{ children: React.ReactNode }> = ({
    children,
}) => {
    const [revision, setRevision] = useState(0);
    const refresh = useCallback(() => setRevision((value) => value + 1), []);
    const value = useMemo(() => ({ revision, refresh }), [revision, refresh]);

    return (
        <CollectionRevisionContext.Provider value={value}>
            {children}
        </CollectionRevisionContext.Provider>
    );
};

/** The current revision: pass it to `useResource`'s dependencies. */
export function useCollectionRevision(): number {
    return useContext(CollectionRevisionContext).revision;
}

/** Ask the pages showing collection data to refetch it. */
export function useRefreshCollection(): () => void {
    return useContext(CollectionRevisionContext).refresh;
}
