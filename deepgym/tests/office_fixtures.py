"""Hand-built .xlsx and .docx fixtures for the office reader tests.

Stdlib only, like the readers themselves: these builders write just the parts
`_checks.py` reads, so no office library is needed to exercise it.
"""

import re
import zipfile
from pathlib import Path

_CELL = re.compile(r'([A-Z]+)(\d+)')

_XLSX_NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
_REL_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
_PKG_REL_NS = 'http://schemas.openxmlformats.org/package/2006/relationships'
_W_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'


class Inline(str):
    """A string cell stored inline (t="inlineStr") instead of in sharedStrings."""


def make_xlsx(path: Path, sheets: list[tuple[str, dict[str, object], list[str]]]) -> Path:
    """Write a minimal workbook: one entry per sheet, (name, cells, merged ranges).

    A cell value may be a number, a bool, a str (shared string) or an Inline (an
    inline string); a cell left out is empty. Cells are 1-based references like 'C7'.
    """
    shared: dict[str, int] = {}
    parts = []
    for index, (name, cells, merges) in enumerate(sheets, start=1):
        parts.append((name, _sheet_xml(cells, merges, shared), index))
    members = {
        'xl/workbook.xml': _workbook_xml([name for name, _, _ in parts]),
        'xl/_rels/workbook.xml.rels': _rels_xml(len(parts)),
    }
    members.update({f'xl/worksheets/sheet{index}.xml': xml for _, xml, index in parts})
    if shared:
        members['xl/sharedStrings.xml'] = _shared_xml(shared)
    with zipfile.ZipFile(path, 'w') as archive:
        for member, xml in members.items():
            archive.writestr(member, xml)
    return path


def _cell_xml(ref: str, value: object, shared: dict[str, int]) -> str:
    if isinstance(value, bool):
        return f'<c r="{ref}" t="b"><v>{int(value)}</v></c>'
    if isinstance(value, (int, float)):
        return f'<c r="{ref}"><v>{value!r}</v></c>'
    if isinstance(value, Inline):
        return f'<c r="{ref}" t="inlineStr"><is><t>{value}</t></is></c>'
    if isinstance(value, str):
        return f'<c r="{ref}" t="s"><v>{shared.setdefault(value, len(shared))}</v></c>'
    raise TypeError(f'cannot write {value!r}')


def _sheet_xml(cells: dict[str, object], merges: list[str], shared: dict[str, int]) -> str:
    rows: dict[int, list[str]] = {}
    for ref, value in cells.items():
        rows.setdefault(int(_CELL.fullmatch(ref).group(2)), []).append(
            _cell_xml(ref, value, shared)
        )
    body = ''.join(
        f'<row r="{number}">{"".join(row)}</row>' for number, row in sorted(rows.items())
    )
    merge = (
        f'<mergeCells count="{len(merges)}">'
        + ''.join(f'<mergeCell ref="{ref}"/>' for ref in merges)
        + '</mergeCells>'
        if merges
        else ''
    )
    return f'<worksheet xmlns="{_XLSX_NS}"><sheetData>{body}</sheetData>{merge}</worksheet>'


def _shared_xml(shared: dict[str, int]) -> str:
    items = sorted(shared, key=shared.get)
    body = ''.join(f'<si><t>{text}</t></si>' for text in items)
    count = len(items)
    return f'<sst xmlns="{_XLSX_NS}" count="{count}" uniqueCount="{count}">{body}</sst>'


def _workbook_xml(names: list[str]) -> str:
    sheets = ''.join(
        f'<sheet name="{name}" sheetId="{index}" r:id="rId{index}"/>'
        for index, name in enumerate(names, start=1)
    )
    return f'<workbook xmlns="{_XLSX_NS}" xmlns:r="{_REL_NS}"><sheets>{sheets}</sheets></workbook>'


def _rels_xml(count: int) -> str:
    rels = ''.join(
        f'<Relationship Id="rId{index}" Type="worksheet" Target="worksheets/sheet{index}.xml"/>'
        for index in range(1, count + 1)
    )
    return f'<Relationships xmlns="{_PKG_REL_NS}">{rels}</Relationships>'


def make_docx(path: Path, paragraphs: list[str]) -> Path:
    """Write a minimal document; a paragraph starting with '<w:p' is taken as raw XML."""
    body = ''.join(
        para if para.startswith('<w:p') else f'<w:p><w:r><w:t>{para}</w:t></w:r></w:p>'
        for para in paragraphs
    )
    document = f'<w:document xmlns:w="{_W_NS}"><w:body>{body}</w:body></w:document>'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('word/document.xml', document)
    return path
