# Vendored icon font

`fa-solid-subset.ttf` is a seven-glyph subset of Font Awesome 5 Free Solid.

- Icons: Font Awesome Free, licensed CC BY 4.0
  (https://fontawesome.com/license/free). Attribution: Font Awesome by
  Fonticons, Inc. (https://fontawesome.com).
- The font file format is licensed SIL OFL 1.1.

Glyphs included and where Corky uses them:

| codepoint | name               | Corky use             |
|-----------|--------------------|-----------------------|
| U+F029    | qrcode             | home: scan            |
| U+F084    | key                | home: key             |
| U+F7D9    | tools              | home: tools           |
| U+F013    | cog                | home: settings        |
| U+F011    | power-off          | settings: power off   |
| U+F05A    | info-circle        | settings: about       |
| U+F019    | download           | (kept; no screen yet) |

Rebuilt 2026-09-05 with fonttools (`python3 -m fontTools.subset`) from the
`fa-solid-900.ttf` that ships inside the sha256-verified Sparrow 2.5.4
release (`tests/sparrow/.build/ext/com.sparrowwallet.sparrow/font/`), so the
source file is one that is already verified for this repo. No other glyphs
are present.
