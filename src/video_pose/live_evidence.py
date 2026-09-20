from __future__ import annotations

import hashlib
import json
import re
import threading
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, Field

from .frames import DecodedFrame
from .video_replay import FrameRef, SynchronizedFrameSet


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _safe_segment(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value)
    return safe.strip("._") or "unknown"


class EvidenceEncoder(Protocol):
    def encode(self, image: Any) -> bytes: ...


class OpenCVJPEGEncoder:
    def __init__(self, *, quality: int = 70) -> None:
        if not 1 <= quality <= 100:
            raise ValueError("quality must be between 1 and 100")
        self.quality = quality
        self._cv2_module: Any | None = None

    def _cv2(self) -> Any:
        if self._cv2_module is not None:
            return self._cv2_module
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError(
                "live evidence requires the optional video dependencies"
            ) from exc
        self._cv2_module = cv2
        return cv2

    def encode(self, image: Any) -> bytes:
        cv2 = self._cv2()
        ok, encoded = cv2.imencode(
            ".jpg",
            image,
            [cv2.IMWRITE_JPEG_QUALITY, self.quality],
        )
        if not ok:
            raise ValueError("failed to encode evidence JPEG")
        return bytes(encoded)


@dataclass(frozen=True, slots=True)
class _EncodedFrame:
    camera_id: str
    timestamp_ms: float
    content: bytes


@dataclass(frozen=True, slots=True)
class _PendingCapture:
    evidence_id: str
    session_id: str
    violation: dict[str, Any]
    start_ms: float
    end_ms: float


class EvidenceImage(BaseModel):
    camera_id: str
    timestamp_ms: float
    filename: str
    sha256: str
    size_bytes: int


class LiveEvidenceManifest(BaseModel):
    evidence_id: str
    session_id: str
    status: str
    violation_type: str
    rule_id: str
    step_code: str
    event_id: str
    normalized_start_ms: float
    normalized_end_ms: float
    created_at: str
    cameras_expected: list[str] = Field(default_factory=list)
    cameras_present: list[str] = Field(default_factory=list)
    images: list[EvidenceImage] = Field(default_factory=list)


