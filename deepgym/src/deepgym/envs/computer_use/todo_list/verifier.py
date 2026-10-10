"""Runs with _checks.py (load_state, report) and PARAMS prepended."""

entries = [
    (str(item.get('text', '')).strip().lower(), item.get('done'))
    for item in load_state().get('items', [])
]
items = dict(entries)
want = {key: value.lower() for key, value in PARAMS.items()}
report(
    progress={
        'added_first': want['add1'] in items,
        'added_second': want['add2'] in items,
        'completed': items.get(want['complete']) is True,
        'deleted': want['delete'] not in items,
    },
    guards={
        'other_item_untouched': items.get(want['keep']) is False,
        'no_duplicate_items': len(items) == len(entries),
    },
)
