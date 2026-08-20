"""Resolves a real, NVENC-capable ffmpeg binary and wires it into MoviePy.

MoviePy reads the FFMPEG_BINARY env var (moviepy.config); if unset it falls
back to imageio-ffmpeg's bundled binary, which is a generic build with no
guaranteed NVENC support. This must run before `import moviepy`.
"""

from __future__ import annotations

import glob
import logging
import os
import shutil

logger = logging.getLogger(__name__)

_WINGET_GLOB = os.path.expandvars(
    r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg_*\ffmpeg-*-full_build\bin\ffmpeg.exe"
)


def resolve_ffmpeg_binary() -> str:
    """Best real ffmpeg found: PATH, then the known winget install location,
    then whatever imageio-ffmpeg bundles (last resort, no NVENC guarantee)."""
    on_path = shutil.which("ffmpeg")
    if on_path:
        return on_path

    matches = sorted(glob.glob(_WINGET_GLOB))
    if matches:
        return matches[-1]

    import imageio_ffmpeg

    logger.warning("No system ffmpeg found; falling back to imageio-ffmpeg's bundled binary (NVENC not guaranteed).")
    return imageio_ffmpeg.get_ffmpeg_exe()


def ensure_ffmpeg_binary_env() -> str:
    path = resolve_ffmpeg_binary()
    os.environ["FFMPEG_BINARY"] = path
    return path
