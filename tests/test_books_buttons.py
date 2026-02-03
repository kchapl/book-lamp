import re


def _opening_tag_for_text(
    html: str, tag_text: str, tag_name: str = "button"
) -> str | None:
    # Find opening tag text for an element containing given inner text
    pattern = rf"(<{tag_name}[^>]*>)(?:\s*{re.escape(tag_text)})"
    m = re.search(pattern, html, flags=re.IGNORECASE | re.DOTALL)
    return m.group(1) if m else None


def test_books_page_buttons_have_no_inline_styles(client):
    resp = client.get("/books")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")

    fetch_tag = _opening_tag_for_text(html, "Fetch missing data", tag_name="button")
    import_tag = _opening_tag_for_text(html, "Import from Libib", tag_name="button")
    search_tag = _opening_tag_for_text(html, "🔍 Search", tag_name="button")

    # The page currently uses inline styles for these buttons; assert they are absent
    assert fetch_tag is not None, "Couldn't find 'Fetch missing data' button"
    assert import_tag is not None, "Couldn't find 'Import from Libib' button"
    assert search_tag is not None, "Couldn't find search button"

    assert (
        "style=" not in fetch_tag
    ), "'Fetch missing data' button should not use inline styles"
    assert (
        "style=" not in import_tag
    ), "'Import from Libib' button should not use inline styles"
    assert "style=" not in search_tag, "Search button should not use inline styles"
