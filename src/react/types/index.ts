export interface Book {
    id: number;
    title: string;
    author?: string;
    authors?: string[];
    isbn13?: string;
    publication_year?: number;
    thumbnail_url?: string;
    cover_url?: string;
    publisher?: string;
    description?: string;
    series?: string;
    bisac_category?: string;
    latest_status?: string;
    is_owned?: boolean;
    in_reading_list?: boolean;
    reading_records?: ReadingRecord[];
    is_planned?: boolean;
}

export interface ReadingRecord {
    id: number;
    book_id: number;
    book_title?: string;
    status: string;
    rating?: number;
    start_date?: string;
    end_date?: string;
    notes?: string;
    created_at?: string;
}

export interface ReadingListItem {
    book_id: number;
    title: string;
    author: string;
    thumbnail_url?: string;
    sort_order?: number;
}

export interface Stats {
    total_books: number;
    total_authors: number;
    total_records: number;
    avg_rating: number;
    status_counts: Record<string, number>;
    rating_distribution: [number, number][];
    top_authors: { name: string; count: number }[];
    top_publishers: { name: string; count: number }[];
    category_distribution: { label: string; count: number }[];
    max_category_count: number;
    yearly_counts: [string, number][];
    max_year_count: number;
    monthly_counts: { index: number; name: string; count: number }[];
    max_month_count: number;
}

export interface HistoryFilters {
    status: string;
    rating: number;
    year: string;
    sort: string;
}

export interface BooksFilters {
    status: string;
    year: string;
    month: string;
    rating: string;
    category: string;
}

export interface Job {
    id: string;
    status: 'pending' | 'started' | 'completed' | 'failed';
    progress?: number;
    message?: string;
    result?: string;
    error?: string;
}

export interface AuthorPage {
    author_name: string;
    read_books: Book[];
    reading_list_books: Book[];
    unread_books: Book[];
}

export interface PublisherPage {
    publisher_name: string;
    books: Book[];
}

export interface User {
    id: string;
    name: string;
    email?: string;
}

export type Theme = 'light' | 'dark' | 'system';