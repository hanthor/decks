# window.py — Decks main window: slide sidebar + Fabric canvas.
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import os

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Gio, Adw, GLib  # noqa: E402
from suite_common.window import SuiteWindow  # noqa: E402
from suite_common.webview import SuiteWebView, build_document  # noqa: E402
from . import fileio  # noqa: E402

VENDOR_ASSETS = [
    ('css', 'reveal.css'),
    ('css', 'reveal-theme.css'),
    ('js', 'fabric.min.js'),
    ('js', 'reveal.js'),
]


class DecksWindow(SuiteWindow):
    def __init__(self, **kwargs):
        super().__init__(app_name='Decks', use_tabs=False, **kwargs)
        self._moduledir = os.path.dirname(__file__)
        self._selftest = os.environ.get('DECKS_SELFTEST')
        print('[decks] selftest =', self._selftest, flush=True)

        self.slides = [None]      # list of fabric JSON (None = blank)
        self.current = 0
        self._pending = None      # index to switch to after saving current
        self._present_pending = False
        self._presenting = False
        self._save_deck_path = None
        self._export_pending = None

        self.webview = SuiteWebView(on_message=self._on_message)

        self._build_layout()
        self._refresh_sidebar()
        self.webview.load_app(self._build_html())

    # ----- layout -----------------------------------------------------------

    def _build_layout(self):
        self.slide_list = Gtk.ListBox()
        self.slide_list.add_css_class('navigation-sidebar')
        self.slide_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.slide_list.connect('row-selected', self._on_row_selected)

        scroller = Gtk.ScrolledWindow()
        scroller.set_child(self.slide_list)
        scroller.set_vexpand(True)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4,
                           margin_top=6, margin_bottom=6, margin_start=6, margin_end=6)
        for icon, tip, cb in (
            ('list-add-symbolic', 'Add slide', lambda *_: self.add_slide()),
            ('list-remove-symbolic', 'Delete slide', lambda *_: self.delete_slide()),
            ('go-up-symbolic', 'Move up', lambda *_: self.move_slide(-1)),
            ('go-down-symbolic', 'Move down', lambda *_: self.move_slide(1)),
        ):
            btn = Gtk.Button(icon_name=icon)
            btn.set_tooltip_text(tip)
            btn.connect('clicked', cb)
            controls.append(btn)

        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sidebar.append(scroller)
        sidebar.append(controls)
        sidebar.set_size_request(200, -1)

        split = Adw.OverlaySplitView()
        split.set_sidebar(sidebar)
        split.set_content(self.webview)
        split.set_max_sidebar_width(260)
        self.set_main_content(split)
        self._split = split

        # Adaptive: collapse the slide sidebar into an overlay on narrow widths
        # (standard GNOME OverlaySplitView pattern).
        breakpoint_ = Adw.Breakpoint.new(
            Adw.BreakpointCondition.parse('max-width: 600sp'))
        breakpoint_.add_setter(split, 'collapsed', True)
        self.add_breakpoint(breakpoint_)

        open_btn = Gtk.Button(label='Open')
        open_btn.connect('clicked', lambda *_: self.open_deck())
        self.header_bar.pack_start(open_btn)

        save_btn = Gtk.Button(icon_name='document-save-symbolic')
        save_btn.set_tooltip_text('Save')
        save_btn.connect('clicked', lambda *_: self.save_deck())
        self.header_bar.pack_start(save_btn)

        export_btn = Gtk.Button(icon_name='document-send-symbolic')
        export_btn.set_tooltip_text('Export to PDF')
        export_btn.connect('clicked', lambda *_: self.export_pdf())
        self.header_bar.pack_start(export_btn)

        present_btn = Gtk.Button(icon_name='view-fullscreen-symbolic')
        present_btn.set_tooltip_text('Present')
        present_btn.connect('clicked', lambda *_: self.present())
        self.header_bar.pack_start(present_btn)

        # Letters idiom: a centered tools toolbar with a responsive extended/more split.
        def tool(icon, label, message):
            btn = Gtk.Button(icon_name=icon)
            btn.set_tooltip_text(label)
            btn.update_property([Gtk.AccessibleProperty.LABEL], [label])
            btn.connect('clicked', lambda *_: self.webview.send(message, None))
            return btn

        group = Gio.SimpleActionGroup()
        for name, message in (('text', 'addText'), ('shape', 'addRect')):
            act = Gio.SimpleAction.new(f'add-{name}', None)
            act.connect('activate', lambda a, p, m=message: self.webview.send(m, None))
            group.add_action(act)
        self.insert_action_group('insert', group)
        more = Gio.Menu()
        more.append('Add Text Box', 'insert.add-text')
        more.append('Add Shape', 'insert.add-shape')

        self.add_action_bar(
            primary=[tool('insert-text-symbolic', 'Add Text Box', 'addText')],
            extended=[tool('insert-object-symbolic', 'Add Shape', 'addRect')],
            more_menu=more)

        # Escape exits present mode.
        keys = Gtk.EventControllerKey()
        keys.connect('key-pressed', self._on_key)
        self.add_controller(keys)

    def _on_key(self, controller, keyval, keycode, state):
        from gi.repository import Gdk
        if keyval == Gdk.KEY_Escape and self._presenting:
            self._presenting = False
            self.unfullscreen()
            self.webview.send('edit', None)
            return True
        return False

    def _build_html(self):
        vendor_dir = os.path.join(self._moduledir, 'vendor')
        with open(os.path.join(self._moduledir, 'engine.js'), encoding='utf-8') as fh:
            engine = fh.read()
        body = (
            '<div id="editor" style="display:flex;justify-content:center;'
            'align-items:center;height:100vh;background:#dcdcdc">'
            '<canvas id="canvas" width="960" height="540" '
            'style="box-shadow:0 0 12px rgba(0,0,0,0.3)"></canvas></div>'
            '<div id="reveal" class="reveal" '
            'style="display:none;position:fixed;inset:0;background:#000">'
            '<div class="slides"></div></div>'
        )
        head_extra = f'<script>{engine}</script>'
        return build_document(vendor_dir, VENDOR_ASSETS, body, head_extra)

    # ----- slide management -------------------------------------------------

    def _refresh_sidebar(self):
        self.slide_list.remove_all()
        for i in range(len(self.slides)):
            row = Adw.ActionRow(title=f'Slide {i + 1}')
            self.slide_list.append(row)
        row = self.slide_list.get_row_at_index(self.current)
        if row:
            self.slide_list.select_row(row)

    def add_slide(self):
        # Save current, then append + switch.
        self.slides.append(None)
        self._pending = len(self.slides) - 1
        self.webview.send('getSlide', None)
        self._refresh_sidebar()

    def delete_slide(self):
        if len(self.slides) <= 1:
            return
        del self.slides[self.current]
        self.current = min(self.current, len(self.slides) - 1)
        self._refresh_sidebar()
        self.webview.send('loadSlide', self.slides[self.current])

    def move_slide(self, delta):
        target = self.current + delta
        if target < 0 or target >= len(self.slides):
            return
        self.slides[self.current], self.slides[target] = \
            self.slides[target], self.slides[self.current]
        self.current = target
        self._refresh_sidebar()

    def present(self):
        # Save the current slide, then present all of them fullscreen.
        self._present_pending = True
        self.webview.send('getSlide', None)

    # ----- deck file I/O ----------------------------------------------------

    def open_deck(self):
        dialog = Gtk.FileDialog(title='Open Presentation')
        flt = Gtk.FileFilter()
        flt.set_name('Presentations')
        flt.add_pattern('*.pptx')
        flt.add_pattern('*.odp')
        store = Gio.ListStore.new(Gtk.FileFilter)
        store.append(flt)
        dialog.set_filters(store)
        dialog.open(self, None, self._on_open_deck)

    def _on_open_deck(self, dialog, result):
        try:
            gfile = dialog.open_finish(result)
        except GLib.Error:
            return
        try:
            self.slides = fileio.read_deck(gfile.get_path()) or [None]
        except Exception as exc:  # noqa: BLE001
            print('[decks] open error:', exc, flush=True)
            return
        self.current = 0
        self._refresh_sidebar()
        self.webview.send('loadSlide', self.slides[0])

    def save_deck(self):
        dialog = Gtk.FileDialog(title='Save Presentation')
        dialog.set_initial_name('Untitled.pptx')
        dialog.save(self, None, self._on_save_deck)

    def _on_save_deck(self, dialog, result):
        try:
            gfile = dialog.save_finish(result)
        except GLib.Error:
            return
        self._save_deck_path = gfile.get_path()
        self.webview.send('getSlide', None)   # save current slide first, then write

    def export_pdf(self):
        dialog = Gtk.FileDialog(title='Export to PDF')
        dialog.set_initial_name('Untitled.pdf')
        dialog.save(self, None, self._on_export_pdf)

    def _on_export_pdf(self, dialog, result):
        try:
            gfile = dialog.save_finish(result)
        except GLib.Error:
            return
        self._start_export(gfile.get_path())

    def _start_export(self, path):
        self._export_pending = path
        self.webview.send('getSlide', None)   # capture current slide, then render all

    def _build_pdf(self, images):
        import base64
        from io import BytesIO
        from PIL import Image
        path = self._export_pending
        self._export_pending = None
        frames = []
        for url in images:
            if ',' in url:
                frames.append(Image.open(BytesIO(base64.b64decode(url.split(',', 1)[1]))).convert('RGB'))
        if not frames:
            print('[decks] export: nothing to render', flush=True)
            return
        frames[0].save(path, save_all=True, append_images=frames[1:])
        print('[decks] exported PDF', os.path.basename(path), len(frames), 'pages', flush=True)

    def _on_row_selected(self, listbox, row):
        if row is None:
            return
        idx = row.get_index()
        if idx == self.current:
            return
        self._pending = idx
        self.webview.send('getSlide', None)   # save current, then load pending

    def _switch_to_pending(self):
        if self._pending is None:
            return
        self.current = self._pending
        self._pending = None
        self.webview.send('loadSlide', self.slides[self.current])

    # ----- bridge -----------------------------------------------------------

    def _on_message(self, payload):
        kind = payload.get('type')
        if kind == 'ready':
            print('[decks] engine ready:', payload.get('engine'),
                  'reveal=', payload.get('reveal'), flush=True)
            if self._selftest:
                self._run_selftest()
            if os.environ.get('DECKS_PRESENT'):
                GLib.timeout_add(800, lambda: (self.present(), False)[1])
            if os.environ.get('DECKS_DECKTEST'):
                self._run_decktest()
            if os.environ.get('DECKS_PDFTEST'):
                GLib.timeout_add(
                    900, lambda: (self._start_export(os.environ['DECKS_PDFTEST']), False)[1])
        elif kind == 'slide':
            # Store the just-saved current slide, then dispatch.
            self.slides[self.current] = payload.get('data')
            if self._selftest_target:
                self._write_selftest(payload.get('data'))
            if self._export_pending:
                self.webview.send('renderAll', self.slides)
            elif self._save_deck_path:
                path = self._save_deck_path
                self._save_deck_path = None
                try:
                    fileio.write_deck(path, self.slides)
                    print('[decks] saved', os.path.basename(path), flush=True)
                except Exception as exc:  # noqa: BLE001
                    print('[decks] save error:', exc, flush=True)
            elif self._present_pending:
                self._present_pending = False
                self._presenting = True
                self.fullscreen()
                self.webview.send('present', self.slides)
            else:
                self._switch_to_pending()
        elif kind == 'rendered':
            self._build_pdf(payload.get('images') or [])
        elif kind == 'presenting':
            print('[decks] presenting', payload.get('slides'), 'slides', flush=True)
        elif kind == 'changed':
            pass

    def _run_decktest(self):
        base = os.environ['DECKS_DECKTEST']
        slide = {'version': '5.5.2', 'background': '#ffffff', 'objects': [
            {'type': 'i-text', 'text': 'HelloDeck', 'left': 100, 'top': 120,
             'width': 400, 'height': 60, 'fontSize': 32}]}
        results = []
        for ext in ('pptx', 'odp'):
            path = os.path.join(base, 'rt.' + ext)
            try:
                fileio.write_deck(path, [slide, slide])
                back = fileio.read_deck(path)
                texts = [o.get('text') for s in back for o in s.get('objects', [])
                         if o.get('type') == 'i-text']
                ok = ('HelloDeck' in texts) and len(back) == 2
                count = len(back)
            except Exception as exc:  # noqa: BLE001
                ok, count, texts = False, '?', [repr(exc)]
            print(f'[decks] decktest {ext}: slides={count} texts={texts} '
                  f'-> {"OK" if ok else "FAIL"}', flush=True)
            results.append(ok)

        # Image round-trip (pptx picture <-> Fabric image).
        img_url = ('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1'
                   'HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')
        img_slide = {'version': '5.5.2', 'background': '#ffffff', 'objects': [
            {'type': 'image', 'src': img_url, 'left': 100, 'top': 100,
             'width': 200, 'height': 150, 'scaleX': 1, 'scaleY': 1}]}
        try:
            p = os.path.join(base, 'img.pptx')
            fileio.write_deck(p, [img_slide])
            back = fileio.read_deck(p)
            has_img = any(o.get('type') == 'image'
                          for s in back for o in s.get('objects', []))
        except Exception as exc:  # noqa: BLE001
            has_img = False
            print('[decks] decktest image error:', exc, flush=True)
        print(f'[decks] decktest image: has_image={has_img} -> '
              f'{"OK" if has_img else "FAIL"}', flush=True)
        results.append(has_img)

        print('[decks] decktest result:', 'PASS' if all(results) else 'FAIL', flush=True)

    # ----- self-test --------------------------------------------------------

    _selftest_target = None

    def _run_selftest(self):
        try:
            _, _, out_path = self._selftest.partition(':')
            self._selftest_target = out_path
            print('[decks] selftest requesting slide', flush=True)
            GLib.timeout_add(600, lambda: (self.webview.send('getSlide', None), False)[1])
        except Exception as exc:  # noqa: BLE001
            print('[decks] selftest error:', exc, flush=True)

    def _write_selftest(self, data):
        target = self._selftest_target
        self._selftest_target = None
        try:
            with open(target, 'w', encoding='utf-8') as fh:
                json.dump(data, fh)
            print('[decks] selftest wrote slide JSON', flush=True)
        except OSError as exc:
            print('[decks] selftest write error:', exc, flush=True)
