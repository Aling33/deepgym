"""Scripted reference trajectories for the built-in computer-use envs.

Coordinates are screenshot pixels on Daytona's default 1024x768 desktop.
"""

from deepgym import Action


def click(x: int, y: int) -> Action:
    return Action(action_type='click', x=x, y=y)


def key(chord: str) -> Action:
    return Action(action_type='key', content=chord)


def type_(text: str) -> Action:
    return Action(action_type='type', content=text)


DONE = Action(action_type='done')

REFERENCE: dict[str, list[Action]] = {
    'signup_form': [
        click(512, 177),
        type_('Ada Lovelace'),
        click(512, 254),
        type_('ada@example.com'),
        key('Tab'),
        type_('Team'),
        click(305, 380),
        click(512, 441),
        DONE,
    ],
    'todo_list': [
        click(279, 243),
        click(743, 185),
        click(463, 119),
        type_('Book flights'),
        key('Return'),
        type_('Pay rent'),
        key('Return'),
        DONE,
    ],
    'settings_tabs': [
        click(512, 210),
        key('ctrl+a'),
        type_('Grace Hopper'),
        click(376, 121),
        click(784, 191),
        click(497, 121),
        click(239, 250),
        click(290, 446),
        DONE,
    ],
    'expense_sheet': [
        click(407, 179),
        key('ctrl+a'),
        type_('Groceries'),
        click(707, 218),
        key('ctrl+a'),
        type_('75'),
        click(259, 310),
        type_('Gym'),
        key('Tab'),
        type_('45'),
        click(351, 349),
        DONE,
    ],
    'file_manager': [
        click(400, 350),
        key('ctrl+shift+n'),
        type_('Archive'),
        key('Return'),
        click(400, 450),
        type_('report'),
        key('Escape'),
        key('ctrl+x'),
        type_('Archive'),
        key('Return'),
        key('ctrl+v'),
        click(100, 102),
        click(400, 450),
        type_('notes'),
        key('Escape'),
        key('F2'),
        type_('todo'),
        key('Return'),
        DONE,
    ],
}
