import asyncio
from pathlib import Path
import edge_tts
import soundfile as sf

# Tamil Neural Voices available in edge-tts:
# 1. 'ta-IN-ValluvarNeural' (Male, India)
# 2. 'ta-IN-PallaviNeural'  (Female, India)
VOICE = "ta-IN-ValluvarNeural"
OUTPUT_FILE = Path("static/audio/test_tamil.mp3")

SAMPLE_TAMIL_TEXT = (
    "வேளாண்மை மற்றும் விவசாயிகள் நல அமைச்சகம் வெளியிட்டுள்ள அதிகாரப்பூர்வ"
    " அறிவிப்பு. பிஎம்-கிசான் திட்டத்தின் 17வது தவணை இரண்டு ஆயிரம் ரூபாய் உங்கள்"
    " வங்கிக் கணக்கில் நேரடியாக வரவு வைக்கப்படும்."
)


async def generate_tamil_audio():
  OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

  print(f"[INFO] Synthesizing Tamil speech using {VOICE}...")
  communicate = edge_tts.Communicate(
      text=SAMPLE_TAMIL_TEXT, voice=VOICE, rate="+0%"
  )

  word_boundaries = []
  with open(OUTPUT_FILE, "wb") as f:
    async for chunk in communicate.stream():
      if chunk["type"] == "audio":
        f.write(chunk["data"])
      elif chunk["type"] == "WordBoundary":
        start_sec = chunk["offset"] / 10_000_000.0
        duration_sec = chunk["duration"] / 10_000_000.0
        word_boundaries.append((chunk["text"], start_sec, duration_sec))

  info = sf.info(str(OUTPUT_FILE))
  print(f"[OK] Generated: {OUTPUT_FILE}")
  print(f"[OK] Total Duration: {round(info.duration, 2)} seconds")
  print(f"[OK] Captured {len(word_boundaries)} word timestamp markers")
  print("\n[SAMPLE TIMESTAMPS]")
  for text, start, dur in word_boundaries[:5]:
    print(f" - {text}: start={start:.2f}s, duration={dur:.2f}s")


if __name__ == "__main__":
  asyncio.run(generate_tamil_audio())