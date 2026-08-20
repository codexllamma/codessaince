from contextlib import contextmanager
import itertools
from pathlib import Path
import sys
import threading
import time
import requests

BASE_URL = "http://127.0.0.1:8000"

# Extended Timeout Configuration (in seconds)
TIMEOUT_CONFIG = {
    "create_job": 20,
    "extract_facts": 30,
    "generate_scenes": 120,
    "synthesize_audio": 300,
    "approval_gate": 20,
    "render_video": 3600,  # Up to 60 mins for 4-language CPU encoding
}


@contextmanager
def active_spinner(task_name: str):
  """Displays an animated spinner with elapsed time in the terminal."""
  stop_event = threading.Event()
  start_time = time.time()

  def _animate():
    spinner_frames = itertools.cycle(
        ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    )
    while not stop_event.is_set():
      frame = next(spinner_frames)
      elapsed_sec = int(time.time() - start_time)
      mins, secs = divmod(elapsed_sec, 60)
      sys.stdout.write(
          f"\r  [\033[36m{frame}\033[0m] {task_name} (Elapsed: {mins:02d}:{secs:02d})..."
      )
      sys.stdout.flush()
      time.sleep(0.08)

  thread = threading.Thread(target=_animate, daemon=True)
  thread.start()

  try:
    yield
  finally:
    stop_event.set()
    thread.join()
    # Clear line and reset carriage
    sys.stdout.write(f"\r{' ' * 90}\r")
    sys.stdout.flush()


def step_1_create_job() -> str:
  print("\n--- [STEP 1] Initializing Notice Job ---")
  payload = {
      "raw_extracted_text": (
          "Ministry of Agriculture: PM-KISAN 17th installment of Rs 2000."
          " Complete verification before 31-10-2026."
      ),
      "source_file_name": "pmkisan_notice.pdf",
      "target_languages": ["en", "hi", "ta", "te"],
      "selected_voice_id": "en-IN-PrabhatNeural",
      "voice_speed_modifier": "+0%",
  }

  with active_spinner("Sending job registration payload"):
    r = requests.post(
        f"{BASE_URL}/api/jobs",
        json=payload,
        timeout=TIMEOUT_CONFIG["create_job"],
    )

  assert (
      r.status_code == 201
  ), f"Failed to create job (HTTP {r.status_code}): {r.text}"
  job_id = r.json()["job_id"]
  print(f"  \033[32m✔\033[0m Job Initialized: {job_id}")
  return job_id


def step_2_extract_facts(job_id: str):
  print("\n--- [STEP 2] Fact Extraction & Grounding ---")
  with active_spinner("Isolating entity pairs and values"):
    r = requests.post(
        f"{BASE_URL}/api/jobs/{job_id}/extract-facts",
        timeout=TIMEOUT_CONFIG["extract_facts"],
    )

  assert (
      r.status_code == 200
  ), f"Fact extraction failed (HTTP {r.status_code}): {r.text}"
  facts = r.json().get("extracted_facts", [])
  print(f"  \033[32m✔\033[0m Extracted {len(facts)} facts:")
  for f in facts:
    print(f"     • {f['category']}: {f['normalized_value']}")


def step_3_generate_scenes(job_id: str):
  print("\n--- [STEP 3] Scene Generation & Multilingual Translation ---")
  with active_spinner("Translating scene scripts to [hi, ta, te] via Google"):
    r = requests.post(
        f"{BASE_URL}/api/jobs/{job_id}/generate-scenes",
        timeout=TIMEOUT_CONFIG["generate_scenes"],
    )

  assert (
      r.status_code == 200
  ), f"Scene generation failed (HTTP {r.status_code}): {r.text}"
  data = r.json()
  master_scenes = data.get("master_scenes_en", [])
  loc_scenes = data.get("localized_scenes", {})
  print(f"  \033[32m✔\033[0m Generated {len(master_scenes)} Master (EN) Scenes")
  print(
      f"  \033[32m✔\033[0m Localized Sets Generated: {list(loc_scenes.keys())}"
  )


