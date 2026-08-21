import os
# Prevent Windows/PyTorch duplicate library crash
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import sys
import subprocess
import cv2
import torch
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
WAV2LIP_DIR = BASE_DIR / "services" / "wav2lip"

# ==========================
# CONFIG & PATHS
# ==========================
INPUT_VIDEO = str(BASE_DIR / "assets" / "avatars" / "indic_official_m02.mp4")
INPUT_AUDIO = str(BASE_DIR / "static" / "audio" / "test_audio.wav")
OUTPUT_VIDEO = str(BASE_DIR / "static" / "videos" / "hd_lipsync_output_punjabi_male.mp4")

# Replaced AVI temp variables with a single MP4 temp since FFmpeg handles it flawlessly
TEMP_RAW_MP4 = str(BASE_DIR / "static" / "temp_raw_w2l.mp4")

def run_video_wav2lip_hd(video_path: str, audio_path: str, out_path: str):
    os.makedirs(Path(out_path).parent, exist_ok=True)

    # -------------------------------------------------------------
    # PASS 1: Wav2Lip Multi-Frame Dynamic Tracking (CUDA)
    # -------------------------------------------------------------
    print("[1/2] Running Wav2Lip across dynamic video frames (CUDA)...")
    
    cmd = [
        sys.executable,
        str(WAV2LIP_DIR / "inference.py"),
        "--checkpoint_path", str(WAV2LIP_DIR / "checkpoints" / "wav2lip_gan.pth"),
        "--face", video_path,
        "--audio", audio_path,
        "--outfile", TEMP_RAW_MP4,
        "--wav2lip_batch_size", "8",  
        "--face_det_batch_size", "4", 
        "--nosmooth"
    ]
    subprocess.run(cmd, check=True)

    # -------------------------------------------------------------
    # PASS 2: Full-Frame GFPGAN Restoration + FFmpeg Direct Pipe
    # -------------------------------------------------------------
    print("\n[2/2] Restoring face clarity & encoding HD output (CUDA)...")
    from gfpgan import GFPGANer
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    restorer = GFPGANer(
        model_path=str(WAV2LIP_DIR / "gfpgan" / "weights" / "GFPGANv1.4.pth"),
        upscale=1,
        arch="clean",
        channel_multiplier=2,
        bg_upsampler=None,
        device=device
    )

    cap = cv2.VideoCapture(TEMP_RAW_MP4)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    # Spawn FFmpeg directly - taking input from stdin memory pipe
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{w}x{h}",
        "-pix_fmt", "bgr24",
        "-r", str(fps),
        "-i", "-",               # Input stream 1: Memory Pipe
        "-i", audio_path,        # Input stream 2: Clean Audio
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "17",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        out_path
    ]
    proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    frame_count = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # GFPGAN Enhancement
        _, _, restored_frame = restorer.enhance(
            frame, 
            has_aligned=False, 
            only_center_face=True, 
            paste_back=True
        )
        
        # Write bytes directly to FFmpeg
        proc.stdin.write(restored_frame.tobytes())
        frame_count += 1

    cap.release()
    proc.stdin.close()
    proc.wait()
    print(f"      -> Enhanced and encoded {frame_count} frames successfully.")

    # -------------------------------------------------------------
    # CLEANUP
    # -------------------------------------------------------------
    if os.path.exists(TEMP_RAW_MP4):
        os.remove(TEMP_RAW_MP4)

    print(f"\n[SUCCESS] Final HD presenter video saved at: {out_path}")

if __name__ == "__main__":
    # Safety Checks
    if not os.path.exists(INPUT_VIDEO):
        print(f"Error: Missing avatar video at: {INPUT_VIDEO}")
        sys.exit(1)
    if not os.path.exists(INPUT_AUDIO):
        print(f"Error: Missing audio file at: {INPUT_AUDIO}")
        sys.exit(1)

    run_video_wav2lip_hd(INPUT_VIDEO, INPUT_AUDIO, OUTPUT_VIDEO)