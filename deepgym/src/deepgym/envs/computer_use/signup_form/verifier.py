"""Runs with _checks.py (load_state, report) and PARAMS prepended."""

state = load_state()
report(
    progress={
        'name': str(state.get('name', '')).strip() == PARAMS['name'],
        'email': str(state.get('email', '')).strip().lower() == PARAMS['email'].lower(),
        'plan': state.get('plan') == PARAMS['plan'].lower(),
        'agreed_to_terms': state.get('agreed') is True,
    },
    guards={'submitted': state.get('submitted') is True},
)
