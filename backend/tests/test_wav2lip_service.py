from pathlib import Path
import numpy as np
import pytest
import soundfile as sf

from services.wav2lip_service import (
    get_device,
    get_face_detector,
    get_wav2lip_model,
    generate_lip_sync,
)


@pytest.fixture
def dummy_audio_wav(tmp_path: Path) -> Path:
    audio_file = tmp_path / "test_synth.wav"
    sr = 16000
    duration_sec = 1.5
    t = np.linspace(0, duration_sec, int(sr * duration_sec))
    sine_wave = (0.25 * np.sin(2 * np.pi * 300 * t)).astype(np.float32)
    sf.write(str(audio_file), sine_wave, sr)
    return audio_file


def test_device_selection():
    dev = get_device()
    assert dev in ("cuda", "cpu")


def test_wav2lip_model_loading():
    model = get_wav2lip_model()
    assert model is not None


def test_face_detector_loading():
    detector = get_face_detector()
    assert detector is not None


def test_generate_lip_sync_succeeds(dummy_audio_wav: Path, tmp_path: Path):
    anchor_img = Path("assets/avatars/anchor_source.png")
    if not anchor_img.exists():
        pytest.skip("anchor_source.png not present in assets/avatars")

    out_mp4 = tmp_path / "out_lipsync.mp4"
    result = generate_lip_sync(
        face_image_path=anchor_img,
        audio_path=dummy_audio_wav,
        output_path=out_mp4,
        batch_size=32,
        enhance_face=False,  # fast test mode
    )

    assert Path(result).exists()
    assert out_mp4.exists()
    assert out_mp4.stat().st_size > 1000
