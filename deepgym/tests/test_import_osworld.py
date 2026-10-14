"""OSWorld importer: the generated envs score the file the task saves, not the screen.

Runs offline: the task configs and the office files here are built by hand, and the
importer's own functions are the ones under test.
"""

import base64
import copy
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from deepgym import ComputerUseEnvironment
from deepgym.registry import load_environment_dir
from tests.office_fixtures import Date, make_docx, make_xlsx

scripts_dir = Path(__file__).resolve().parent.parent / 'scripts'
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

from import_osworld import (  # noqa: E402
    _TASK_API_URL,
    _TASK_URL,
    TASKS,
    Task,
    build_environment,
    build_registry_entry,
    build_setup,
    build_task_md,
    fetch_file,
    fetch_task,
    install_shared,
    load_checks_module,
    parse_task,
)

TASK_ID = '00000000-0000-4000-8000-000000000024'
CALC = 'libreoffice_calc'
WRITER = 'libreoffice_writer'
FILE = 'budget.xlsx'
DOC = 'report.docx'
DESKTOP = '/home/user/Desktop'
TITLE = 'A task title'

_START = {
    'A1': 'Item',
    'B1': 'Cost',
    'A2': 'Rent',
    'B2': 1200,
    'A3': 'Food',
    'B3': 300,
    'A4': 'Total',
}
_GOLD = {**_START, 'B4': 1500}
_MERGED = ['A5:B5']
"""The gold file's merge; is_merged() is openpyxl's MergedCell rule, so B5, not A5."""

_DOC_TEXT = ['Presentation Instruction', 'Describe some customs in China.']
_DOC_GOLD = ['presentation instruction', 'describe some customs in china.']


def _cell(sheet_idx: object, coordinate: str, prop: str, spec: dict) -> dict:
    return {
        'type': 'check_cell',
        'sheet_idx': sheet_idx,
        'coordinate': coordinate,
        'props': {prop: spec},
    }


def _rules() -> list[dict]:
    """Two rules the starting file fails and one it already holds."""
    return [
        _cell(0, 'A2', 'value', {'method': 'eq', 'ref': 'Rent'}),
        _cell('RNSheet1', 'B4', 'value', {'method': 'eq', 'ref': 1500}),
        _cell(0, 'B5', 'merge', {'method': 'eq', 'ref': True}),
    ]


def _task_config(
    file_name: str = FILE,
    *,
    func: str = 'compare_table',
    rules: list[dict] | None = None,
    instruction: str = 'Fill in the total and merge the closing row.',
    expected: bool = True,
    task_id: str = TASK_ID,
) -> dict:
    """An OSWorld task config shaped like the LibreOffice ones the importer reads."""
    remote = f'https://example.invalid/{file_name}'
    download = {
        'type': 'download',
        'parameters': {'files': [{'path': f'{DESKTOP}/{file_name}', 'url': remote}]},
    }
    evaluator: dict = {
        'func': func,
        'result': {'type': 'vm_file', 'path': f'{DESKTOP}/{file_name}'},
    }
    if expected:
        evaluator['expected'] = {
            'type': 'cloud_file',
            'path': f'https://example.invalid/gold/{file_name}',
        }
    if func == 'compare_table':
        evaluator['options'] = {'rules': _rules() if rules is None else rules}
    return {
        'id': task_id,
        'instruction': instruction,
        'config': [download, {'type': 'open', 'parameters': {'path': f'{DESKTOP}/{file_name}'}}],
        'evaluator': evaluator,
    }


def _parse(config: dict, *, domain: str = CALC) -> Task:
    return parse_task(config['id'], domain, TITLE, config)


def _import(
    tmp_path: Path, config: dict, source: Path, gold: Path | None, *, domain: str = CALC
) -> tuple[ComputerUseEnvironment, Path]:
    """Import one task from the local *source* and *gold* files, and load it back."""
    task = parse_task(config['id'], domain, TITLE, config)
    out = tmp_path / 'environments' / 'osworld'
    out.mkdir(parents=True, exist_ok=True)
    install_shared(out)
    build_environment(task, source, gold, out, load_checks_module())
    return load_environment_dir(out / task.task_id), out


