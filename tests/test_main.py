"""Package import smoke: the public surface must import and expose the M1 API.

This replaces the Template's ``greet``/``add`` scaffold tests. The scaffold
helpers are gone, so a test that still asserted on them would be asserting the
package had not been built yet.
"""

from __future__ import annotations

import doc_lineage


def test_version_is_a_string() -> None:
    assert isinstance(doc_lineage.__version__, str)
    assert doc_lineage.__version__ == "0.1.0"


def test_public_surface_exposes_the_ingest_api() -> None:
    assert "ingest_document" in doc_lineage.__all__
    assert callable(doc_lineage.ingest_document)
    assert not hasattr(doc_lineage, "greet")
    assert not hasattr(doc_lineage, "add")


def test_console_entry_point_is_importable() -> None:
    from doc_lineage.cli import main

    assert callable(main)
