"""Downloads weights for Wav2Lip-GAN, S3FD Face Detector, and GFPGANv1.4 with multiple fallback mirrors."""

import os
import sys
from pathlib import Path
import requests
from tqdm import tqdm

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent / "services" / "wav2lip"

CHECKPOINTS_DIR = BASE_DIR / "checkpoints"
SFD_DIR = BASE_DIR / "face_detection" / "detection" / "sfd"
GFPGAN_DIR = BASE_DIR / "gfpgan" / "weights"

CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)
SFD_DIR.mkdir(parents=True, exist_ok=True)
GFPGAN_DIR.mkdir(parents=True, exist_ok=True)

WEIGHT_FILES = [
    {
        "name": "Wav2Lip-GAN Checkpoint",
        "target": CHECKPOINTS_DIR / "wav2lip_gan.pth",
        "min_bytes": 400 * 1024 * 1024,  # ~435 MB
        "urls": [
            "https://github.com/justinjohn0306/Wav2Lip/releases/download/models/wav2lip_gan.pth",
            "https://github.com/anothermartz/Easy-Wav2Lip/releases/download/Prerequesits/Wav2Lip_GAN.pth",
            "https://huggingface.co/numz/wav2lip_studio/resolve/main/checkpoints/wav2lip_gan.pth",
            "https://huggingface.co/Nekochu/Wav2Lip/resolve/main/wav2lip_gan.pth",
        ],
    },
    {
        "name": "S3FD Face Detector",
        "target": SFD_DIR / "s3fd-619a316812.pth",
        "min_bytes": 80 * 1024 * 1024,  # ~89 MB
        "urls": [
            "https://www.adrianbulat.com/downloads/python-fan/s3fd-619a316812.pth",
            "https://github.com/justinjohn0306/Wav2Lip/releases/download/models/s3fd.pth",
            "https://huggingface.co/numz/wav2lip_studio/resolve/main/face_detection/detection/sfd/s3fd.pth",
        ],
    },
    {
        "name": "GFPGAN v1.4 Face Enhancer",
        "target": GFPGAN_DIR / "GFPGANv1.4.pth",
        "min_bytes": 300 * 1024 * 1024,  # ~348 MB
        "urls": [
            "https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.4.pth",
            "https://huggingface.co/public-data/GFPGAN/resolve/main/GFPGANv1.4.pth",
        ],
    },
]


def download_file(name: str, target: Path, urls: list[str], min_bytes: int):
    if target.exists() and target.stat().st_size >= min_bytes:
        print(f"[OK] {name} already exists ({target.stat().st_size / (1024*1024):.1f} MB): {target}")
        return True

    print(f"\n[DOWNLOAD] Fetching {name} -> {target}...")
    for url in urls:
        print(f"  Trying mirror: {url}")
        try:
            resp = requests.get(
                url,
                stream=True,
                timeout=45,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                allow_redirects=True,
            )
            if resp.status_code != 200:
                print(f"  HTTP Status: {resp.status_code}")
                continue

            total_size = int(resp.headers.get("content-length", 0))
            temp_target = target.with_suffix(".tmp")

            with open(temp_target, "wb") as f, tqdm(
                desc=target.name,
                total=total_size,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
            ) as bar:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
                        bar.update(len(chunk))

            if temp_target.stat().st_size >= min_bytes:
                if target.exists():
                    target.unlink()
                temp_target.rename(target)
                print(f"[OK] Successfully downloaded {name} ({target.stat().st_size / (1024*1024):.1f} MB)")
                return True
            else:
                print(f"  Downloaded size too small ({temp_target.stat().st_size} bytes)")
                if temp_target.exists():
                    temp_target.unlink()
        except Exception as e:
            print(f"  Error downloading from {url}: {e}")

    print(f"[FAIL] Failed to download {name} from all mirrors!")
    return False


if __name__ == "__main__":
    success = True
    for item in WEIGHT_FILES:
        res = download_file(item["name"], item["target"], item["urls"], item["min_bytes"])
        if not res:
            success = False

    if success:
        print("\nAll weights verified and downloaded successfully!")
        sys.exit(0)
    else:
        print("\nSome weights failed to download.")
        sys.exit(1)
