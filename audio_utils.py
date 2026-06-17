"""Утилиты для работы с аудиофайлами."""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


def extract_audio_from_webm(webm_bytes: bytes, original_name: str) -> tuple[bytes, str]:
    """Извлекает аудиодорожку из webm и кодирует её в MP3 (128 kbps).

    Returns (mp3_bytes, mp3_filename).
    Raises RuntimeError, если ffmpeg недоступен или конвертация упала.
    """
    mp3_name = Path(original_name).stem + ".mp3"

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / "input.webm"
        output_path = Path(tmpdir) / "output.mp3"
        input_path.write_bytes(webm_bytes)

        try:
            result = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i", str(input_path),
                    "-vn",
                    "-acodec", "libmp3lame",
                    "-ab", "128k",
                    str(output_path),
                ],
                capture_output=True,
                check=False,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "ffmpeg не найден. Установите ffmpeg (например, `brew install ffmpeg`)."
            ) from exc

        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"Не удалось извлечь аудио из webm: {stderr}")

        return output_path.read_bytes(), mp3_name
