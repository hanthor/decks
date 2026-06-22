// export.rs — Typst export for Decks.
pub fn to_typst(slides: &[crate::engine::Slide]) -> String {
    let mut out = String::from("#set page(width: 16cm, height: 9cm)\n");
    for s in slides {
        out.push_str(&format!("#pagebreak()\n= {}\n", s.title));
        for obj in &s.objects {
            use crate::engine::SlideObject::*;
            match obj {
                TextBox { text, .. } => out.push_str(&format!("{}\n\n", text)),
                Rect { .. } => out.push_str("#rect(width: 100%, height: 100%)\n"),
            }
        }
    }
    out
}

pub fn to_pdf(slides: &[crate::engine::Slide], path: &str) -> Result<(), String> {
    let src = to_typst(slides);
    let world = typst::World::new(typst::CompilerFeat::default());
    let doc = typst::compile(&src, &world).map_err(|e| format!("{:?}", e))?;
    std::fs::write(path, &doc).map_err(|e| format!("{}", e))
}
