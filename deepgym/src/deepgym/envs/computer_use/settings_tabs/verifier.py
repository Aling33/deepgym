"""Runs with _checks.py (load_state, report) and PARAMS prepended."""

INITIAL = {'email_notifications': True, 'push_notifications': True, 'weekly_digest': False}

state = load_state()
toggle = PARAMS['toggle']
report(
    progress={
        'display_name': str(state.get('display_name', '')).strip() == PARAMS['display_name'],
        'notification_toggled': state.get(toggle) is (not INITIAL[toggle]),
        'theme': state.get('theme') == PARAMS['theme'],
    },
    guards={
        'saved': state.get('saved') is True,
        'other_notifications_untouched': all(
            state.get(key) is value for key, value in INITIAL.items() if key != toggle
        ),
    },
)
