import importlib
import sys

REQUIRED_PYTHON = (3, 12)
CORE_PACKAGES = [
    "fastapi",
    "uvicorn",
    "pydantic",
    "edge_tts",
    "moviepy",
    "PIL",  # Pillow
    "fitz",  # PyMuPDF
    "deep_translator",
]


def run_enforced_check():
  print("[INFO] Initializing environment validation...")

  # 1. Enforce Exact Python Version
  current_version = sys.version_info[:2]
  if current_version != REQUIRED_PYTHON:
    print(
        f"[ERROR] Python version mismatch: Detected {current_version[0]}.{current_version[1]}, "
        f"required {REQUIRED_PYTHON[0]}.{REQUIRED_PYTHON[1]}"
    )
    sys.exit(1)
  print(f"[OK] Python version verified: {sys.version.split()[0]}")

  # 2. Verify Package Imports
  failed = []
  for pkg in CORE_PACKAGES:
    try:
      importlib.import_module(pkg)
      print(f"[OK] Package loaded: {pkg}")
    except ImportError as e:
      print(f"[ERROR] Failed to load {pkg}: {e}")
      failed.append(pkg)

  if failed:
    print("\n[ACTION REQUIRED] Run: pip install -r requirements.txt")
    sys.exit(1)

  print(
      "\n[SUCCESS] Environment validation passed. Core pipeline ready for development."
  )


if __name__ == "__main__":
  run_enforced_check()