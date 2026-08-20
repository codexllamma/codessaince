# Asset Licences

## Fonts

| File | Source | Licence | Notes |
|---|---|---|---|
| `fonts/NotoSans-Regular.ttf` | google/fonts repo, `ofl/notosans/NotoSans[wdth,wght].ttf`, instanced at wght=400/wdth=100 via fonttools | SIL Open Font License 1.1 | Redistributable, no attribution required |
| `fonts/NotoSans-Bold.ttf` | google/fonts repo, `ofl/notosans/NotoSans[wdth,wght].ttf`, instanced at wght=700/wdth=100 via fonttools | SIL Open Font License 1.1 | Redistributable, no attribution required |

Indic script fonts (NotoSansDevanagari-Bold.ttf, NotoSansTamil-Bold.ttf, NotoSansTelugu-Bold.ttf, NotoSansBengali-Bold.ttf) are not yet bundled — this slice is English-only. `typography.py` degrades gracefully (placeholder + log) rather than crashing when one of these is missing.

## B-roll video loops

None bundled yet. This slice uses procedural mesh-gradient backgrounds (README §10.2 fallback) in place of licensed B-roll footage.

## Presenter avatars

None bundled yet. `assets/avatars/manifest.json` is empty, so the presenter
layout is inactive and rendering uses the normal full-width composition.

Every avatar added must record its licence here **and** in the manifest, and
must declare a `source` of `synthetic`, `licensed_stock`, or
`consented_performer`. `services/avatar_registry.py` refuses to load any other
origin at parse time.

Animating a real, identifiable official's likeness is not permitted. That is a
deepfake of a named public figure in their official capacity, and no
disclosure label makes it acceptable for government communications — README
§21 already forbids cloning a named official's voice, and a face carries more
weight than a voice, not less.

Every avatar entry also requires a `disclosure_label`, which the compositor
renders on screen for as long as the presenter is visible. There is no code
path that draws an unlabelled synthetic presenter.

| Field | Value |
|---|---|
| `assets/avatars/*.mp4` | none bundled |
