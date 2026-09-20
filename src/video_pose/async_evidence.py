from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from .frames import DecodedFrame
from .evidence_retention import EvidenceRetentionManager
from .live_evidence import LiveEvidenceBuffer, LiveEvidenceManifest
from .video_replay import FrameRef, SynchronizedFrameSet


@dataclass(frozen=True, slots=True)
class _CapturedBatch:
    frame_set: SynchronizedFrameSet
    images: dict[str, Any]


class EvidenceWorkerStats(BaseModel):
    submitted_total: int = 0
    processed_total: int = 0
    dropped_total: int = 0
    errors_total: int = 0
    queue_depth: int = 0
    queue_capacity: int = 0


class _CapturedFrameLoader:
    def __init__(self, images: dict[str, Any]) -> None:
        self.images = images

    def load(self, ref: FrameRef) -> DecodedFrame:
        return DecodedFrame(
            ref=ref,
            image=self.images[ref.uri],
        )


class AsyncLiveEvidenceRecorder:
    """Move JPEG encoding and evidence I/O off the camera capture thread."""

    def __init__(
        self,
        buffer: LiveEvidenceBuffer,
        *,
        queue_size: int = 2,
        retention: EvidenceRetentionManager | None = None,
        cleanup_interval_s: float = 3600.0,
    ) -> None:
        if queue_size < 1:
            raise ValueError("queue_size must be >= 1")
        self.buffer = buffer
        self.queue_size = queue_size
        self.retention = retention
        self.cleanup_interval_s = cleanup_interval_s
        self._last_cleanup_monotonic = 0.0
        self._queue: queue.Queue[_CapturedBatch] = queue.Queue(
            maxsize=queue_size
        )
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._worker: threading.Thread | None = None
        self._submitted_total = 0
        self._processed_total = 0
        self._dropped_total = 0
        self._errors_total = 0

    def start(self) -> None:
        if self._worker is not None:
            return
        self._stop.clear()
        self._worker = threading.Thread(
            target=self._run,
            name="video-pose-evidence",
            daemon=True,
        )
        self._worker.start()

    def stop(self) -> list[LiveEvidenceManifest]:
        self._stop.set()
        if self._worker is not None:
            self._worker.join(timeout=5.0)
            self._worker = None
        return self.buffer.flush_pending()

    def submit(
        self,
        frame_set: SynchronizedFrameSet,
        frame_loader: Any,
    ) -> None:
        images = {
            ref.uri: frame_loader.load(ref).image
            for ref in frame_set.frames.values()
        }
        batch = _CapturedBatch(
            frame_set=frame_set,
            images=images,
        )
        with self._lock:
            self._submitted_total += 1
        try:
            self._queue.put_nowait(batch)
        except queue.Full:
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except queue.Empty:
                pass
            with self._lock:
                self._dropped_total += 1
            self._queue.put_nowait(batch)

    def wait_until_idle(self) -> None:
        self._queue.join()

    def stats(self) -> EvidenceWorkerStats:
        with self._lock:
            return EvidenceWorkerStats(
                submitted_total=self._submitted_total,
                processed_total=self._processed_total,
                dropped_total=self._dropped_total,
                errors_total=self._errors_total,
                queue_depth=self._queue.qsize(),
                queue_capacity=self.queue_size,
            )

    def schedule(
        self,
        session_id: str,
        violation: dict[str, Any],
        *,
        timestamp_ms: float,
    ) -> str:
        return self.buffer.schedule(
            session_id,
            violation,
            timestamp_ms=timestamp_ms,
        )

    def list_session(
        self,
        session_id: str,
    ) -> list[LiveEvidenceManifest]:
        return self.buffer.list_session(session_id)

    def get_manifest(
        self,
        session_id: str,
        evidence_id: str,
    ) -> LiveEvidenceManifest | None:
        return self.buffer.get_manifest(session_id, evidence_id)

    def mark_reviewed(
        self,
        session_id: str,
        *,
        rule_id: str,
        step_code: str,
        event_id: str,
        status: str,
        reviewed_at: str | None,
    ) -> str:
        return self.buffer.mark_reviewed(
            session_id,
            rule_id=rule_id,
            step_code=step_code,
            event_id=event_id,
            status=status,
            reviewed_at=reviewed_at,
        )

    def read_file(
        self,
        session_id: str,
        evidence_id: str,
        camera_id: str,
        filename: str,
    ) -> bytes:
        return self.buffer.read_file(
            session_id,
            evidence_id,
            camera_id,
            filename,
        )

    def _run(self) -> None:
        while not self._stop.is_set() or not self._queue.empty():
            try:
                batch = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                finalized = self.buffer.ingest(
                    batch.frame_set,
                    _CapturedFrameLoader(batch.images),
                )
                if finalized:
                    self._maybe_cleanup()
                with self._lock:
                    self._processed_total += 1
            except Exception:
                with self._lock:
                    self._errors_total += 1
            finally:
                self._queue.task_done()

    def _maybe_cleanup(self) -> None:
        if self.retention is None:
            return
        now = time.monotonic()
        if (
            now - self._last_cleanup_monotonic
            < self.cleanup_interval_s
        ):
            return
        self.retention.cleanup()
        self._last_cleanup_monotonic = now