def _calc_env(tmp_path: Path, *, rules: list[dict] | None = None):
    source = make_xlsx(tmp_path / 'source.xlsx', [('Sheet1', _START, [])])
    gold = make_xlsx(tmp_path / 'gold.xlsx', [('Sheet1', _GOLD, _MERGED)])
    return _import(tmp_path, _task_config(rules=rules), source, gold)


def _doc_env(tmp_path: Path, *, gold_text=None):
    source = make_docx(tmp_path / 'source.docx', _DOC_TEXT)
    gold = make_docx(tmp_path / 'gold.docx', _DOC_GOLD if gold_text is None else gold_text)
    config = _task_config(DOC, func='compare_docx_files')
    return _import(tmp_path, config, source, gold, domain=WRITER)


def _run_verifier(env: ComputerUseEnvironment, home: Path, work: Path) -> dict:
    """Run *env*'s verifier as Session.score does: its own HOME, the agent's by name."""
    for rel, text in env.files.items():
        (work / rel).parent.mkdir(parents=True, exist_ok=True)
        (work / rel).write_text(text)
    (work / '_final_verifier.py').write_text(env.final_verifier_code)
    proc = subprocess.run(
        [sys.executable, '-I', '_final_verifier.py'],
        capture_output=True,
        text=True,
        cwd=work,
        env={'HOME': str(work), 'DEEPGYM_AGENT_HOME': str(home)},
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip().splitlines()[-1])


def _save(tmp_path: Path, home: Path, cells: dict, merges: list[str], *, name: str = FILE) -> None:
    """Save a workbook to ~/Desktop/<name> of the agent's home, where the task saves."""
    saved = make_xlsx(tmp_path / 'state.xlsx', [('Sheet1', cells, merges)])
    (home / 'Desktop').mkdir(parents=True, exist_ok=True)
    shutil.copyfile(saved, home / 'Desktop' / name)


@pytest.fixture()
def work(tmp_path: Path) -> Path:
    path = tmp_path / 'work'
    path.mkdir()
    return path


# --- The generated folder, as the loader and deepgym check see it. ---


def test_imported_env_loads_as_computer_use(tmp_path: Path) -> None:
    env, out = _calc_env(tmp_path)
    env_dir = out / TASK_ID

    assert isinstance(env, ComputerUseEnvironment)
    assert sorted(path.name for path in env_dir.iterdir()) == [
        'assets',
        'metadata.json',
        'setup.sh',
        'task.md',
        'variants.json',
        'verifier.py',
    ]
    # Spec files stay out of the session; the starting file is staged instead.
    assert set(env.files) == {f'assets/{FILE}.b64'}
    assert not any('checks' in rel for rel in env.files)
    assert 'def report(' in env.final_verifier_code
    asset = (env_dir / 'assets' / f'{FILE}.b64').read_text()
    assert base64.b64decode(asset) == (tmp_path / 'source.xlsx').read_bytes()
    assert f'assets/{FILE}.b64' in env.setup_script
    assert env.task.startswith('Fill in the total and merge the closing row.')
    assert '$' not in env.task


def test_metadata_and_registry_entry_describe_a_desktop_task(tmp_path: Path) -> None:
    _, out = _calc_env(tmp_path)
    metadata = json.loads((out / TASK_ID / 'metadata.json').read_text())
    assert metadata == {
        'id': TASK_ID,
        'name': TITLE,
        'type': 'computer-use',
        'difficulty': 'medium',
        'domain': 'libreoffice-calc',
        'tags': ['osworld', 'libreoffice', 'calc', 'desktop', 'gui'],
        'max_steps': 30,
    }
    assert build_registry_entry(_parse(_task_config())) == {
        'id': TASK_ID,
        'name': TITLE,
        'path': f'environments/osworld/{TASK_ID}',
        'type': 'computer-use',
        'benchmark': 'osworld',
        'variants': 1,
        'difficulty': 'medium',
        'domain': 'libreoffice-calc',
        'family': 'computer-use',
        'tags': ['osworld', 'libreoffice', 'calc', 'desktop', 'gui'],
    }


