# Static provenance links

`doc_lineage.render.resolve_triple_link(tracked_variable)` returns an escaped
HTML fragment for a `tracked-variable/v1` provenance object. It performs no file
access or network requests and needs no template engine. Pass the result directly
to a static HTML output, or mark this fragment safe at the Jinja insertion point
after calling the helper (do not mark the original provenance data safe).

```python
from doc_lineage.render import resolve_triple_link

html = resolve_triple_link({
    "provenance": {
        "document": {"source_id": "document:synthetic", "locator": {"page": 42}},
        "mirror": {
            "mirror_root": "mirror",
            "blob_path": "blobs/notice.pdf",
            "page_anchor": "#page=42",
        },
        "source_system": {
            "system": "backstop",
            "url": "https://backstop.example/documents/notice",
        },
    },
})
```

The three links are **Document page** (`mirror/blobs/notice.pdf#page=42`),
**Local mirror** (`mirror/blobs/notice.pdf`), and **Source system** (the supplied
HTTP(S) URL). A canonical `source_id` is an identity, not a URL; the mirror and
explicit `page_anchor` make the primary document link navigable. The helper
preserves the supplied page/tool fragment without inferring page numbering from
`locator.page` or inventing a source-system route.

Relative mirror roots resolve relative to the final HTML file. Absolute POSIX,
Windows drive, and UNC paths become file URIs; local `file:///` roots are also
accepted. Paths are encoded without resolving them on the build machine. The
blob path follows `document-mirror/v1`: relative POSIX components with no drive,
backslashes, or traversal. Supply paths that exist on the viewing machine.
Browser policy still controls whether local navigation is permitted.

For SharePoint use `source_system.web_url` (or normalized `url`). The manifest's
chosen `source_refs` entry must already be projected into `source_system` by the
caller; this helper does not choose among multiple source records. Local-only
records may omit `source_system` or set it to null: they produce two links and a
visible **Source system unavailable** label. Present but malformed source data,
unsafe URLs, and missing navigation fields raise `ValueError`.

This validates navigation fields only; use the shared contract validator for
the complete tracked-variable/evidence record. No renderer, manifest loader, or
source-system connector is added here.

Acceptance: `python -m pytest tests/render/test_triple_link_resolver.py -q`.
The named `test_emits_three_hrefs` parses actual generated HTML and checks all
three destinations. Removing `page_anchor` from the checked-in synthetic fixture
must fail that test; restore the fixture afterward.
