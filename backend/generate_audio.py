import os
import asyncio
import subprocess
from pathlib import Path
import sys

try:
    import edge_tts
except ImportError:
    print("Installing edge-tts...")
    subprocess.run([sys.executable, "-m", "pip", "install", "edge-tts"], check=True)
    import edge_tts

async def setup_test_audio():
    base_dir = Path(__file__).resolve().parent
    audio_dir = base_dir / "static" / "audio"
    
    # 1. Guarantee the directory exists
    audio_dir.mkdir(parents=True, exist_ok=True)
    
    mp3_path = audio_dir / "temp.mp3"
    wav_path = audio_dir / "test_audio.wav"
    
    print("[1/3] Generating Hindi TTS via Edge-TTS...")
    tts = edge_tts.Communicate("नमस्कार, यह दूरदर्शन समाचार का आधिकारिक बुलेटिन है। हम जल्द ही शुरू करेंगे।", "hi-IN-MadhurNeural")
    await tts.save(str(mp3_path))
    
    print("[2/3] Converting to 16kHz WAV format for Wav2Lip...")
    try:
        subprocess.run([
            "ffmpeg", "-y", "-i", str(mp3_path), 
            "-ar", "16000", "-ac", "1", 
            str(wav_path)
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        print("\nERROR: FFmpeg is not installed or not in your system PATH.")
        print("Please download FFmpeg (https://github.com/BtbN/FFmpeg-Builds/releases)")
        print("and extract ffmpeg.exe into your backend/ directory.")
        sys.exit(1)
        
    if mp3_path.exists():
        mp3_path.unlink()
        
    print(f"[3/3] Success! Audio ready at: {wav_path}")

if __name__ == "__main__":
    asyncio.run(setup_test_audio())