"""Runs with _checks.py prepended (load_state, report)."""

state = load_state()
report(
    progress={
        'display_name': str(state.get('display_name', '')).strip() == 'Grace Hopper',
        'email_notifications_off': state.get('email_notifications') is False,
        'theme_dark': state.get('theme') == 'dark',
    },
    guards={
        'saved': state.get('saved') is True,
        'other_notifications_untouched': state.get('push_notifications') is True
        and state.get('weekly_digest') is False,
    },
)
