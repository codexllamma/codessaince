# Adding visual assets

Read this before adding backgrounds. The retrieval system ranks assets by
their **metadata**, never by their pixels — so how you describe an asset
decides whether it is ever used. A beautiful photo with thin metadata is dead
weight; a plain one described in the vocabulary of government notices gets
picked constantly.

See [`ASSET_PLAN.md`](ASSET_PLAN.md) for which domains to cover and what to
source for each.

## The fastest way

```bash
cd backend

# 1. Fetch stills from the curated Commons categories
../.venv/Scripts/python.exe scripts/build_image_library.py --per-category 7

# 2. Fetch b-roll clips (expect thin results — see the caveat below)
../.venv/Scripts/python.exe scripts/build_image_library.py --media video --per-category 3

# 3. REVIEW WHAT LANDED — do not skip this, see "Review" below
#    A contact sheet is written to out/inspect/image_library_sheet.png

# 4. Build the vector index
../.venv/Scripts/python.exe scripts/build_visual_index.py --reset

# 5. Check retrieval actually improved
../.venv/Scripts/python.exe scripts/query_visual_index.py "eligible farmer families" --compare
```

Re-run steps 4 and 5 after **any** change to the library or the sidecars. The
index is a snapshot; it does not notice new files on its own.

## Where assets live

```
assets/broll/library/<FACT_CATEGORY>/<name>.jpg        # the asset
assets/broll/library/<FACT_CATEGORY>/<name>.source.json # its metadata
```

`<FACT_CATEGORY>` ∈ `AUTHORITY`, `SCHEME_NAME`, `AMOUNT`, `DEADLINE`,
`ACTION_REQUIRED`, `ELIGIBILITY`, `BENEFICIARY`.

An asset with no sidecar is **skipped silently**. If something you added never
shows up, that is the first thing to check.

## The sidecar

```json
{
  "category": "ELIGIBILITY",
  "commons_title": "File:Smallholder paddy harvest.jpg",
  "description": "Two farmers cutting paddy by hand in a small field",
  "domains": ["agriculture", "rural_development"],
  "media_type": "image",
  "tags": ["farmer", "smallholder", "paddy", "harvest", "rural"],
  "licence": "CC BY-SA 4.0",
  "artist": "...",
  "source_page": "https://commons.wikimedia.org/wiki/File:...",
  "width": 2048, "height": 1365, "duration_sec": 0
}
```

The fetcher fills all of this in automatically. Two fields deserve your
attention because they are what makes retrieval good rather than adequate:

**`description`** — the highest-value field, and the only one written in prose
rather than keywords. It is the only part of an asset phrased the way a
narration line is phrased, which is exactly what the embedding model compares
against. Commons supplies one when the uploader wrote one; **when it is empty,
write it yourself.** One plain sentence describing what is happening in the
frame. `--retag` deliberately will not invent one.

**`tags`** — write the words a *notice* would use, not the words a
photographer would.

> good: `beneficiary`, `disbursement`, `verification`, `installment`, `kisan`
> useless: `golden hour`, `bokeh`, `wide angle`, `Nikon D850`

`domains` is derived from the category by `CATEGORY_DOMAINS` in the fetcher;
override it by hand if an asset genuinely spans two domains.

## Backfilling assets already on disk

```bash
../.venv/Scripts/python.exe scripts/build_image_library.py --retag
```

Offline, no downloads. Recomputes `tags`, fills in `domains` and `media_type`
for sidecars written before those fields existed. It prints
`(no description - add one by hand)` for every asset still missing one — that
list is your to-do.

## Review before you commit anything

Two rules, both learned the hard way on this project:

1. **Open the actual file at full resolution.** A thumbnail contact sheet is
   for spotting layout, not for clearing content. An image with an
   identifiable child's face was once passed as clean from a thumbnail and had
   to be pruned later.
2. **Reject identifiable private individuals**, most of all children. Crowds
   and distant figures are fine. A face in focus is not.

Also reject: NC or ND licences, press-agency photographs, and anything showing
a named public official (animating or re-captioning one is exactly the
impersonation this project rules out).

Accepted licences, enforced in the fetcher: Public Domain / CC0 / PDM,
CC BY, CC BY-SA, GODL-India.

## B-roll: `--media video` works, but Commons is the wrong source

The code path is finished and correct — `--media video` queries
`VIDEO_SOURCE_CATEGORIES`, filters to clips of 4–180s at 960×540 or better,
and saves them without transcoding. **The footage it finds is not usable.**

Measured, not assumed. A real run returned exactly four clips:

| Filed as | What it actually was |
|----------|----------------------|
| `ACTION_REQUIRED` | US bank lobby CCTV, Christmas tree, "Front Door", timestamped 12-10-2021 |
| `AMOUNT` | the same CCTV clip again |
| `DEADLINE` | ornate Viennese museum clock, portrait 1440×1920 |
| `SCHEME_NAME` | aerial flood-disaster water, near-featureless, watermarked |

All four were pruned. Each is *categorically* defensible and *contextually*
wrong, and the flood clip is worse than useless: disaster footage behind
"PM-KISAN installment announced" actively misinforms. Commons simply has very
little video, almost none of it Indian-government context, and a generic
category like `Videos of banks` returns whatever happens to exist.

**So: do not source b-roll from Commons.** If you want motion backgrounds, use
licensed stock (Pexels/Pixabay video, both permissive) or footage shot for
this project, drop the file into the right category directory, and hand-write
its sidecar with `media_type: "video"`. The catalogue, retrieval and
compositor all handle video already — only acquisition is the gap.

Stills carry the load regardless: they are plentiful, and Ken Burns gives them
motion. Spend b-roll only where movement genuinely says something — a hand
counting notes, a queue advancing, a crop being cut.

## How selection actually works

Three layers, each falling through to the next:

| Layer | What it does | Needs |
|-------|--------------|-------|
| `vector` | MiniLM embeddings in ChromaDB — matches *meaning* | model + built index |
| `fuzzy` | rapidfuzz over the sidecar JSON | nothing |
| `tags` | exact substring tag scoring | nothing |
| *(gradient)* | procedural background | nothing |

Why it matters that the vector layer is on top: the narration line *"eligible
farmer families in rural districts"* shares **no word** with an asset titled
*"Agriculture land around P.N.Palayam"*. Tag scoring cannot connect those.
The embedding scores it 0.51.

Why it matters that fuzzy is underneath: it needs no model and no index, so a
teammate who has never run `build_visual_index.py` still gets sensible
backgrounds. Nothing in this stack can stop a scene rendering.

Force the fallback to check it still works:

```bash
VISUAL_RAG_DISABLE=1 ../.venv/Scripts/python.exe scripts/query_visual_index.py "your query"
```

## Not in git

`assets/broll/library/` and `data/chroma/` are both gitignored. The library is
other people's photographs under their own licences and this repo should not
redistribute them; the index is derived data — rebuild it, don't sync it.

This means **every teammate builds their own library.** If a render looks
different on your machine, check `scripts/query_visual_index.py` before
assuming the compositor changed.
