"""Scripted reference trajectories for the built-in computer-use envs, per variant.

Coordinates are screenshot pixels on Daytona's default 1024x768 desktop.
"""

import json
from collections.abc import Callable
from pathlib import Path

from deepgym import Action

ENVS_DIR = Path(__file__).resolve().parent.parent / 'src' / 'deepgym' / 'envs' / 'computer_use'
DONE = Action(action_type='done')

TODO_ROWS = ['Buy milk', 'Call mom', 'Write report']
NOTIFICATION_Y = {'email_notifications': 191, 'push_notifications': 243, 'weekly_digest': 295}
THEME_Y = {'light': 210, 'dark': 250, 'system': 290}


def click(x: int, y: int) -> Action:
    return Action(action_type='click', x=x, y=y)


def key(chord: str) -> Action:
    return Action(action_type='key', content=chord)


def type_(text: str) -> Action:
    return Action(action_type='type', content=text)


def variants(name: str) -> list[dict]:
    return json.loads((ENVS_DIR / name / 'variants.json').read_text())


def _signup(p: dict) -> list[Action]:
    return [
        click(512, 177), type_(p['name']),
        click(512, 254), type_(p['email']),
        key('Tab'), type_(p['plan']),
        click(305, 380), click(512, 441), DONE,
    ]  # fmt: skip


def _todo(p: dict) -> list[Action]:
    def row_y(text: str) -> int:
        return 185 + 58 * TODO_ROWS.index(text)

    return [
        click(279, row_y(p['complete'])),
        click(743, row_y(p['delete'])),
        click(463, 119), type_(p['add1']), key('Return'),
        type_(p['add2']), key('Return'), DONE,
    ]  # fmt: skip


def _settings(p: dict) -> list[Action]:
    return [
        click(512, 210), key('ctrl+a'), type_(p['display_name']),
        click(376, 121), click(784, NOTIFICATION_Y[p['toggle']]),
        click(497, 121), click(239, THEME_Y[p['theme']]),
        click(290, 446), DONE,
    ]  # fmt: skip


def _expense(p: dict) -> list[Action]:
    return [
        click(407, 179), key('ctrl+a'), type_('Groceries'),
        click(707, 218), key('ctrl+a'), type_(p['internet']),
        click(259, 310), type_(p['new_item']), key('Tab'), type_(p['new_amount']),
        click(351, 349), DONE,
    ]  # fmt: skip


def _files(p: dict) -> list[Action]:
    def stem(name: str) -> str:
        return name.rsplit('.', 1)[0]

    return [
        click(400, 350), key('ctrl+shift+n'), type_(p['folder']), key('Return'),
        click(400, 450), type_(stem(p['move'])), key('Escape'), key('ctrl+x'),
        type_(p['folder']), key('Return'), key('ctrl+v'),
        click(100, 75), click(400, 450),
        type_(stem(p['rename_from'])), key('Escape'), key('F2'),
        type_(stem(p['rename_to'])), key('Return'), DONE,
    ]  # fmt: skip


REFERENCE: dict[str, Callable[[dict], list[Action]]] = {
    'signup_form': _signup,
    'todo_list': _todo,
    'settings_tabs': _settings,
    'expense_sheet': _expense,
    'file_manager': _files,
}
