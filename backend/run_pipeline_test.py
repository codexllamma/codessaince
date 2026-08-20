import sys
import requests

BASE_URL = "http://127.0.0.1:8000"

print("[INFO] 1. Creating Job...")
r1 = requests.post(
    f"{BASE_URL}/api/jobs",
    json={
        "raw_extracted_text": (
            "Ministry of Agriculture: PM-KISAN 17th installment of Rs 2000."
            " Complete verification before 31-10-2026."
        ),
        "source_file_name": "pmkisan_notice.pdf",
        "target_languages": ["en"],
        "selected_voice_id": "en-IN-PrabhatNeural",
        "voice_speed_modifier": "+0%",
    },
    timeout=5,
)
job_id = r1.json()["job_id"]
print(f"[OK] Job created: {job_id}")

print(f"[INFO] 2. Extracting Facts for {job_id}...")
requests.post(f"{BASE_URL}/api/jobs/{job_id}/extract-facts", timeout=5)

print(f"[INFO] 3. Generating Master Scenes for {job_id}...")
requests.post(f"{BASE_URL}/api/jobs/{job_id}/generate-scenes", timeout=5)

print(f"[INFO] 4. Synthesizing Audio for {job_id}...")
r4 = requests.post(f"{BASE_URL}/api/jobs/{job_id}/synthesize", timeout=30)
if r4.status_code != 200:
  print(f"[ERROR] Synthesis failed: {r4.text}")
  sys.exit(1)
print("[OK] Audio synthesis complete.")

print(f"[INFO] 5. Officer Approving Job {job_id}...")
requests.post(
    f"{BASE_URL}/api/jobs/{job_id}/approve", json={"approved": True}, timeout=5
)

print(f"[INFO] 6. Rendering Final Video with MoviePy for {job_id}...")
r6 = requests.post(f"{BASE_URL}/api/jobs/{job_id}/render", timeout=120)
if r6.status_code != 200:
  print(f"[ERROR] Render failed: {r6.text}")
  sys.exit(1)

result = r6.json()
print(f"[SUCCESS] Final Video Rendered: {result['final_video_paths']}")