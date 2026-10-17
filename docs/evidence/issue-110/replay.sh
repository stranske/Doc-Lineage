#!/bin/sh
# Explicit interpreter argument supports an activated/repository-selected venv.
set -eu
runtime=${1:-/opt/anaconda3/bin/python3}
evidence=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
repo=$(CDPATH='' cd -- "$evidence/../../.." && pwd)
run=$(mktemp -d "${TMPDIR:-/tmp}/doc-lineage-110-replay.XXXXXX")
export PYTHONPATH="$repo/src:$repo"
export XDG_CACHE_HOME="$run/cache"
"$runtime" - "$evidence" <<'PY'
import hashlib
import json
from pathlib import Path
import sys

artifacts = Path(sys.argv[1]) / 'artifacts'
record = json.loads((artifacts / 'comparison-record.json').read_text())
for role in ('original', 'modified'):
    assert hashlib.sha256((artifacts / f'{role}.docx').read_bytes()).hexdigest() == record[f'{role}_sha256']
print('Retained original package hashes verified; creating a NEW record with explicit relocated inputs.')
PY
id=$("$runtime" -m doc_lineage.cli create-comparison \
  --original "$evidence/artifacts/original.docx" --modified "$evidence/artifacts/modified.docx" \
  --comparison-store "$run/records")
# Separate process reopens only the persisted ID, using the same explicit store.
"$runtime" -m doc_lineage.cli export-docx --blackline "$id" \
  --comparison-store "$run/records" --output "$run/redline.docx" --author Counsel
"$runtime" - "$run/redline.docx" <<'PY'
from io import BytesIO
from pathlib import Path
import sys
from xml.etree import ElementTree as ET
from zipfile import ZipFile
from tests.export.test_docx_redline_golden import NS, _visible_text

with ZipFile(BytesIO(Path(sys.argv[1]).read_bytes())) as package:
    assert package.testzip() is None
    document = ET.fromstring(package.read('word/document.xml'))
assert document.findall('.//w:ins', NS) and document.findall('.//w:del', NS)
assert _visible_text(document, 'ins') == 'The fee is five dollars.'
assert _visible_text(document, 'del') == 'The fee is ten dollars.'
print('Native DOCX reject/accept reconstruction verified:', sys.argv[1])
PY
