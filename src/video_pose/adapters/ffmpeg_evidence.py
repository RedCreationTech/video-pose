from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..evidence import CameraClipPlan, EvidenceBundlePlan
from ..video_manifest import CameraPosition


@dataclass(frozen=True, slots=True)
class EvidenceArtifact:
    evidence_id: str
    directory: str
    camera_clips: dict[str, str]
    multiview_clip: str | None


class FFmpegEvidenceWriter:
    """Render exact evidence clips and an optional 2x2 synchronized mosaic."""

    def __init__(
        self,
        *,
        ffmpeg_binary: str = "ffmpeg",
        width: int = 640,
        height: int = 360,
    ) -> None:
        self.ffmpeg_binary = ffmpeg_binary
        self.width = width
        self.height = height

    def write_bundle(
        self,
        plan: EvidenceBundlePlan,
        output_root: str | Path,
    ) -> EvidenceArtifact:
        directory = Path(output_root) / plan.evidence_id
        directory.mkdir(parents=True, exist_ok=True)

        clip_paths: dict[str, str] = {}
        ordered_paths: list[tuple[CameraPosition, Path]] = []
        for camera in plan.cameras:
            path = directory / f"{camera.position.value.lower()}.mp4"
            subprocess.run(
                self.build_clip_command(camera, path),
                check=True,
            )
            clip_paths[camera.camera_id] = str(path)
            ordered_paths.append((camera.position, path))

        multiview: Path | None = None
        if len(ordered_paths) == 4:
            multiview = directory / "multiview.mp4"
            subprocess.run(
                self.build_mosaic_command(ordered_paths, multiview),
                check=True,
            )

        return EvidenceArtifact(
            evidence_id=plan.evidence_id,
            directory=str(directory),
            camera_clips=clip_paths,
            multiview_clip=str(multiview) if multiview is not None else None,
        )

    def build_clip_command(
        self,
        plan: CameraClipPlan,
        output_path: str | Path,
    ) -> list[str]:
        start_seconds = plan.source_start_ms / 1000.0
        duration_seconds = max(0.001, plan.duration_ms / 1000.0)
        return [
            self.ffmpeg_binary,
            "-y",
            "-ss",
            f"{start_seconds:.3f}",
            "-i",
            plan.uri,
            "-t",
            f"{duration_seconds:.3f}",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            str(output_path),
        ]

    def build_mosaic_command(
        self,
        clips: list[tuple[CameraPosition, Path]],
        output_path: str | Path,
    ) -> list[str]:
        order = {
            CameraPosition.FRONT: 0,
            CameraPosition.REAR: 1,
            CameraPosition.LEFT: 2,
            CameraPosition.RIGHT: 3,
        }
        clips = sorted(clips, key=lambda item: order[item[0]])
        command = [self.ffmpeg_binary, "-y"]
        for _, path in clips:
            command.extend(["-i", str(path)])

        filter_parts = [
            f"[{index}:v]scale={self.width}:{self.height}[v{index}]"
            for index in range(4)
        ]
        filter_parts.append(
            "[v0][v1][v2][v3]"
            "xstack=inputs=4:layout=0_0|w0_0|0_h0|w0_h0[v]"
        )
        command.extend(
            [
                "-filter_complex",
                ";".join(filter_parts),
                "-map",
                "[v]",
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "20",
                str(output_path),
            ]
        )
        return command
