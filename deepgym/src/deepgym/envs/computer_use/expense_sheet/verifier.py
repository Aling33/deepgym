"""Runs with _checks.py (load_state, report) and PARAMS prepended."""


def amount(raw: object) -> float | None:
    try:
        return float(str(raw).replace('$', '').replace(',', '').strip())
    except ValueError:
        return None


state = load_state()
entries = [
    (str(row.get('name', '')).strip().lower(), amount(row.get('amount')))
    for row in state.get('rows', [])
]
entries = [(name, value) for name, value in entries if name or value is not None]
rows = dict(entries)
report(
    progress={
        'typo_fixed': 'groceries' in rows and 'grocries' not in rows,
        'internet_updated': rows.get('internet') == float(PARAMS['internet']),
        'row_added': rows.get(PARAMS['new_item'].lower()) == float(PARAMS['new_amount']),
    },
    guards={
        'saved': state.get('saved') is True,
        'rent_untouched': rows.get('rent') == 1200,
        'groceries_amount_kept': rows.get('groceries', rows.get('grocries')) == 300,
        'no_duplicate_rows': len(rows) == len(entries),
    },
)