def test_task_md_names_the_file_the_app_and_the_done_action() -> None:
    text = build_task_md(_parse(_task_config()))
    assert text.startswith('Fill in the total and merge the closing row.')
    assert f'~/Desktop/{FILE}' in text
    assert 'LibreOffice Calc' in text and 'Ctrl+S' in text and '`done`' in text

    writer = _parse(_task_config(DOC, func='compare_docx_files'), domain=WRITER)
    assert 'LibreOffice Writer' in build_task_md(writer)

    # task.md is substituted as a string.Template at load time.
    loud = _parse(_task_config(instruction='Show the $ total.'))
    with pytest.raises(ValueError, match='contains'):
        build_task_md(loud)


def test_setup_script_decodes_the_staged_file() -> None:
    script = build_setup(_parse(_task_config()))
    assert f'assets/{FILE}.b64' in script
    assert f'"$HOME/Desktop/{FILE}"' in script
    assert '--calc' in script and '--writer' not in script
    assert 'sudo' not in script

    writer = _parse(_task_config(DOC, func='compare_docx_files'), domain=WRITER)
    assert '--writer' in build_setup(writer)


# --- Scoring: the saved file, never the screen. ---


def test_scores_untouched_half_done_and_finished_files(tmp_path: Path, work: Path) -> None:
    env, _ = _calc_env(tmp_path)
    home = tmp_path / 'home'
    for label, cells, merges, score in (
        ('untouched', _START, [], 0.0),
        ('total only', {**_START, 'B4': 1500}, [], 0.5),
        ('finished', _GOLD, _MERGED, 1.0),
    ):
        _save(tmp_path, home, cells, merges)
        result = _run_verifier(env, home, work)
        assert result['score'] == score, label
        assert result['passed'] is (score == 1.0), label
        assert {case['id'] for case in result['cases']} == {
            'workbook_saved',
            'rule0_check_cell',
            'rule1_check_cell',
            'rule2_check_cell',
        }, label

    # Nothing saved: every check fails and the guard says why.
    result = _run_verifier(env, tmp_path / 'empty-home', work)
    assert result['score'] == 0.0
    assert 'workbook_saved' in result['details']


def test_rules_the_starting_file_holds_become_guards(tmp_path: Path, work: Path) -> None:
    """Saving the starting file untouched must earn nothing, so a rule it already
    holds is a guard, and only the rules that need work are progress."""
    env, out = _calc_env(tmp_path)
    variant = json.loads((out / TASK_ID / 'variants.json').read_text())[0]

    assert variant['result'] == f'Desktop/{FILE}'
    assert [rule['coordinate'] for rule in variant['progress']] == ['B4', 'B5']
    assert [rule['coordinate'] for rule in variant['guards']] == ['A2']
    assert [rule['name'] for rule in variant['progress']] == [
        'rule1_check_cell',
        'rule2_check_cell',
    ]

    home = tmp_path / 'home'
    _save(tmp_path, home, _START, [])
    assert _run_verifier(env, home, work)['score'] == 0.0


def test_a_date_only_matches_a_cell_shown_as_that_date(tmp_path: Path, work: Path) -> None:
    """pandas reads a date-formatted cell as a datetime, so the right serial typed as
    a plain number does not match the reference's date."""
    head = {'A1': 'Start', 'B1': 'Due'}
    start = {**head, 'A2': Date(40437)}
    done = {**start, 'B2': Date(40557)}
    source = make_xlsx(tmp_path / 'source.xlsx', [('Sheet1', start, [])])
    gold = make_xlsx(tmp_path / 'gold.xlsx', [('Sheet1', done, [])])
    rules = [{'type': 'sheet_data', 'sheet_idx0': 0, 'sheet_idx1': 'EI0'}]
    env, _ = _import(tmp_path, _task_config(rules=rules), source, gold)

    home = tmp_path / 'home'
    for label, cells, score in (
        ('the serial as a plain number', {**start, 'B2': 40557}, 0.0),
        ('the date', done, 1.0),
    ):
        _save(tmp_path, home, cells, [])
        assert _run_verifier(env, home, work)['score'] == score, label


def test_a_saved_file_too_large_to_read_scores_zero(tmp_path: Path, work: Path) -> None:
    """One cell at the far corner of a sheet would make a dense grid of a billion
    cells: the workbook counts as unreadable (a scored 0), not a verifier crash."""
    env, _ = _calc_env(tmp_path)
    home = tmp_path / 'home'
    _save(tmp_path, home, {**_GOLD, 'AMJ1048576': 'x'}, _MERGED)

    result = _run_verifier(env, home, work)

    assert result['score'] == 0.0
    assert 'workbook_saved' in result['details']


