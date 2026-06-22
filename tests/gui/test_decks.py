#!/usr/bin/env python3
# Dogtail GUI test for Decks — drives the running Flatpak via AT-SPI.
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Uses AT-SPI actions (no X mouse synthesis) so it runs headlessly on Wayland.
#   python3 tests/gui/test_decks.py     (`just guitest` handles launch/teardown)

import os
import sys
import time

# Resolve suite-common: sibling clone (dev layout) or subproject (Flatpak build).
for _candidate in (
    os.path.join(os.path.dirname(__file__), '..', '..', '..', 'suite-common'),
    os.path.join(os.path.dirname(__file__), '..', '..', 'subprojects', 'suite-common'),
):
    if os.path.isdir(_candidate):
        sys.path.insert(0, _candidate)
        break

from dogtail import tree  # noqa: E402
from suite_common.test_helpers import click, count_nodes, find_app, find_widget, dump_tree


def main():
    app = find_app('decks')
    print('found application: decks')

    # The tools toolbar (Letters idiom): Add Text Box is the primary tool.
    # Use recursive find_widget because Gtk.Button(icon_name) inside an
    # AdwToolbarView top-bar Box may not surface via app.child().
    add_text = find_widget(app, name='Add Text Box', role='push button', showing_only=False)
    if add_text is None:
        print('DEBUG: a11y tree (shallow) — searching for Add Text Box...')
        dump_tree(app, max_depth=3)
        raise AssertionError('Add Text Box button not found in a11y tree')
    click(add_text)
    time.sleep(0.5)
    print('Add Text Box driven via AT-SPI: OK')

    # The slide sidebar controls are accessible.
    app.child(name='Add slide', roleName='push button', showingOnly=False)
    print('slide sidebar control "Add slide" found: OK')

    # The primary menu button.
    menu = app.child(name='Main Menu', roleName='toggle button', showingOnly=False)
    click(menu)
    time.sleep(0.4)
    print('primary menu found + activated: OK')

    # A slide row is listed in the sidebar.
    app.child(roleName='list box', showingOnly=False)
    print('slide list (list box) found: OK')

    nodes = count_nodes(app)
    assert nodes > 15, f'expected a populated a11y tree, got {nodes} nodes'
    print(f'a11y tree populated: {nodes} accessible nodes')

    print('GUITEST: PASS')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f'GUITEST: FAIL — {exc}')
        sys.exit(1)
