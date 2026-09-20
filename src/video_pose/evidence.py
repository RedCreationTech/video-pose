from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .contracts import ActionEvent, ReplayResult
from .video_manifest import CameraPosition, ReplayManifest


@dataclass(frozen=True, slots=True)
class CameraClipPlan:
    camera_id: str
    position: CameraPosition
    uri: str
    source_start_ms: float
    source_end_ms: float

    @property
    def duration_ms(self) -> float:
        return max(0.0, self.source_end_ms - self.source_start_ms)


@dataclass(frozen=True, slots=True)
class EvidenceBundlePlan:
    evidence_id: str
    violation_type: str
    violation_event_id: str
    normalized_start_ms: float
    normalized_end_ms: float
    cameras: tuple[CameraClipPlan, ...]


class EvidencePlanner:
    """Map rule violations back to synchronized source-video time windows."""

    def __init__(
        self,
        manifest: ReplayManifest,
        *,
        manifest_dir: str | Path,
        pre_roll_ms: float = 3000.0,
        post_roll_ms: float = 3000.0,
    ) -> None:
        self.manifest = manifest
        self.manifest_dir = Path(manifest_dir)
        self.pre_roll_ms = pre_roll_ms
        self.post_roll_ms = post_roll_ms

    def plan(
        self,
        actions: list[ActionEvent],
        evaluation: ReplayResult,
    ) -> list[EvidenceBundlePlan]:
        by_event_id = {action.event_id: action for action in actions}
        fallback = actions[-1] if actions else None
        bundles: list[EvidenceBundlePlan] = []

        for index, violation in enumerate(evaluation.violations, start=1):
            action = by_event_id.get(violation.event_id, fallback)
            if action is None:
                continue

            normalized_start = max(
                0.0,
                float(action.started_at_ms) - self.pre_roll_ms,
            )
            action_end = action.ended_at_ms or action.started_at_ms
            normalized_end = float(action_end) + self.post_roll_ms
            clips = tuple(
                self._camera_clip(
                    camera_id=camera.camera_id,
                    position=camera.position,
                    uri=camera.uri,
                    clock_offset_ms=camera.clock_offset_ms,
                    normalized_start_ms=normalized_start,
                    normalized_end_ms=normalized_end,
                )
                for camera in self.manifest.cameras
                if camera.enabled
            )
            bundles.append(
                EvidenceBundlePlan(
                    evidence_id=f"evidence-{index:04d}",
                    violation_type=violation.type,
                    violation_event_id=violation.event_id,
                    normalized_start_ms=normalized_start,
                    normalized_end_ms=normalized_end,
                    cameras=clips,
                )
            )
        return bundles

    def _camera_clip(
        self,
        *,
        camera_id: str,
        position: CameraPosition,
        uri: str,
        clock_offset_ms: float,
        normalized_start_ms: float,
        normalized_end_ms: float,
    ) -> CameraClipPlan:
        source_start = max(0.0, normalized_start_ms - clock_offset_ms)
        source_end = max(
            source_start + 1.0,
            normalized_end_ms - clock_offset_ms,
        )
        return CameraClipPlan(
            camera_id=camera_id,
            position=position,
            uri=self._resolve_uri(uri),
            source_start_ms=source_start,
            source_end_ms=source_end,
        )

    def _resolve_uri(self, uri: str) -> str:
        if "://" in uri:
            return uri
        path = Path(uri)
        if path.is_absolute():
            return str(path)
        return str((self.manifest_dir / path).resolve())
