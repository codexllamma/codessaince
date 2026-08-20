import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
input_video = str(BASE_DIR / "assets" / "avatars" / "male_raw.mp4")
output_video = str(BASE_DIR / "assets" / "avatars" / "indic_official_m01.mp4")

print(f"Reading: {input_video}")
print("Creating seamless ping-pong loop for the male anchor...")

ffmpeg_cmd = [
    "ffmpeg", "-y", 
    "-i", input_video,
    "-filter_complex", "[0:v]reverse[r];[0:v][r]concat=n=2:v=1:a=0[v]",
    "-map", "[v]", 
    "-c:v", "libx264", 
    "-preset", "fast", 
    "-crf", "17", 
    "-pix_fmt", "yuv420p", 
    output_video
]

subprocess.run(ffmpeg_cmd, check=True)
print(f"\n[SUCCESS] Seamless loop saved to: {output_video}")