"""Navigation contract for the static triple-link helper."""

import json
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pytest

from doc_lineage.render import resolve_triple_link

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/render/tracked_variable.json"


class Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []
        self.tags: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        self.tags.append((tag, attributes))
        if tag == "a":
            href = attributes.get("href")
            assert href is not None
            self.hrefs.append(href)


@pytest.fixture
def variable() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def hrefs(variable: dict[str, Any]) -> list[str]:
    parser = Links()
    parser.feed(resolve_triple_link(variable))
    return parser.hrefs


def test_emits_three_hrefs(variable: dict[str, Any]) -> None:
    before = json.dumps(variable, sort_keys=True)
    assert hrefs(variable) == [
        "file:///synthetic/Manager%20Library/blobs/notice.pdf#page=42",
        "file:///synthetic/Manager%20Library/blobs/notice.pdf",
        "https://backstop.example/documents/notice?view=full&version=1",
    ]
    assert json.dumps(variable, sort_keys=True) == before


@pytest.mark.parametrize(
    ("root", "expected"),
    [
        ("mirror/Manager Library", "mirror/Manager%20Library/blobs/notice.pdf"),
        (
            "file:///synthetic/Manager%20Library",
            "file:///synthetic/Manager%20Library/blobs/notice.pdf",
        ),
        (r"C:\Manager Library", "file:///C:/Manager%20Library/blobs/notice.pdf"),
        (
            r"\\server\share\Manager Library",
            "file://server/share/Manager%20Library/blobs/notice.pdf",
        ),
    ],
)
def test_portable_mirror_roots(variable: dict[str, Any], root: str, expected: str) -> None:
    variable["provenance"]["mirror"]["mirror_root"] = root
    assert hrefs(variable)[:2] == [expected + "#page=42", expected]


def test_sharepoint_backlink(variable: dict[str, Any]) -> None:
    variable["provenance"]["source_system"] = {
        "system": "sharepoint",
        "web_url": "https://tenant.example/sites/library/notice.pdf",
    }
    assert hrefs(variable)[2] == "https://tenant.example/sites/library/notice.pdf"


@pytest.mark.parametrize("missing", [True, False])
def test_local_only_document_does_not_invent_source_url(
    variable: dict[str, Any], missing: bool
) -> None:
    if missing:
        variable["provenance"].pop("source_system")
    else:
        variable["provenance"]["source_system"] = None
    assert len(hrefs(variable)) == 2
    assert "Source system unavailable" in resolve_triple_link(variable)


@pytest.mark.parametrize("field", ["mirror_root", "blob_path", "page_anchor"])
def test_requires_navigation_fields(variable: dict[str, Any], field: str) -> None:
    del variable["provenance"]["mirror"][field]
    with pytest.raises(ValueError, match=field):
        resolve_triple_link(variable)


@pytest.mark.parametrize(
    "path", ["../secret.pdf", "/secret.pdf", "C:/secret.pdf", r"a\b.pdf", "a//b.pdf", "a/./b.pdf"]
)
def test_rejects_unsafe_blob_paths(variable: dict[str, Any], path: str) -> None:
    variable["provenance"]["mirror"]["blob_path"] = path
    with pytest.raises(ValueError, match="blob_path"):
        resolve_triple_link(variable)


@pytest.mark.parametrize(
    "root",
    [
        "javascript:alert(1)",
        "https://host/mirror",
        "../mirror",
        "file:///a/../b",
        "file:///tmp#fragment",
        "file://host/tmp",
        r"C:relative",
    ],
)
def test_rejects_invalid_roots(variable: dict[str, Any], root: str) -> None:
    variable["provenance"]["mirror"]["mirror_root"] = root
    with pytest.raises(ValueError, match="mirror_root"):
        resolve_triple_link(variable)


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "data:text/html,test",
        "//host/path",
        "https:///path",
        "https://user:pass@host/path",
        "https://host/\npath",
        "https://host/with space",
        "file:///tmp/doc.pdf",
    ],
)
def test_rejects_unsafe_source_urls(variable: dict[str, Any], url: str) -> None:
    variable["provenance"]["source_system"]["url"] = url
    with pytest.raises(ValueError):
        resolve_triple_link(variable)


def test_escapes_html_and_encodes_path_and_anchor(variable: dict[str, Any]) -> None:
    variable["provenance"]["mirror"]["blob_path"] = 'blobs/quote"<&>#%.pdf'
    variable["provenance"]["mirror"]["page_anchor"] = '#section="<script>"'
    variable["provenance"]["source_system"]["url"] = 'https://host/doc?x="<script>"&y=1'
    parser = Links()
    parser.feed(resolve_triple_link(variable))
    assert len(parser.hrefs) == 3
    assert parser.hrefs[0].endswith("quote%22%3C%26%3E%23%25.pdf#section=%22%3Cscript%3E%22")
    assert {tag for tag, _ in parser.tags} == {"span", "a"}
    assert all(set(attrs) <= {"class", "href"} for _, attrs in parser.tags)


@pytest.mark.parametrize("anchor", ["", "#", "page=42", "#\npage=42"])
def test_rejects_missing_or_invalid_fragment(variable: dict[str, Any], anchor: str) -> None:
    variable["provenance"]["mirror"]["page_anchor"] = anchor
    with pytest.raises(ValueError, match="page_anchor"):
        resolve_triple_link(variable)
