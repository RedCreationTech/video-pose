from __future__ import annotations

from pathlib import Path
from typing import Any

from ..frames import DecodedFrame
from ..overlay import OverlayPrimitive, PrimitiveType


class OpenCVOverlayRenderer:
    """Draw normalized overlay primitives without leaking OpenCV into core."""

    def __init__(self) -> None:
        self._cv2_module: Any | None = None

    def _cv2(self) -> Any:
        if self._cv2_module is not None:
            return self._cv2_module
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError(
                "OpenCVOverlayRenderer requires the optional video dependencies"
            ) from exc
        self._cv2_module = cv2
        return cv2

    def render(
        self,
        frame: DecodedFrame,
        primitives: list[OverlayPrimitive],
    ) -> Any:
        cv2 = self._cv2()
        image = frame.image.copy()
        text_row = 0
        for primitive in primitives:
            if primitive.camera_id != frame.ref.camera_id:
                continue
            if primitive.type == PrimitiveType.BOX:
                if primitive.x2 is None or primitive.y2 is None:
                    continue
                cv2.rectangle(
                    image,
                    (round(primitive.x1), round(primitive.y1)),
                    (round(primitive.x2), round(primitive.y2)),
                    (255, 255, 255),
                    2,
                )
                cv2.putText(
                    image,
                    primitive.label,
                    (round(primitive.x1), max(16, round(primitive.y1) - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45,
                    (255, 255, 255),
                    1,
                    cv2.LINE_AA,
                )
            elif primitive.type == PrimitiveType.POINT:
                cv2.circle(
                    image,
                    (round(primitive.x1), round(primitive.y1)),
                    4,
                    (255, 255, 255),
                    -1,
                )
            else:
                text_row += 1
                cv2.putText(
                    image,
                    primitive.label,
                    (12, 24 * text_row),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (255, 255, 255),
                    1,
                    cv2.LINE_AA,
                )
        return image

    def write_image(
        self,
        frame: DecodedFrame,
        primitives: list[OverlayPrimitive],
        path: str | Path,
    ) -> None:
        cv2 = self._cv2()
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(output), self.render(frame, primitives)):
            raise ValueError(f"failed to write overlay image: {output}")
