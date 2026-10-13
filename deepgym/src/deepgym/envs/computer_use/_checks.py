"""Shared helpers for computer-use verifiers.

Besides the app-state helpers, this module carries the readers and rule engine
for office files: `read_sheets` and `read_docx_text` read .xlsx and .docx with
the standard library only, and `office_rule_checks` evaluates the compare_table
rules of an imported OSWorld task against the workbook the agent saved.
"""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


def load_state(path: str = 'state.json') -> dict:
    """Return the app state the page last saved, or {} if it never saved."""
    try:
        return json.loads(Path(path).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def report(progress: dict[str, bool], guards: dict[str, bool]) -> None:
    """Print verifier protocol JSON.

    Score is the fraction of progress checks passed, but only if every guard
    holds (work was saved, nothing else was broken). Otherwise it is 0, so
    neither doing nothing nor saving untouched state earns reward.
    """
    guards_ok = all(guards.values())
    done = sum(progress.values())
    score = done / len(progress) if guards_ok else 0.0
    failed = [name for name, ok in guards.items() if not ok]
    print(
        json.dumps(
            {
                'schema_version': '1.0',
                'score': score,
                'passed': guards_ok and done == len(progress),
                'details': f'{done}/{len(progress)} changes made'
                + (f'; guards failed: {", ".join(failed)}' if failed else ''),
                'cases': [
                    {'id': name, 'passed': ok, 'score': float(ok)}
                    for name, ok in {**guards, **progress}.items()
                ],
            }
        )
    )


# Office files {{{ #
#
# The readers follow what OSWorld's own evaluators see through pandas, openpyxl
# and python-docx: cached formula values (not formula text), empty cells as
# None, numbers int when integral (dates stay raw serials, so both sides of a
# comparison encode the same way), and docx text as python-docx reads it.
# office_rule_checks() evaluates compare_table's rules with the same semantics,
# including DataFrame.round's rounding (numpy's, not Python's, half-to-even).

_XLSX_NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
_REL_NS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
_PKG_REL_NS = '{http://schemas.openxmlformats.org/package/2006/relationships}'
_W_NS = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

_COORD_RE = re.compile(r'([A-Z]+)(\d+)')


def _coord_to_cell(coord: str) -> tuple[int, int]:
    """'C7' -> (row 7, column 3), both 1-based."""
    match = _COORD_RE.fullmatch(coord)
    if not match:
        raise ValueError(f'not a cell coordinate: {coord!r}')
    col = 0
    for ch in match.group(1):
        col = col * 26 + (ord(ch) - ord('A') + 1)
    return int(match.group(2)), col


def _number(text: str) -> int | float | None:
    """A numeric cell's value: float when fractional, int when integral (pandas-like)."""
    try:
        value = float(text)
    except ValueError:
        return None
    if value.is_integer() and abs(value) < 1e15:
        return int(value)
    return value


def _cell_value(cell: ET.Element, shared: list[str]) -> object:
    """The value of one <c> element, as pandas reads it (dates stay serials)."""
    kind = cell.get('t')
    if kind == 'inlineStr':
        node = cell.find(f'{_XLSX_NS}is')
        if node is None:
            return None
        return ''.join(t.text or '' for t in node.iter(f'{_XLSX_NS}t'))
    value = cell.find(f'{_XLSX_NS}v')
    if value is None or value.text is None:
        return None
    if kind == 's':
        try:
            return shared[int(value.text)]
        except (ValueError, IndexError):
            return None
    if kind == 'str':
        return value.text
    if kind == 'b':
        return value.text == '1'
    if kind == 'e':
        return value.text
    return _number(value.text)


def _merge_ranges(root: ET.Element) -> list[str]:
    merges = root.find(f'{_XLSX_NS}mergeCells')
    if merges is None:
        return []
    return [cell.get('ref', '') for cell in merges.findall(f'{_XLSX_NS}mergeCell')]


def _trim(grid: list[list[object]]) -> list[list[object]]:
    """Drop trailing rows and columns whose every cell is None (pandas reads no further)."""
    while grid and all(value is None for value in grid[-1]):
        grid.pop()
    while grid and all((row[-1] if row else None) is None for row in grid):
        for row in grid:
            row.pop()
    return grid


def _sheet_grid(root: ET.Element, shared: list[str]) -> list[list[object]]:
    """Rows of cell values over the sheet's used range; missing cells are None."""
    cells: dict[tuple[int, int], object] = {}
    max_row = 0
    max_col = 0
    data = root.find(f'{_XLSX_NS}sheetData')
    if data is None:
        return []
    for row in data.findall(f'{_XLSX_NS}row'):
        for cell in row.findall(f'{_XLSX_NS}c'):
            ref = cell.get('r')
            if not ref:
                continue
            r, c = _coord_to_cell(ref)
            cells[(r, c)] = _cell_value(cell, shared)
            max_row = max(max_row, r)
            max_col = max(max_col, c)
    grid: list[list[object]] = []
    for r in range(1, max_row + 1):
        grid.append([cells.get((r, c)) for c in range(1, max_col + 1)])
    return _trim(grid)


def _sheet_parts(archive: zipfile.ZipFile) -> list[tuple[str, str]]:
    """(sheet name, part name) for every sheet, in workbook order."""
    workbook = ET.fromstring(archive.read('xl/workbook.xml'))
    rels = ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
    targets = {
        rel.get('Id'): rel.get('Target') for rel in rels.findall(f'{_PKG_REL_NS}Relationship')
    }
    sheets = []
    node = workbook.find(f'{_XLSX_NS}sheets')
    for sheet in [] if node is None else node:
        target = targets.get(sheet.get(f'{_REL_NS}id'), '')
        if target.startswith('/'):
            target = target[1:]
        elif not target.startswith('xl/'):
            target = f'xl/{target}'
        sheets.append((sheet.get('name', ''), target))
    return sheets


def read_sheets(path: str) -> list[tuple[str, list[list[object]], list[str]]]:
    """Every sheet of *path*: (name, values grid, merged ranges in A1 notation).

    Args:
        path: Path to an .xlsx workbook.

    Returns:
        Sheets in workbook order. A grid's cells are strings, numbers (int when
        integral), booleans, error text, or None for an empty cell.

    Raises:
        ValueError: If the file is missing or not a readable workbook.
    """
    try:
        with zipfile.ZipFile(path) as archive:
            shared_node = None
            if 'xl/sharedStrings.xml' in archive.namelist():
                shared_node = ET.fromstring(archive.read('xl/sharedStrings.xml'))
            shared = [
                ''.join(t.text or '' for t in si.iter(f'{_XLSX_NS}t'))
                for si in (shared_node if shared_node is not None else [])
            ]
            sheets = []
            for name, part in _sheet_parts(archive):
                root = ET.fromstring(archive.read(part))
                sheets.append((name, _sheet_grid(root, shared), _merge_ranges(root)))
            return sheets
    except (OSError, zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
        raise ValueError(f'{path} is not a readable workbook: {exc}') from exc


def _run_text(run: ET.Element) -> str:
    """python-docx's `Run.text`: direct t/tab/br/cr/noBreakHyphen/ptab children."""
    parts = []
    for node in run:
        tag = node.tag
        if tag == f'{_W_NS}t':
            parts.append(node.text or '')
        elif tag == f'{_W_NS}tab':
            parts.append('\t')
        elif tag == f'{_W_NS}cr':
            parts.append('\n')
        elif tag == f'{_W_NS}br':
            parts.append('\n' if node.get(f'{_W_NS}type', 'textWrapping') == 'textWrapping' else '')
        elif tag == f'{_W_NS}noBreakHyphen':
            parts.append('-')
        elif tag == f'{_W_NS}ptab':
            parts.append('\t')
    return ''.join(parts)


def read_docx_text(path: str) -> str:
    """The document's text as compare_docx_files reads it: python-docx's
    `paragraph.text` for every body paragraph (direct runs and hyperlink runs), in
    order, whitespace collapsed to single spaces, stripped.

    Args:
        path: Path to a .docx document.

    Returns:
        The normalized text.

    Raises:
        ValueError: If the file is missing or not a readable document.
    """
    try:
        with zipfile.ZipFile(path) as archive:
            root = ET.fromstring(archive.read('word/document.xml'))
    except (OSError, zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
        raise ValueError(f'{path} is not a readable document: {exc}') from exc
    body = root.find(f'{_W_NS}body')
    paragraphs = []
    if body is not None:
        for para in body:
            if para.tag != f'{_W_NS}p':
                continue
            text_parts = []
            for child in para:
                if child.tag == f'{_W_NS}r':
                    text_parts.append(_run_text(child))
                elif child.tag == f'{_W_NS}hyperlink':
                    for run in child:
                        if run.tag == f'{_W_NS}r':
                            text_parts.append(_run_text(run))
            paragraphs.append(''.join(text_parts))
    return re.sub(r'\s+', ' ', '\n'.join(paragraphs)).strip()


def _np_round(value: float, precision: int) -> float:
    """Round like pandas' DataFrame.round, i.e. like numpy: round the value scaled by
    10**precision to nearest-even, then scale back.

    Python's `round(value, precision)` can disagree at exact halves, e.g.
    round(-0.00005, 4) == -0.0001 while numpy rounds it to -0.0.
    """
    scale = 10**precision
    return round(value * scale) / scale


def _is_number(value: object) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float))


def _same_value(a: object, b: object) -> bool:
    """Elementwise equality as pandas uses it: None only equals None; numbers compare
    across int/float (and bool, as Python's `==` does); other types must match."""
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return float(a) == float(b)
    if isinstance(a, str) and isinstance(b, str):
        return a == b
    return False


def _round_grid(grid: list[list[object]], precision: int) -> list[list[object]]:
    """DataFrame.round(precision)'s effect on a grid: round all-numeric columns' data.

    Row 0 is the header and becomes the frame's column labels, so it never takes
    part in a column's dtype and is never rounded. pandas leaves object columns (a
    column becomes object as soon as one data cell is not a plain number), bools
    and datetimes untouched, so a stray text cell turns off rounding for the whole
    column on that side.
    """
    width = max((len(row) for row in grid), default=0)
    numeric = []
    for column in range(width):
        values = [row[column] for row in grid[1:] if column < len(row) and row[column] is not None]
        numeric.append(bool(values) and all(_is_number(value) for value in values))
    if not any(numeric):
        return grid
    rounded = [list(grid[0])] if grid else []
    for row in grid[1:]:
        rounded.append(
            [
                _np_round(value, precision)
                if column < len(row) and numeric[column] and _is_number(value)
                else value
                for column, value in enumerate(row)
            ]
        )
    return rounded


def sheets_match(
    agent: list[list[object]], expected: list[list[object]], precision: int = 4
) -> bool:
    """Whether two grids are the same sheet, as compare_table's sheet_data sees it.

    Mirrors `pd.read_excel(a).round(precision).equals(pd.read_excel(b).round(precision))`:
    each side is rounded by its own column dtypes first, then shapes and every value
    must match.
    """
    if len(agent) != len(expected):
        return False
    for row_a, row_e in zip(agent, expected):
        if len(row_a) != len(row_e):
            return False
    agent = _round_grid(agent, precision)
    expected = _round_grid(expected, precision)
    for row_a, row_e in zip(agent, expected):
        for value_a, value_e in zip(row_a, row_e):
            if not _same_value(value_a, value_e):
                return False
    return True


def is_merged(merges: list[str], coordinate: str) -> bool:
    """True when *coordinate* sits in a merged range but is not its top-left anchor.

    This is what openpyxl reports for a MergedCell, which compare_table's check_cell
    'merge' prop matches against.
    """
    r, c = _coord_to_cell(coordinate)
    for ref in merges:
        if ':' not in ref:
            continue
        start, end = ref.split(':', 1)
        r1, c1 = _coord_to_cell(start)
        r2, c2 = _coord_to_cell(end)
        if r1 <= r <= r2 and c1 <= c <= c2 and not (r == r1 and c == c1):
            return True
    return False


def cell_at(sheet_rows: list[list[object]], coordinate: str) -> object:
    """The value at *coordinate* ('E3'), or None outside the sheet."""
    r, c = _coord_to_cell(coordinate)
    if 1 <= r <= len(sheet_rows) and 1 <= c <= len(sheet_rows[r - 1]):
        return sheet_rows[r - 1][c - 1]
    return None


def build_sheet(rows: list[list[object]]) -> list[list[object]]:
    """Trim a grid built from a literal the way read_sheets trims a file's."""
    return _trim([list(row) for row in rows])


def _parse_sheet_idx(idx: object, names_r: list[str], names_e: list[str]) -> tuple[str, str]:
    """OSWorld's `_parse_sheet_idx`: int/RI/RN select the *result* book (the file the
    agent saved), EI/EN the *expected* one. Returns (side, sheet name); an index that
    cannot be resolved yields name '' which then fails to load, as in OSWorld."""
    if isinstance(idx, int):
        if not names_r or idx >= len(names_r):
            return ('r', '')
        return ('r', names_r[idx])
    if isinstance(idx, str) and idx.startswith('RI'):
        try:
            return ('r', names_r[int(idx[2:])])
        except Exception:
            return ('r', '')
    if isinstance(idx, str) and idx.startswith('RN'):
        return ('r', idx[2:])
    if isinstance(idx, str) and idx.startswith('EI'):
        try:
            return ('e', names_e[int(idx[2:])])
        except Exception:
            return ('e', '')
    if isinstance(idx, str) and idx.startswith('EN'):
        return ('e', idx[2:])
    raise ValueError(f'unrecognized sheet index: {idx!r}')


def _match_rule(value: object, rule: dict) -> bool:
    """OSWorld's `_match_value_to_rule` for the comparison methods the importer
    copies over. A malformed rule or unknown method fails the rule, never passes it."""
    import operator as op

    method = str(rule.get('method', ''))
    if method in {'eq', 'ne', 'le', 'lt', 'ge', 'gt'}:
        try:
            return bool(getattr(op, method)(value, rule['ref']))
        except (KeyError, TypeError):
            return False
    if method.startswith('approx'):
        try:
            return abs(float(value) - rule['ref']) <= float(method.split(':', 1)[1])
        except (KeyError, TypeError, ValueError):
            return False
    return False


def _rule_verdict(
    rule: dict,
    result: list[tuple[str, list[list[object]], list[str]]] | None,
    expected: list[tuple[str, list[list[object]], list[str]]] | None,
    names_r: list[str],
    names_e: list[str],
) -> bool:
    """One compare_table rule against the agent's workbook (and the reference).

    A rule that cannot be resolved — a missing sheet, index or cell — fails;
    no rule of any shape raises."""
    kind = rule.get('type')
    if kind == 'sheet_name':
        return expected is not None and names_r == names_e
    if kind == 'sheet_data':

        def grid_of(idx: object) -> list[list[object]] | None:
            try:
                side, name = _parse_sheet_idx(idx, names_r, names_e)
            except ValueError:
                return None
            sheets = result if side == 'r' else expected
            match = [sheet for sheet in sheets or [] if sheet[0] == name]
            return match[0][1] if match else None

        grid1 = grid_of(rule.get('sheet_idx0'))
        if grid1 is None:
            return False
        grid2 = grid_of(rule.get('sheet_idx1'))
        if grid2 is None:
            return False
        return sheets_match(grid1, grid2, rule.get('precision', 4))
    if kind == 'check_cell':
        try:
            side, name = _parse_sheet_idx(rule.get('sheet_idx'), names_r, names_e)
        except ValueError:
            return False
        sheets = result if side == 'r' else expected
        match = [sheet for sheet in sheets or [] if sheet[0] == name]
        if not match or not rule.get('props'):
            return False
        _, rows, merges = match[0]
        for prop, rule_value in rule['props'].items():
            try:
                if prop == 'value':
                    value = cell_at(rows, rule['coordinate'])
                elif prop == 'merge':
                    value = is_merged(merges, rule['coordinate'])
                else:
                    return False
            except (KeyError, ValueError):
                return False
            if not _match_rule(value, rule_value):
                return False
        return True
    return False


def office_rule_checks(
    rules: list[dict],
    result: list[tuple[str, list[list[object]], list[str]]] | None,
    expected: list[tuple[str, list[list[object]], list[str]]] | None,
) -> dict[str, bool]:
    """Evaluate an imported task's compare_table rules against the agent's workbook.

    Args:
        rules: The task's rules, in order.
        result: `read_sheets()` of the file the agent saved, or None if it could not
            be read.
        expected: `read_sheets()` of the task's reference workbook, or None when the
            task has no reference file.

    Returns:
        {rule name, e.g. 'rule0_sheet_data': passed}; a rule whose sheets, indices
        or cells cannot be resolved fails. A rule's 'name', when it has one, is
        used as its key.
    """
    names_r = [sheet[0] for sheet in result or []]
    names_e = [sheet[0] for sheet in expected or []]
    checks = {}
    for index, rule in enumerate(rules):
        name = str(rule.get('name') or f'rule{index}_{rule.get("type", "?")}')
        while name in checks:  # two rules must never share one verdict slot
            name += '_'
        checks[name] = _rule_verdict(rule, result, expected, names_r, names_e)
    return checks


# }}} Office files #
