from __future__ import annotations

from typing import Any

from ..frames import DecodedFrame
from ..video_replay import FrameRef


class OpenCVFileFrameLoader:
    """Offline file frame loader.

    OpenCV is imported lazily so the core package remains usable without AI/video
    extras. Production RTSP should use a persistent streaming implementation.
    """

    def __init__(self) -> None:
        self._captures: dict[str, Any] = {}
        self._cv2_module: Any | None = None

    def _cv2(self) -> Any:
        if self._cv2_module is not None:
            return self._cv2_module
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError(
                "OpenCVFileFrameLoader requires opencv-python or "
                "opencv-python-headless"
            ) from exc
        self._cv2_module = cv2
        return cv2

    def load(self, ref: FrameRef) -> DecodedFrame:
        cv2 = self._cv2()
        capture = self._captures.get(ref.uri)
        if capture is None:
            capture = cv2.VideoCapture(ref.uri)
            if not capture.isOpened():
                capture.release()
                raise ValueError(f"cannot open video file: {ref.uri}")
            self._captures[ref.uri] = capture

        capture.set(cv2.CAP_PROP_POS_MSEC, ref.source_timestamp_ms)
        ok, image = capture.read()
        if not ok:
            raise ValueError(
                f"cannot decode frame at {ref.source_timestamp_ms} ms: {ref.uri}"
            )
        return DecodedFrame(ref=ref, image=image)

    def close(self) -> None:
        for capture in self._captures.values():
            capture.release()
        self._captures.clear()

    def __enter__(self) -> OpenCVFileFrameLoader:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
