"""Domain models for Book Lamp."""

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class Book:
    """Represents a book entity in the catalogue."""

    id: Optional[int] = None
    isbn13: str = ""
    title: str = ""
    author: str = ""
    authors: List[str] = field(default_factory=list)
    publication_year: Optional[int] = None
    thumbnail_url: Optional[str] = None
    cover_url: Optional[str] = None
    publisher: Optional[str] = None
    description: Optional[str] = None
    series: Optional[str] = None
    bisac_category: Optional[str] = None
    bisac_main_category: Optional[str] = None
    bisac_sub_category: Optional[str] = None
    language: Optional[str] = None
    page_count: Optional[int] = None
    physical_format: Optional[str] = None
    edition: Optional[str] = None
    created_at: Optional[datetime] = None
    latest_status: Optional[str] = None
    is_owned: bool = False
    in_reading_list: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert dataclass to dictionary for JSON serialisation."""
        data = asdict(self)
        if self.created_at:
            data["created_at"] = self.created_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Book":
        """Construct a Book instance from a dictionary or database row."""
        authors = data.get("authors") or []
        if isinstance(authors, str):
            authors = [a.strip() for a in authors.split(",") if a.strip()]
        elif not isinstance(authors, list):
            authors = []
        author = data.get("author") or (authors[0] if authors else "")
        return cls(
            id=data.get("id"),
            isbn13=str(data.get("isbn13") or ""),
            title=str(data.get("title") or ""),
            author=author,
            authors=authors,
            publication_year=data.get("publication_year"),
            thumbnail_url=data.get("thumbnail_url"),
            cover_url=data.get("cover_url"),
            publisher=data.get("publisher"),
            description=data.get("description"),
            series=data.get("series"),
            bisac_category=data.get("bisac_category"),
            bisac_main_category=data.get("bisac_main_category"),
            bisac_sub_category=data.get("bisac_sub_category"),
            language=data.get("language"),
            page_count=data.get("page_count"),
            physical_format=data.get("physical_format"),
            edition=data.get("edition"),
            latest_status=data.get("latest_status"),
            is_owned=bool(data.get("is_owned", False)),
            in_reading_list=bool(data.get("in_reading_list", False)),
        )


@dataclass
class ReadingRecord:
    """Represents a reading log entry."""

    id: Optional[int] = None
    user_id: Optional[int] = None
    book_id: int = 0
    status: str = "Plan to Read"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    rating: int = 0
    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert dataclass to dictionary for JSON serialisation."""
        data = asdict(self)
        if self.created_at:
            data["created_at"] = self.created_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReadingRecord":
        return cls(
            id=data.get("id"),
            user_id=data.get("user_id"),
            book_id=data.get("book_id", 0),
            status=str(data.get("status") or "Plan to Read"),
            start_date=str(data.get("start_date")) if data.get("start_date") else None,
            end_date=str(data.get("end_date")) if data.get("end_date") else None,
            rating=int(data.get("rating") or 0),
        )


@dataclass
class ReadingListItem:
    """Represents an item in the user's reading list queue."""

    user_id: int
    book_id: int
    position: int = 0
    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if self.created_at:
            data["created_at"] = self.created_at.isoformat()
        return data


@dataclass
class JobInfo:
    """Represents a background job and its execution state."""

    id: str
    user_id: Optional[int] = None
    function_name: str = ""
    status: str = "pending"
    progress: int = 0
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Recommendation:
    """Represents an AI-generated book recommendation."""

    id: Optional[int] = None
    user_id: Optional[int] = None
    title: str = ""
    author: str = ""
    isbn13: Optional[str] = None
    reason: str = ""
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