def test_the_main_document_part_is_the_one_the_package_names(tmp_path: Path) -> None:
    """python-docx reads the part the officeDocument relationship names, so a stray
    word/document.xml holding the expected text is not what gets scored."""
    checks = load_checks_module()
    doc = make_docx(tmp_path / 'real.docx', _DOC_TEXT)
    with zipfile.ZipFile(doc) as archive:
        real = archive.read('word/document.xml')
    forged = tmp_path / 'forged.docx'
    main = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument'
    with zipfile.ZipFile(forged, 'w') as archive:
        archive.writestr(
            '_rels/.rels',
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Id="rId1" Type="{main}" Target="word/real.xml"/></Relationships>',
        )
        archive.writestr('word/real.xml', real)
        with zipfile.ZipFile(make_docx(tmp_path / 'gold.docx', _DOC_GOLD)) as gold:
            archive.writestr('word/document.xml', gold.read('word/document.xml'))

    assert checks.read_docx_text(str(forged)) == checks.read_docx_text(str(doc))


def test_a_sheet_rule_is_one_all_or_nothing_check(tmp_path: Path, work: Path) -> None:
    """compare_table compares a whole sheet, so fixing one cell of it earns nothing;
    and values within the rule's precision match, as pandas' rounding makes them."""
    head = {'A1': 'Name', 'B1': 'Amount', 'A2': 'a', 'A3': 'b', 'A4': 'c'}
    start = {**head, 'B2': 1.0, 'B3': 2.5, 'B4': 3.0}
    done = {**head, 'B2': 1.5, 'B3': 2.5, 'B4': 4.0}
    source = make_xlsx(tmp_path / 'source.xlsx', [('Sheet1', start, [])])
    gold = make_xlsx(tmp_path / 'gold.xlsx', [('Sheet1', done, [])])
    rules = [{'type': 'sheet_data', 'sheet_idx0': 0, 'sheet_idx1': 'EI0'}]
    env, _ = _import(tmp_path, _task_config(rules=rules), source, gold)

    home = tmp_path / 'home'
    for label, cells, score in (
        ('untouched', start, 0.0),
        ('one of the two cells fixed', {**start, 'B4': 4.0}, 0.0),
        ('within the precision', {**start, 'B2': 1.50001, 'B4': 4.0}, 1.0),
        ('past the precision', {**start, 'B2': 1.5002, 'B4': 4.0}, 0.0),
        ('finished', done, 1.0),
    ):
        _save(tmp_path, home, cells, [])
        assert _run_verifier(env, home, work)['score'] == score, label


def test_text_tasks_compare_the_saved_text(tmp_path: Path, work: Path) -> None:
    env, out = _doc_env(tmp_path)
    variant = json.loads((out / TASK_ID / 'variants.json').read_text())[0]
    assert set(variant) == {'result', 'expected_text'}
    assert variant['result'] == f'Desktop/{DOC}'
    assert variant['expected_text'] == 'presentation instruction describe some customs in china.'

    home = tmp_path / 'home'
    for label, text, score in (
        ('untouched', _DOC_TEXT, 0.0),
        ('halfway', ['presentation instruction', 'Describe some customs in China.'], 0.0),
        ('finished', _DOC_GOLD, 1.0),
    ):
        (home / 'Desktop').mkdir(parents=True, exist_ok=True)
        make_docx(home / 'Desktop' / DOC, text)
        assert _run_verifier(env, home, work)['score'] == score, label

    result = _run_verifier(env, tmp_path / 'empty-home', work)
    assert result['score'] == 0.0 and 'document_saved' in result['details']


# --- Imports that would produce a task the starting state already solves. ---


def test_a_task_the_starting_file_already_solves_is_rejected(tmp_path: Path) -> None:
    source = make_xlsx(tmp_path / 'source.xlsx', [('Sheet1', _START, [])])
    gold = make_xlsx(tmp_path / 'gold.xlsx', [('Sheet1', _GOLD, _MERGED)])
    with pytest.raises(ValueError, match='needs no work'):
        _import(tmp_path, _task_config(rules=[_rules()[0]]), source, gold)

    with pytest.raises(ValueError, match='needs no work'):
        _doc_env(tmp_path, gold_text=_DOC_TEXT)


