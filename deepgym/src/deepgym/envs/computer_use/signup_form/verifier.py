"""Runs with _checks.py prepended (load_state, report)."""

state = load_state()
report(
    progress={
        'name': str(state.get('name', '')).strip() == 'Ada Lovelace',
        'email': str(state.get('email', '')).strip().lower() == 'ada@example.com',
        'plan': state.get('plan') == 'team',
        'agreed_to_terms': state.get('agreed') is True,
    },
    guards={'submitted': state.get('submitted') is True},
)
