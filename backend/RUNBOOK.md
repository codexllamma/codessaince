# End-to-end pipeline runbook

How to check out the project on a fresh machine and drive the whole pipeline
(job → facts → scenes → translation → audio → video) with logs you can read.

Everything below was run on Windows 11 / Python 3.12 against commit `f8f645d`.

---

## 1. Prerequisites

| Component | Needed for | Check |
|---|---|---|
| Python 3.12 | everything | `py -0` lists `3.12` |
| ffmpeg | encoding the MP4 | `ffmpeg -version` |
| Internet | edge-tts voices and Google Translate | — |

There is **no Ollama, GPU, or CUDA requirement**. Fact extraction currently
returns fixed sample facts (`server.py`, `/extract-facts`), so nothing calls an
LLM. PDFs are not parsed either — a job is created from raw text.

### Install Python 3.12

```powershell
winget install Python.Python.3.12
```

### Install ffmpeg

```powershell
winget install Gyan.FFmpeg
```

Open a **new terminal** afterwards so the updated PATH is picked up, then:

```powershell
ffmpeg -version
ffmpeg -hide_banner -encoders | Select-String nvenc
```

If `h264_nvenc` is listed, rendering may use the GPU. If it is missing, or your
NVIDIA driver is older than the build requires, the compositor falls back to
`libx264` automatically and logs `NVENC encode failed; using libx264`. Output is
identical, just slower.

---

## 2. Clone and set up

```powershell
git clone https://github.com/codexllamma/codessaince.git
cd codessaince

py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -r requirements.lock
```

`requirements.lock` is the authority. It includes `uharfbuzz` and `freetype-py`,
which are **required for correct Indic text** — see section 6.

---

## 3. Verify fonts and shaping before rendering anything

This is the cheapest check and catches the failure that is hardest to spot later.

```powershell
python compositor/typography.py --selftest
```

Writes `assets/fonts/_selftest.png`. Open it and confirm:

- one line per language, all six legible, **no empty boxes** (tofu)
- the last line reads `shaping: HarfBuzz+FreeType`

If it says `shaping: Pillow (NO complex shaping)`, stop and fix the install.
Rendering will still "work", but Hindi, Tamil, Telugu, Bengali and Marathi will
come out **misspelt** — vowel signs land on the wrong side of their consonant
("किसान" renders as "कसिान"). It does not look broken, so it will pass a casual
glance and reach the demo.

Per-language cards through the real compositor:

```powershell
python test_font.py
```

Writes `static/font_tests/test_card_<lang>.png` for all six languages.

Unit tests, including shaping regressions:

```powershell
python -m pytest tests/ -q
```

Expect `36 passed`.

---

## 4. Start the API

Keep this terminal open; it is your server log.

```powershell
mkdir logs -Force
python -m uvicorn server:app --host 127.0.0.1 --port 8000 --log-level info
```

To keep a log file as well:

```powershell
python -m uvicorn server:app --host 127.0.0.1 --port 8000 --log-level info 2>&1 | Tee-Object -FilePath logs\server.log
```

In a second terminal:

```powershell
curl http://127.0.0.1:8000/health
# {"status":"HEALTHY"}
```

Interactive API docs: <http://127.0.0.1:8000/docs>

---

## 5. Run the pipeline

### Quick check — English only (~2 minutes)

```powershell
python run_pipeline_test.py
```

```
[INFO] 1. Creating Job...
[OK] Job created: job_001
[INFO] 2. Extracting Facts for job_001...
[INFO] 3. Generating Master Scenes for job_001...
[INFO] 4. Synthesizing Audio for job_001...
[OK] Audio synthesis complete.
[INFO] 5. Officer Approving Job job_001...
[INFO] 6. Rendering Final Video with MoviePy for job_001...
[SUCCESS] Final Video Rendered: {'en': '/static/videos/job_001_final_en.mp4'}
```

### Full check — four languages (~10 minutes on CPU)

```powershell
python test_multilingual.py
```

Renders `en`, `hi`, `ta`, `te`. **Roughly 2-3 minutes per language** at 1080p
without NVENC, so be patient — the server log is the real progress indicator.

### Step through it by hand

```powershell
$body = @{
  raw_extracted_text = "Ministry of Agriculture: PM-KISAN 17th installment of Rs 2000. Complete verification before 31-10-2026."
  source_file_name   = "notice.pdf"
  target_languages   = @("en","hi")
  selected_voice_id  = "en-IN-PrabhatNeural"
  voice_speed_modifier = "+0%"
} | ConvertTo-Json

$job = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/jobs -Body $body -ContentType "application/json"
$id = $job.job_id

Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/jobs/$id/extract-facts"
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/jobs/$id/generate-scenes"
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/jobs/$id/synthesize"
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/jobs/$id/approve" -Body '{"approved":true}' -ContentType "application/json"
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/jobs/$id/render" -TimeoutSec 1800
```