def test_a_reference_that_fails_a_rule_is_rejected(tmp_path: Path) -> None:
    source = make_xlsx(tmp_path / 'source.xlsx', [('Sheet1', _START, [])])
    gold = make_xlsx(tmp_path / 'gold.xlsx', [('Sheet1', {**_START, 'B4': 1400}, _MERGED)])
    with pytest.raises(ValueError, match='reference file fails'):
        _import(tmp_path, _task_config(), source, gold)


# --- Task configs the importer does not port. ---


def _updated(config: dict, path: tuple, value: object) -> dict:
    """A deep copy of *config* with the value at the nested *path* replaced."""
    clone = copy.deepcopy(config)
    node = clone
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    return clone


def _rule(config: dict, rule: dict) -> dict:
    return _updated(config, ('evaluator', 'options', 'rules'), [rule])


def _cell_rule(method: str, *, sheet_idx: object = 0, **props: object) -> dict:
    return {
        'type': 'check_cell',
        'sheet_idx': sheet_idx,
        'coordinate': 'A1',
        'props': props or {'value': {'method': method, 'ref': 1}},
    }


def _other_id(config: dict) -> dict:
    return _updated(config, ('id',), 'another')


def _no_instruction(config: dict) -> dict:
    return _updated(config, ('instruction',), '  ')


def _no_open(config: dict) -> dict:
    return _updated(config, ('config',), config['config'][:1])


def _two_downloads(config: dict) -> dict:
    return _updated(config, ('config',), [config['config'][0], *config['config']])


def _two_files(config: dict) -> dict:
    other = {'path': f'{DESKTOP}/other.xlsx', 'url': 'https://example.invalid/other.xlsx'}
    files = config['config'][0]['parameters']['files']
    return _updated(config, ('config', 0, 'parameters', 'files'), [*files, other])


def _opens_another(config: dict) -> dict:
    return _updated(config, ('config', 1, 'parameters', 'path'), f'{DESKTOP}/other.xlsx')


def _local_result(config: dict) -> dict:
    return _updated(config, ('evaluator', 'result', 'type'), 'local_file')


def _result_names_another(config: dict) -> dict:
    return _updated(config, ('evaluator', 'result', 'path'), f'{DESKTOP}/other.xlsx')


def _pptx_evaluator(config: dict) -> dict:
    return _updated(config, ('evaluator', 'func'), 'compare_pptx_files')


def _no_rules(config: dict) -> dict:
    return _updated(config, ('evaluator', 'options'), {})


def _chart_rule(config: dict) -> dict:
    return _rule(config, {'type': 'compare_chart'})


def _half_sheet_data(config: dict) -> dict:
    return _rule(config, {'type': 'sheet_data', 'sheet_idx0': 0})


def _bare_cell_rule(config: dict) -> dict:
    return _rule(config, {'type': 'check_cell', 'sheet_idx': 0, 'coordinate': 'A1'})


def _style_prop(config: dict) -> dict:
    return _rule(config, _cell_rule('eq', style={'method': 'eq', 'ref': 1}))


def _contains(config: dict) -> dict:
    return _rule(config, _cell_rule('contains'))


def _bad_tolerance(config: dict) -> dict:
    return _rule(config, _cell_rule('approx:tight'))


def _bad_index(config: dict) -> dict:
    return _rule(config, _cell_rule('eq', sheet_idx='XX0'))


def _unstaged_name(config: dict) -> dict:
    name = 'a;b.xlsx'
    file = {'path': f'{DESKTOP}/{name}', 'url': 'https://example.invalid/x'}
    patched = _updated(config, ('config', 0, 'parameters', 'files'), [file])
    return _updated(patched, ('config', 1, 'parameters', 'path'), f'{DESKTOP}/{name}')