def step_4_synthesize_audio(job_id: str):
  print("\n--- [STEP 4] Edge-TTS Synthesis & Word Timestamps ---")
  start = time.time()

  with active_spinner(
      "Synthesizing audio for 4 languages across all scenes (Edge-TTS)"
  ):
    r = requests.post(
        f"{BASE_URL}/api/jobs/{job_id}/synthesize",
        timeout=TIMEOUT_CONFIG["synthesize_audio"],
    )

  assert (
      r.status_code == 200
  ), f"Audio synthesis failed (HTTP {r.status_code}): {r.text}"
  elapsed = round(time.time() - start, 2)
  data = r.json()
  en_s1 = data["master_scenes_en"][0]

  print(f"  \033[32m✔\033[0m Multilingual audio generated in {elapsed}s")
  print(f"     • S1 Audio Path: {en_s1['audio_path']}")
  print(f"     • S1 Duration: {en_s1['scene_duration_sec']}s")


def step_5_approval_gate(job_id: str):
  print("\n--- [STEP 5] Human-in-the-Loop Approval Gate ---")

  # 5a. Verify unapproved render fails as expected
  with active_spinner("Validating guardrail (attempting unapproved render)"):
    r_unapproved = requests.post(
        f"{BASE_URL}/api/jobs/{job_id}/render",
        timeout=TIMEOUT_CONFIG["approval_gate"],
    )

  assert r_unapproved.status_code == 400, (
      "Guardrail Error: Unapproved render was allowed! Expected HTTP 400,"
      f" received HTTP {r_unapproved.status_code}"
  )
  print(
      "  \033[32m✔\033[0m Unapproved render attempt blocked correctly (HTTP"
      " 400)"
  )

  # 5b. Grant officer approval
  with active_spinner("Submitting officer approval signature"):
    r_approve = requests.post(
        f"{BASE_URL}/api/jobs/{job_id}/approve",
        json={"approved": True},
        timeout=TIMEOUT_CONFIG["approval_gate"],
    )

  assert (
      r_approve.status_code == 200
  ), f"Approval failed (HTTP {r_approve.status_code}): {r_approve.text}"
  print("  \033[32m✔\033[0m Officer Approval Granted (Status: APPROVED)")


def step_6_render_video(job_id: str):
  print("\n--- [STEP 6] Compositing & Video Encoding (MoviePy / FFmpeg) ---")
  start = time.time()

  with active_spinner(
      "Rendering final MP4 deliverables (Typography + Presenter + Subtitles)"
  ):
    r = requests.post(
        f"{BASE_URL}/api/jobs/{job_id}/render",
        timeout=TIMEOUT_CONFIG["render_video"],
    )

  assert (
      r.status_code == 200
  ), f"Render failed (HTTP {r.status_code}): {r.text}"
  elapsed = round(time.time() - start, 2)
  data = r.json()

  print(
      f"  \033[32m✔\033[0m All video deliverables rendered successfully in"
      f" {elapsed}s:"
  )
  for lang, vpath in data.get("final_video_paths", {}).items():
    print(f"     • [{lang.upper()}]: {vpath}")


if __name__ == "__main__":
  try:
    jid = step_1_create_job()
    step_2_extract_facts(jid)
    step_3_generate_scenes(jid)
    step_4_synthesize_audio(jid)
    step_5_approval_gate(jid)
    step_6_render_video(jid)
    print("\n\033[32m[SUCCESS]\033[0m Entire end-to-end pipeline validated.")
  except AssertionError as ae:
    print(f"\n\033[31m[FAILED]\033[0m Stage Failure: {ae}")
    sys.exit(1)
  except requests.exceptions.Timeout:
    print("\n\033[31m[TIMEOUT]\033[0m Request exceeded configured timeout limit.")
    sys.exit(1)
  except Exception as ex:
    print(f"\n\033[31m[ERROR]\033[0m Unexpected failure: {ex}")
    sys.exit(1)