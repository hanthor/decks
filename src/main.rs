// main.rs — Decks presentation app, pure Rust + gtk4-rs.
// SPDX-License-Identifier: GPL-3.0-or-later

use gtk4 as gtk;
use gtk::prelude::*;

mod window;

fn main() {
    let app = libadwaita::Application::new(Some("org.tunaos.decks"), Default::default());
    app.connect_activate(|app| {
        let win = window::DecksWindow::new(app);
        win.present();
    });
    app.run();
}
pub mod export;
