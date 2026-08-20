import sys
import requests

BASE_URL = "http://127.0.0.1:8000"

print("[INFO] 1. Creating 4-Language Job (en, hi, ta, te)...")
r1 = requests.post(
    f"{BASE_URL}/api/jobs",
    json={
        "raw_extracted_text": (
            "Ministry of Agriculture notification: PM-KISAN 17th installment of"
            " Rs 2000 is released. Complete verification before 31-10-2026."
        ),
        "source_file_name": "pmkisan_notice.pdf",
        "target_languages": ["en", "hi", "ta", "te"],
        "selected_voice_id": "en-IN-PrabhatNeural",
        "voice_speed_modifier": "+0%",
    },
    timeout=10,
)
if r1.status_code != 201:
  print(f"[ERROR] Job creation failed: {r1.text}")
  sys.exit(1)

job_id = r1.json()["job_id"]
print(f"[OK] Job created: {job_id}")

print(f"[INFO] 2. Extracting Facts for {job_id}...")
requests.post(f"{BASE_URL}/api/jobs/{job_id}/extract-facts", timeout=10)
print("[OK] Facts extracted.")

print(
    f"[INFO] 3. Batch Translating & Localizing Scenes for en, hi, ta, te on"
    f" {job_id}..."
)
r3 = requests.post(f"{BASE_URL}/api/jobs/{job_id}/generate-scenes", timeout=45)
if r3.status_code != 200:
  print(f"[ERROR] Scene generation failed: {r3.text}")
  sys.exit(1)

data = r3.json()
print(f"[OK] Master EN scenes: {len(data['master_scenes_en'])}")
print(f"[OK] Localized languages: {list(data['localized_scenes'].keys())}")

print(f"[INFO] 4. Synthesizing Audio (Edge-TTS) for all 4 languages...")
r4 = requests.post(f"{BASE_URL}/api/jobs/{job_id}/synthesize", timeout=90)
if r4.status_code != 200:
  print(f"[ERROR] Audio synthesis failed: {r4.text}")
  sys.exit(1)
print("[OK] Audio synthesis complete.")

print(f"[INFO] 5. Officer Approving Job {job_id}...")
requests.post(
    f"{BASE_URL}/api/jobs/{job_id}/approve", json={"approved": True}, timeout=10
)
print("[OK] Approved.")

print(f"[INFO] 6. Rendering Final MP4 Videos...")
# CPU (libx264) rendering costs roughly 2-3 minutes per language at 1080p,
# so four languages needs well over the 300s this used to allow. NVENC would
# be far faster but is not available on every machine.
r6 = requests.post(f"{BASE_URL}/api/jobs/{job_id}/render", timeout=1800)
if r6.status_code != 200:
  print(f"[ERROR] Video render failed: {r6.text}")
  sys.exit(1)

result = r6.json()
print(f"\n[SUCCESS] Rendered Final Deliverables:")
for lang, path in result["final_video_paths"].items():
  print(f" - [{lang.upper()}]: {path}")