from __future__ import annotations

from pathlib import Path
from statistics import median
from typing import Any

from .frames import DecodedFrame
from .overlay import OverlayPrimitive, PrimitiveType, build_overlay_primitives
from .trace import FrameTrace
from .video_manifest import CameraPosition


def estimate_trace_fps(traces: list[FrameTrace], default: float = 25.0) -> float:
    timestamps = sorted(
        {
            trace.frame_set.reference_timestamp_ms
            for trace in traces
        }
    )
    deltas = [
        right - left
        for left, right in zip(timestamps, timestamps[1:], strict=False)
        if right > left
    ]
    if not deltas:
        return default
    interval_ms = median(deltas)
    return 1000.0 / interval_ms if interval_ms > 0 else default


def action_overlay_primitives(trace: FrameTrace) -> list[OverlayPrimitive]:
    primitives: list[OverlayPrimitive] = []
    for index, action in enumerate(trace.actions, start=1):
        object_class = action.object.class_name if action.object else None
        label = " ".join(
            part
            for part in [
                f"ACTION={action.action.value}",
                object_class or "",
                f"conf={action.confidence:.2f}",
            ]
            if part
        )
        for frame in trace.frame_set.frames.values():
            primitives.append(
                OverlayPrimitive(
                    type=PrimitiveType.TEXT,
                    camera_id=frame.camera_id,
                    label=label,
                    x1=12,
                    y1=24 * (index + 4),
                )
            )
    return primitives


class OpenCVDebugVideoWriter:
    """Render per-camera trace videos from synchronized replay references."""

    def __init__(self, *, codec: str = "mp4v") -> None:
        self.codec = codec
        self._cv2_module: Any | None = None

    def _cv2(self) -> Any:
        if self._cv2_module is not None:
            return self._cv2_module
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError(
                "OpenCVDebugVideoWriter requires the optional video dependencies"
            ) from exc
        self._cv2_module = cv2
        return cv2

    def write(
        self,
        traces: list[FrameTrace],
        *,
        frame_loader: Any,
        output_dir: str | Path,
        fps: float | None = None,
    ) -> dict[str, str]:
        if not traces:
            return {}
        cv2 = self._cv2()
        output_root = Path(output_dir)
        output_root.mkdir(parents=True, exist_ok=True)
        frame_rate = fps or estimate_trace_fps(traces)

        writers: dict[CameraPosition, Any] = {}
        paths: dict[str, str] = {}
        try:
            for trace in traces:
                base_primitives = build_overlay_primitives(
                    list(trace.observations)
                )
                action_primitives = action_overlay_primitives(trace)
                primitives = base_primitives + action_primitives
                for position, ref in trace.frame_set.frames.items():
                    decoded = frame_loader.load(ref)
                    image = self._render(decoded, primitives)
                    writer = writers.get(position)
                    if writer is None:
                        height, width = image.shape[:2]
                        path = output_root / f"{position.value.lower()}-debug.mp4"
                        fourcc = cv2.VideoWriter_fourcc(*self.codec)
                        writer = cv2.VideoWriter(
                            str(path),
                            fourcc,
                            frame_rate,
                            (width, height),
                        )
                        if not writer.isOpened():
                            writer.release()
                            raise ValueError(
                                f"cannot open debug video writer: {path}"
                            )
                        writers[position] = writer
                        paths[position.value] = str(path)
                    writer.write(image)
        finally:
            for writer in writers.values():
                writer.release()
        return paths

    def _render(
        self,
        frame: DecodedFrame,
        primitives: list[OverlayPrimitive],
    ) -> Any:
        from .adapters.opencv_overlay import OpenCVOverlayRenderer

        renderer = OpenCVOverlayRenderer()
        renderer._cv2_module = self._cv2()
        return renderer.render(frame, primitives)
