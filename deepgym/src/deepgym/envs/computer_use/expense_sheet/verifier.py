"""Runs with _checks.py prepended (load_state, report)."""


def amount(raw: object) -> float | None:
    try:
        return float(str(raw).replace('$', '').replace(',', '').strip())
    except ValueError:
        return None


state = load_state()
rows = {
    str(r.get('name', '')).strip().lower(): amount(r.get('amount')) for r in state.get('rows', [])
}
report(
    progress={
        'typo_fixed': 'groceries' in rows and 'grocries' not in rows,
        'internet_updated': rows.get('internet') == 75,
        'gym_added': rows.get('gym') == 45,
    },
    guards={
        'saved': state.get('saved') is True,
        'rent_untouched': rows.get('rent') == 1200,
        'groceries_amount_kept': rows.get('groceries', rows.get('grocries')) == 300,
    },
)