class LiveEvidenceBuffer:
    """Compressed rolling evidence buffer with pre/post violation capture."""

    def __init__(
        self,
        *,
        root: str | Path,
        encoder: EvidenceEncoder,
        camera_ids: list[str],
        pre_roll_ms: int = 3000,
        post_roll_ms: int = 3000,
        sample_interval_ms: int = 200,
        max_pending: int = 32,
    ) -> None:
        self.root = Path(root)
        self.encoder = encoder
        self.camera_ids = tuple(camera_ids)
        self.pre_roll_ms = pre_roll_ms
        self.post_roll_ms = post_roll_ms
        self.sample_interval_ms = sample_interval_ms
        self.max_pending = max_pending
        self._retention_ms = pre_roll_ms + post_roll_ms + 5000
        self._lock = threading.RLock()
        self._frames: dict[str, deque[_EncodedFrame]] = {
            camera_id: deque() for camera_id in self.camera_ids
        }
        self._last_sample_ms: dict[str, float] = {}
        self._pending: dict[str, _PendingCapture] = {}

    def ingest(
        self,
        frame_set: SynchronizedFrameSet,
        frame_loader: Any,
    ) -> list[LiveEvidenceManifest]:
        encoded: list[_EncodedFrame] = []
        for ref in frame_set.frames.values():
            last = self._last_sample_ms.get(ref.camera_id)
            if (
                last is not None
                and ref.normalized_timestamp_ms - last
                < self.sample_interval_ms
            ):
                continue
            frame: DecodedFrame = frame_loader.load(ref)
            encoded.append(
                _EncodedFrame(
                    camera_id=ref.camera_id,
                    timestamp_ms=ref.normalized_timestamp_ms,
                    content=self.encoder.encode(frame.image),
                )
            )

        with self._lock:
            for item in encoded:
                self._frames.setdefault(item.camera_id, deque()).append(item)
                self._last_sample_ms[item.camera_id] = item.timestamp_ms
            cutoff = (
                frame_set.reference_timestamp_ms - self._retention_ms
            )
            self._prune(cutoff)
            ready = [
                pending
                for pending in self._pending.values()
                if frame_set.reference_timestamp_ms >= pending.end_ms
            ]
            manifests = [
                self._finalize_locked(pending, force_partial=False)
                for pending in ready
            ]
        return manifests

    def schedule(
        self,
        session_id: str,
        violation: dict[str, Any],
        *,
        timestamp_ms: float,
    ) -> str:
        identity = "|".join(
            [
                session_id,
                str(violation.get("rule_id", "")),
                str(violation.get("step", "")),
                str(violation.get("event_id", "")),
            ]
        )
        evidence_id = "evidence-" + hashlib.sha256(
            identity.encode("utf-8")
        ).hexdigest()[:16]
        with self._lock:
            if self.get_manifest(session_id, evidence_id) is not None:
                return evidence_id
            if evidence_id in self._pending:
                return evidence_id
            if len(self._pending) >= self.max_pending:
                oldest = next(iter(self._pending))
                self._finalize_locked(
                    self._pending[oldest],
                    force_partial=True,
                )
            self._pending[evidence_id] = _PendingCapture(
                evidence_id=evidence_id,
                session_id=session_id,
                violation=dict(violation),
                start_ms=max(0.0, timestamp_ms - self.pre_roll_ms),
                end_ms=timestamp_ms + self.post_roll_ms,
            )
        return evidence_id

    def flush_pending(self) -> list[LiveEvidenceManifest]:
        with self._lock:
            pending = list(self._pending.values())
            return [
                self._finalize_locked(item, force_partial=True)
                for item in pending
            ]

    def list_session(
        self,
        session_id: str,
    ) -> list[LiveEvidenceManifest]:
        session_root = self.root / _safe_segment(session_id)
        if not session_root.exists():
            return []
        manifests: list[LiveEvidenceManifest] = []
        for path in sorted(session_root.glob("*/manifest.json")):
            manifests.append(
                LiveEvidenceManifest.model_validate_json(
                    path.read_text(encoding="utf-8")
                )
            )
        return manifests

    def get_manifest(
        self,
        session_id: str,
        evidence_id: str,
    ) -> LiveEvidenceManifest | None:
        path = (
            self.root
            / _safe_segment(session_id)
            / _safe_segment(evidence_id)
            / "manifest.json"
        )
        if not path.exists():
            return None
        return LiveEvidenceManifest.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    def read_file(
        self,
        session_id: str,
        evidence_id: str,
        camera_id: str,
        filename: str,
    ) -> bytes:
        base = (
            self.root
            / _safe_segment(session_id)
            / _safe_segment(evidence_id)
        ).resolve()
        candidate = (
            base
            / _safe_segment(camera_id)
            / _safe_segment(filename)
        ).resolve()
        if base not in candidate.parents:
            raise ValueError("invalid evidence path")
        if not candidate.exists():
            raise FileNotFoundError(candidate)
        return candidate.read_bytes()

    def _prune(self, cutoff_ms: float) -> None:
        for frames in self._frames.values():
            while frames and frames[0].timestamp_ms < cutoff_ms:
                frames.popleft()

    def _finalize_locked(
        self,
        pending: _PendingCapture,
        *,
        force_partial: bool,
    ) -> LiveEvidenceManifest:
        directory = (
            self.root
            / _safe_segment(pending.session_id)
            / _safe_segment(pending.evidence_id)
        )
        directory.mkdir(parents=True, exist_ok=True)

        images: list[EvidenceImage] = []
        present: set[str] = set()
        for camera_id in self.camera_ids:
            camera_frames = [
                frame
                for frame in self._frames.get(camera_id, ())
                if pending.start_ms
                <= frame.timestamp_ms
                <= pending.end_ms
            ]
            if not camera_frames:
                continue
            present.add(camera_id)
            camera_dir = directory / _safe_segment(camera_id)
            camera_dir.mkdir(parents=True, exist_ok=True)
            for index, frame in enumerate(camera_frames):
                filename = (
                    f"{index:04d}-"
                    f"{round(frame.timestamp_ms):012d}.jpg"
                )
                path = camera_dir / filename
                path.write_bytes(frame.content)
                images.append(
                    EvidenceImage(
                        camera_id=camera_id,
                        timestamp_ms=frame.timestamp_ms,
                        filename=filename,
                        sha256=hashlib.sha256(
                            frame.content
                        ).hexdigest(),
                        size_bytes=len(frame.content),
                    )
                )

        complete = set(self.camera_ids) == present
        status = "COMPLETE" if complete and not force_partial else "PARTIAL"
        violation = pending.violation
        manifest = LiveEvidenceManifest(
            evidence_id=pending.evidence_id,
            session_id=pending.session_id,
            status=status,
            violation_type=str(violation.get("type", "")),
            rule_id=str(violation.get("rule_id", "")),
            step_code=str(violation.get("step", "")),
            event_id=str(violation.get("event_id", "")),
            normalized_start_ms=pending.start_ms,
            normalized_end_ms=pending.end_ms,
            created_at=_utc_now(),
            cameras_expected=list(self.camera_ids),
            cameras_present=sorted(present),
            images=images,
        )
        (directory / "manifest.json").write_text(
            manifest.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )
        self._pending.pop(pending.evidence_id, None)
        return manifest
