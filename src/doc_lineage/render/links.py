"""Render document-page, local-mirror, and best-effort source-system links.

Canonical ``source_id`` values are identities, not browser URLs. The primary
document link therefore uses the mirror blob plus its explicit page/tool anchor.
Paths are converted lexically, without reading files or resolving against the
rendering machine's current directory (which may differ from the target PC).
"""

from collections.abc import Mapping
from html import escape
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any
from urllib.parse import quote, unquote, urlsplit


def _object(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError(f"{field} must not contain control characters")
    return value


def _relative_path(value: str, field: str) -> str:
    if (
        value.startswith("/")
        or "\\" in value
        or ":" in value
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise ValueError(f"{field} must be a relative POSIX path without traversal")
    return value


def _mirror_url(root: str, blob: str) -> str:
    _relative_path(blob, "provenance.mirror.blob_path")
    windows = PureWindowsPath(root)
    if windows.is_absolute():
        if ".." in windows.parts:
            raise ValueError("mirror_root must not contain traversal")
        return (windows / PurePosixPath(blob)).as_uri()
    if root.startswith("file:"):
        parsed = urlsplit(root)
        if parsed.netloc not in {"", "localhost"} or not parsed.path.startswith("/"):
            raise ValueError("mirror_root file URI must be local and absolute")
        if parsed.query or parsed.fragment:
            raise ValueError("mirror_root file URI must not contain a query or fragment")
        root = _text(unquote(parsed.path), "mirror_root")
    elif urlsplit(root).scheme:
        raise ValueError("mirror_root must be a local path or file URI")
    if "\\" in root or ".." in PurePosixPath(root).parts:
        raise ValueError("mirror_root must not contain backslashes or traversal")
    if root.startswith("/"):
        return (PurePosixPath(root) / blob).as_uri()
    _relative_path(root.rstrip("/"), "mirror_root")
    return quote(f"{root.rstrip('/')}/{blob}", safe="/")


def _source_url(value: object) -> str:
    url = _text(value, "provenance.source_system.url")
    parsed = urlsplit(url)
    if (
        url != url.strip()
        or parsed.scheme not in {"https", "http"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or "\\" in url
        or any(char.isspace() for char in url)
    ):
        raise ValueError("source-system URL must be an absolute HTTP(S) URL without credentials")
    return url


def _link(kind: str, label: str, url: str) -> str:
    return f'<a class="provenance-{kind}" href="{escape(url, quote=True)}">{escape(label)}</a>'


def resolve_triple_link(tracked_variable: Mapping[str, Any]) -> str:
    """Return safe static HTML from a tracked variable's provenance anchors.

    ``document.source_id`` identifies the source. ``mirror_root``, ``blob_path``
    and ``page_anchor`` (including its leading ``#``) are required for page and
    mirror navigation. An absent/null ``source_system`` produces a visible
    unavailable label instead of inventing a third URL. When present it accepts
    ``url`` (Backstop) or ``web_url`` (SharePoint). Invalid input raises ValueError.
    This helper validates navigation fields, not the entire tracked-variable schema.
    """
    variable = _object(tracked_variable, "tracked_variable")
    provenance = _object(variable.get("provenance"), "provenance")
    document = _object(provenance.get("document"), "provenance.document")
    _text(document.get("source_id"), "provenance.document.source_id")
    mirror = _object(provenance.get("mirror"), "provenance.mirror")
    root = _text(mirror.get("mirror_root"), "provenance.mirror.mirror_root")
    blob = _text(mirror.get("blob_path"), "provenance.mirror.blob_path")
    anchor = _text(mirror.get("page_anchor"), "provenance.mirror.page_anchor")
    if not anchor.startswith("#") or not anchor[1:].strip():
        raise ValueError("page_anchor must be a non-empty fragment beginning with #")
    mirror_url = _mirror_url(root, blob)
    page_url = mirror_url + "#" + quote(anchor[1:], safe="=&-._~")
    links = [
        _link("document", "Document page", page_url),
        _link("mirror", "Local mirror", mirror_url),
    ]
    source = provenance.get("source_system")
    if source is None:
        links.append('<span class="provenance-source-unavailable">Source system unavailable</span>')
    else:
        system = _object(source, "provenance.source_system")
        links.append(
            _link("source", "Source system", _source_url(system.get("url", system.get("web_url"))))
        )
    return '<span class="provenance-links">' + " | ".join(links) + "</span>"
