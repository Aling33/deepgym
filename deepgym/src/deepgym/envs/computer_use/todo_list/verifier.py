"""Runs with _checks.py prepended (load_state, report)."""

items = {
    str(i.get('text', '')).strip().lower(): i.get('done') for i in load_state().get('items', [])
}
report(
    progress={
        'added_book_flights': 'book flights' in items,
        'added_pay_rent': 'pay rent' in items,
        'call_mom_done': items.get('call mom') is True,
        'buy_milk_deleted': 'buy milk' not in items,
    },
    guards={'write_report_untouched': items.get('write report') is False},
)