_REJECTED = [
    ('no instruction', _no_instruction, 'no instruction'),
    ('no open step', _no_open, 'one download and one open'),
    ('two downloads', _two_downloads, 'one download and one open'),
    ('two files in one download', _two_files, 'one downloaded file'),
    ('opening another file than the one staged', _opens_another, 'not the downloaded'),
    ('a result that is not the saved file', _local_result, 'is not the saved'),
    ('a result that names another file', _result_names_another, 'is not the saved'),
    ('an evaluator that is not ported', _pptx_evaluator, 'is not ported yet'),
    ('compare_table without a rules list', _no_rules, 'without a rules list'),
    ('a rule that is not ported', _chart_rule, 'is not ported yet'),
    ('sheet_data without its second index', _half_sheet_data, "without 'sheet_idx1'"),
    ('check_cell without props', _bare_cell_rule, 'without props'),
    ('a prop that is not ported', _style_prop, 'is not ported yet'),
    ('a comparison that is not ported', _contains, 'is not ported yet'),
    ('a tolerance that is not a number', _bad_tolerance, 'bad'),
    ('a sheet index that is not ported', _bad_index, 'is not ported yet'),
    ('a file name that cannot be staged', _unstaged_name, 'is not stageable'),
]


@pytest.mark.parametrize(
    ('label', 'mutate', 'match'), _REJECTED, ids=[case[0] for case in _REJECTED]
)
def test_a_task_the_importer_does_not_port_is_rejected(label: str, mutate, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        _parse(mutate(_task_config()))


def test_a_config_that_is_not_the_task_asked_for_is_rejected() -> None:
    with pytest.raises(ValueError, match='does not match'):
        parse_task(TASK_ID, CALC, TITLE, _other_id(_task_config()))


def test_a_text_task_without_a_usable_reference_is_rejected() -> None:
    with pytest.raises(ValueError, match='needs a reference file'):
        _parse(_task_config(DOC, func='compare_docx_files', expected=False), domain=WRITER)

    odd = _task_config(DOC, func='compare_docx_files')
    odd['evaluator']['expected'] = {'type': 'vm_file', 'path': f'{DESKTOP}/{DOC}'}
    with pytest.raises(ValueError, match='is not a cloud_file'):
        _parse(odd, domain=WRITER)


def test_the_imported_tasks_are_unique_libreoffice_tasks() -> None:
    ids = [task_id for task_id, _, _ in TASKS]
    assert len(set(ids)) == len(ids)
    assert {domain for _, domain, _ in TASKS} == {CALC, WRITER}
    titles = [title for _, _, title in TASKS]
    assert len(set(titles)) == len(titles) and all(titles)


# --- Downloads: the fallbacks that make a blocked network work. ---


def test_fetch_task_falls_back_to_the_contents_api(monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list[str] = []

    def fake(url: str, *, accept: str | None = None) -> bytes:
        asked.append(url)
        if url.startswith(_TASK_URL):
            raise OSError('blocked')
        return b'{"id": "abc"}'

    monkeypatch.setattr('import_osworld.download', fake)
    assert fetch_task('abc', CALC) == {'id': 'abc'}
    assert asked == [f'{_TASK_URL}/{CALC}/abc.json', f'{_TASK_API_URL}/{CALC}/abc.json']

    def refuse(url: str, *, accept: str | None = None) -> bytes:
        raise OSError('blocked')

    monkeypatch.setattr('import_osworld.download', refuse)
    with pytest.raises(RuntimeError, match='raw.githubusercontent.com'):
        fetch_task('abc', CALC)


def test_fetch_file_mirrors_huggingface_and_leaves_other_hosts_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[str] = []

    def fake(url: str, *, accept: str | None = None) -> bytes:
        asked.append(url)
        if 'hf-mirror' not in url:
            raise OSError('blocked')
        return b'file bytes'

    monkeypatch.setattr('import_osworld.download', fake)
    host = 'https://huggingface.co/datasets/x/y/resolve/main/a.xlsx'
    fetch_file(host, tmp_path / 'a.xlsx')
    assert asked == [host, host.replace('huggingface.co', 'hf-mirror.com')]
    assert (tmp_path / 'a.xlsx').read_bytes() == b'file bytes'

    asked.clear()

    def any_host(url: str, *, accept: str | None = None) -> bytes:
        asked.append(url)
        return b'file bytes'

    monkeypatch.setattr('import_osworld.download', any_host)
    fetch_file('https://example.com/a.xlsx', tmp_path / 'b.xlsx')
    assert asked == ['https://example.com/a.xlsx']
