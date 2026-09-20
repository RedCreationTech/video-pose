from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class VideoProbe:
    width: int
    height: int
    fps: float
    duration_s: float
    codec: str


def _parse_rate(value: str) -> float:
    if "/" not in value:
        return float(value)
    numerator, denominator = value.split("/", 1)
    denominator_value = float(denominator)
    return float(numerator) / denominator_value if denominator_value else 0.0


def probe_video(path: str | Path) -> VideoProbe:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,avg_frame_rate,codec_name:format=duration",
        "-of",
        "json",
        str(path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=True)
    payload = json.loads(completed.stdout)
    if not payload.get("streams"):
        raise ValueError(f"no video stream found in {path}")
    stream = payload["streams"][0]
    return VideoProbe(
        width=int(stream["width"]),
        height=int(stream["height"]),
        fps=_parse_rate(stream.get("avg_frame_rate", "0/1")),
        duration_s=float(payload.get("format", {}).get("duration", 0.0)),
        codec=str(stream.get("codec_name", "unknown")),
    )


def probe_frame_timestamps(path: str | Path) -> list[float]:
    """Return video frame timestamps in milliseconds using ffprobe."""

    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "frame=best_effort_timestamp_time",
        "-of",
        "json",
        str(path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=True)
    payload = json.loads(completed.stdout)
    timestamps: list[float] = []
    for frame in payload.get("frames", []):
        raw = frame.get("best_effort_timestamp_time")
        if raw is None:
            continue
        timestamps.append(float(raw) * 1000.0)
    if not timestamps:
        raise ValueError(f"no frame timestamps found in {path}")
    return timestamps
