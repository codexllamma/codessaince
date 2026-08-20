# Asset Licences

## Fonts

| File | Source | Licence | Notes |
|---|---|---|---|
| `fonts/NotoSans-Regular.ttf` | google/fonts repo, `ofl/notosans/NotoSans[wdth,wght].ttf`, instanced at wght=400/wdth=100 via fonttools | SIL Open Font License 1.1 | Redistributable, no attribution required |
| `fonts/NotoSans-Bold.ttf` | google/fonts repo, `ofl/notosans/NotoSans[wdth,wght].ttf`, instanced at wght=700/wdth=100 via fonttools | SIL Open Font License 1.1 | Redistributable, no attribution required |

Indic script fonts (NotoSansDevanagari-Bold.ttf, NotoSansTamil-Bold.ttf, NotoSansTelugu-Bold.ttf, NotoSansBengali-Bold.ttf) are not yet bundled — this slice is English-only. `typography.py` degrades gracefully (placeholder + log) rather than crashing when one of these is missing.

## B-roll video loops

None bundled yet. This slice uses procedural mesh-gradient backgrounds (README §10.2 fallback) in place of licensed B-roll footage.
