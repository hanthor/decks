# Decks — Specification

**Decks** is a presentation app for the GNOME desktop (PowerPoint-equivalent), part of a
FOSS office suite alongside [Letters](https://github.com/codelogistics/letters) (word
processor) and [Tables](https://github.com/hanthor/tables) (spreadsheet). It follows the
Letters pattern: **pure libadwaita chrome wrapping a `WebKit.WebView` engine**, with
**in-process Python libraries** doing file I/O. See
[suite-common](https://github.com/hanthor/suite-common) for the shared architecture.

- **App ID:** `io.github.hanthor.decks`
- **Runtime:** `org.gnome.Platform` 50, Flatpak
- **Stack:** Python + PyGObject + GTK4 + libadwaita + WebKitGTK 6.0 + Blueprint
- **License:** GPLv3-or-later (matches the suite)

## Why a canvas, not contenteditable

PowerPoint's model is **freeform, absolute-positioned boxes** (text frames, shapes,
images per slide) — not flowing text. That maps to a canvas editor, so Decks diverges from
Letters' contenteditable surface here.

## Engine (best-of-breed, all MIT)

| Concern | Library | Notes |
|---------|---------|-------|
| Editing canvas | **Fabric.js** | add/move/resize/rotate text boxes, shapes, images; SVG in/out |
| Present mode | **Reveal.js** | full-screen navigation + transitions; render the Fabric scene graph to Reveal slides |

Engines are vendored as minified UMD bundles in `src/vendor/`, gresource'd, and
`<script>`-loaded into the HTML passed to `webview.load_html(...)`. No Node runtime ships;
the webview stays offline/sandboxed.

## File I/O (in-process Python, vendored as `python3-*` pip modules)

| Format | Read | Write |
|--------|------|-------|
| `.pptx` | `python-pptx` | `python-pptx` |
| `.odp` | `odfpy` | `odfpy` |
| PDF | — | export Reveal deck (print-to-PDF) or WeasyPrint on exported HTML |

The bridge maps each slide's shapes ↔ Fabric objects (text frames, autoshapes, pictures;
positions in EMUs) over the `UserContentManager` script-message channel. Mirrors Letters'
`pypandoc` flow.

## Chrome (from suite-common, plus a slide sidebar)

`Adw.ApplicationWindow` + `Adw.TabView` (one deck per tab), header bar, preferences,
shortcuts, about, error toasts — **plus** an `Adw.NavigationSplitView` / `GtkListView`
**slide-thumbnail sidebar** for reorder/add/delete (the one piece of chrome Letters lacks).
Target gnome-gui-spec parity with Letters (85/92 baseline).

## Repo layout

See [suite-common](https://github.com/hanthor/suite-common). `engine.js` initializes
Fabric.js + Reveal.js; `subprojects/suite-common/` provides the shell + bridge.

## Verification (end-to-end)

1. Build the Flatpak (vendored JS + pip libs).
2. Launch; confirm libadwaita chrome + slide sidebar render.
3. Open a sample `.pptx` → slides + text/shape/image boxes load in Fabric; add/move a
   text box; enter present mode (Reveal); Save → reopen in LibreOffice/PowerPoint to
   confirm round-trip.
4. Repeat for `.odp`; export PDF.
5. Run gnome-gui-spec audit; target Letters parity.

See repo **Issues** for the tracer-bullet vertical-slice build order.
