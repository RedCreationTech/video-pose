from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class EncodedSnapshot:
    content: bytes
    timestamp_ms: float
    media_type: str = "image/jpeg"


def encode_jpeg(
    image: Any,
    *,
    timestamp_ms: float,
    quality: int = 80,
) -> EncodedSnapshot:
    if not 1 <= quality <= 100:
        raise ValueError("JPEG quality must be between 1 and 100")
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError(
            "JPEG snapshots require the optional video dependencies"
        ) from exc

    ok, encoded = cv2.imencode(
        ".jpg",
        image,
        [cv2.IMWRITE_JPEG_QUALITY, quality],
    )
    if not ok:
        raise ValueError("failed to encode camera snapshot")
    return EncodedSnapshot(
        content=encoded.tobytes(),
        timestamp_ms=timestamp_ms,
    )
