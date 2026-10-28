"""The authorship module: names in, names out.

The list is the representation; text is read once at an edge (`parse`) and
written once for the page (`display`). These tests pin the two rules that make
that safe: a list is never re-parsed, and a single comma still means
"Last, First".
"""

from book_lamp.utils.authors import display, matches, parse, slug, sort_key


def test_parse_reads_a_semicolon_list():
    """A semicolon is the unambiguous separator, so it decides the split."""
    assert parse("Neil Gaiman; Terry Pratchett") == ["Neil Gaiman", "Terry Pratchett"]


def test_parse_reads_and_and_ampersand_lists():
    """' and ' and ' & ' join names and cannot appear inside one."""
    assert parse("Neil Gaiman and Terry Pratchett") == ["Neil Gaiman", "Terry Pratchett"]
    assert parse("Neil Gaiman & Terry Pratchett") == ["Neil Gaiman", "Terry Pratchett"]


def test_parse_reads_a_single_comma_as_last_first():
    """One comma is a name's own, not a separator between two."""
    assert parse("Austen, Jane") == ["Austen, Jane"]


def test_parse_reads_two_commas_as_a_list():
    """Two commas cannot be one 'Last, First' name, so it is a bare list."""
    assert parse("Gaiman, Pratchett, Adams") == ["Gaiman", "Pratchett", "Adams"]


def test_parse_ignores_blank_parts():
    """Separators next to each other, or at the end, name nobody."""
    assert parse(" Gaiman ; ; Pratchett ; ") == ["Gaiman", "Pratchett"]
    assert parse("") == []
    assert parse("   ") == []


def test_display_joins_what_a_reader_reads():
    """The display string is a projection, so it uses ordinary prose commas."""
    assert display(["Neil Gaiman", "Terry Pratchett"]) == "Neil Gaiman, Terry Pratchett"
    assert display([" Jane Austen ", ""]) == "Jane Austen"
    assert display([]) == ""


def test_slug_keeps_its_shape():
    """Author links that have been handed out depend on this exact transform."""
    assert slug("Jane Austen") == "jane-austen"
    assert slug("J.R.R. Tolkien") == "jrr-tolkien"
    # Frozen: a comma or a hyphen survives, because it is part of the name.
    assert slug("Austen, Jane") == "austen,-jane"
    assert slug("Saint-Exupéry") == "saint-exupéry"
    assert slug("") == ""


def test_matches_compares_the_page_slug():
    """A page's slug identifies its Author, whatever the URL's case."""
    assert matches("Jane Austen", "jane-austen")
    assert matches("Jane Austen", "JANE-AUSTEN")
    assert not matches("Jane Austen", "neil-gaiman")
    assert not matches("Jane Austen", "")


def test_sort_key_puts_the_surname_first():
    """Sorting by surname works for both orders a name is written in."""
    assert sort_key("Austen, Jane") == ("austen", "jane")
    assert sort_key("Jane Austen") == ("austen", "jane")
    assert sort_key("Homer") == ("homer", "")
    assert sort_key("") == ("", "")
