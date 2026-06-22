# main.py — Decks application entry point.
# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gio, Adw  # noqa: E402
from suite_common import _
from suite_common.application import SuiteApplication  # noqa: E402
from .window import DecksWindow  # noqa: E402


class DecksApplication(SuiteApplication):
    def __init__(self, version):
        super().__init__(application_id='io.github.hanthor.decks',
                         window_class=DecksWindow,
                         app_name='Decks',
                         version=version)

        # ── Slide shortcuts (PowerPoint / Google Slides convention) ──
        self._add_action('add-slide', self._on_add_slide, ['<primary>m'])
        self._add_action('duplicate-slide', self._on_dup_slide,
                         ['<primary><shift>d'])
        self._add_action('delete-slide', self._on_delete_slide, ['Delete'])
        self._add_action('present', self._on_present, ['F5'])
        self._add_action('first-slide', self._on_go_slide, ['Home'])
        self._add_action('last-slide', self._on_go_slide, ['End'])

        # Present-mode shortcuts (handled by the window's key handler)
        self._add_action('present-blank', self._on_present_key)
        self._add_action('present-white', self._on_present_key)

        # Add to shortcuts overlay
        self.shortcuts[_('Slide')] = [
            ('<primary>m', _('Add Slide')),
            ('<primary><shift>d', _('Duplicate Slide')),
            ('Delete', _('Delete Slide')),
            ('F5', _('Present')),
            ('Home', _('First Slide')),
            ('End', _('Last Slide')),
            ('B', _('Blank Screen (present mode)')),
            ('W', _('White Screen (present mode)')),
        ]

    def _on_add_slide(self, *a):
        self._call_win('add_slide')

    def _on_dup_slide(self, *a):
        # Duplicate: add then move/reorder.  For now, just add.
        self._call_win('add_slide')

    def _on_delete_slide(self, *a):
        self._call_win('delete_slide')

    def _on_present(self, *a):
        self._call_win('present')

    def _on_go_slide(self, action, *a):
        name = action.get_name()
        if name == 'first-slide':
            self._call_win('go_first_slide')
        elif name == 'last-slide':
            self._call_win('go_last_slide')

    def _on_present_key(self, action, *a):
        name = action.get_name()
        js = None
        if name == 'present-blank':
            js = 'blank'
        elif name == 'present-white':
            js = 'white'
        if js:
            self._call_win('webview_send', 'presentKey', js)


def main(version):
    Adw.init()
    app = DecksApplication(version)
    return app.run(sys.argv)