Rendering before approving returns an error — the human-in-the-loop gate
(README §3.5) is enforced server-side, so that failure is the correct behaviour.

### Single-language card preview, no rendering

```
http://127.0.0.1:8000/api/test/preview-card/hi
```

Returns a PNG straight from the compositor. Fastest way to eyeball typography
for one language.

---

## 6. Where the output and logs live

| Path | Contents |
|---|---|
| `static/videos/<job>_final_<lang>.mp4` | final videos |
| `static/audio/` | per-scene edge-tts audio |
| `jobs/<job_id>.json` | full job state — facts, scenes, subtitles, telemetry |
| `assets/fonts/_selftest.png` | font and shaping check |
| `static/font_tests/` | per-language cards |
| `logs/server.log` | server log, if you used `Tee-Object` |

Inspect a finished video:

```powershell
ffprobe -v error -show_entries stream=codec_name,codec_type,pix_fmt,width,height -of default=noprint_wrappers=1 static\videos\job_002_final_hi.mp4
ffprobe -v error -show_entries format=duration -of csv=p=0 static\videos\job_002_final_hi.mp4
```

Expected: one `h264` / `yuv420p` / `1920x1080` video stream, one `aac` audio
stream, duration in the 30-45s range.

Pull a frame out to check the text:

```powershell
ffmpeg -y -ss 4.0 -i static\videos\job_002_final_hi.mp4 -update 1 -vframes 1 frame_hi.png
```

---

## 6b. Optional: the split-screen presenter

Off by default. `assets/avatars/manifest.json` has an empty `avatars` list, so
rendering uses the normal full-width layout.

To try it, copy the block under `_example_entry` into `avatars`. A placeholder
clip (`placeholder_m01.mp4`) ships in that folder, so this works immediately:

```powershell
python scripts\render_fixture_demo.py job libx264
```

The presenter appears on the left with an on-screen "AI-GENERATED PRESENTER"
label, the fact card moves to the right panel, and captions stay full width.

To use a real clip, drop the MP4 in `assets/avatars/` and add an entry. No code
changes. Generating one with LivePortrait, which ships its own sample portraits
and driving videos:

```bash
git clone https://github.com/KwaiVGI/LivePortrait && cd LivePortrait
python inference.py -s assets/examples/source/s9.jpg -d assets/examples/driving/d0.mp4
```

Trim the result to a clean 6-12s loop and copy it across.

**Cost:** the loop is decoded once per job, not per frame — about 1.4s to load
and 137MB cached, adding roughly 1ms (3%) per rendered frame.

**Two rules enforced in code, not by review:**

- `source` must be `synthetic`, `licensed_stock` or `consented_performer`.
  The registry refuses to load anything else. Animating a real, identifiable
  official's likeness is a deepfake of a public figure in their official
  capacity — filming a consenting teammate is the fastest safe option and is
  what `consented_performer` is for.
- `disclosure_label` must be non-empty. There is no code path that renders an
  unlabelled synthetic presenter.

---

## 7. Troubleshooting

**Indic text looks subtly wrong / vowel marks on the wrong side**
`uharfbuzz` or `freetype-py` is missing. Confirm with the selftest footer, then
`pip install -r requirements.lock`.

**Empty boxes instead of letters**
A font file is missing from `assets/fonts/`. All six ship in the repo, so this
usually means an incomplete clone (they are binary files).

**`ImportError` on `uvicorn server:app`**
Run from the repo root with the venv active. `server.py` imports `compositor/`
and `models/` as top-level packages.

**Render is very slow**
Expected without NVENC. ~2-3 min per language at 1080p. Check the server log
for `NVENC encode failed; using libx264` to confirm which path is in use.

**Client times out but the server keeps going**
The render continues server-side; watch `static/videos/` for new files. The
scripts allow 1800s, but a hand-rolled request may not.

**`edge-tts` or translation errors**
Both need internet. edge-tts talks to a Microsoft endpoint whose voice list
changes without notice; translation uses Google Translate and can rate-limit.

---

## 8. What is real and what is stubbed

Worth knowing before judging output quality:

- **Stubbed** — fact extraction returns fixed sample facts; no PDF/OCR ingestion;
  no NLI entailment check.
- **Real** — scene generation, entity-locked translation, edge-tts audio with
  word-level timestamps, and the full compositor: Ken Burns motion, 5-layer
  canvas, karaoke captions, HarfBuzz shaping, yuv420p encode.
- **Placeholder visuals** — no licensed B-roll is bundled, so every scene uses
  the procedural mesh-gradient background (README §10.2 fallback). Scene
  generation does request `video_loop` assets; the files simply are not there
  yet and the compositor degrades to the gradient rather than failing.
