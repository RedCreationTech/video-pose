from __future__ import annotations

from typing import Protocol

from .frames import DecodedFrame
from .observations import Observation
from .video_manifest import CameraPosition
from .video_replay import FrameRef, SynchronizedFrameSet


class FrameLoader(Protocol):
    def load(self, ref: FrameRef) -> DecodedFrame: ...


class CameraPerceptionModel(Protocol):
    def infer(
        self,
        frame: DecodedFrame,
        *,
        session_id: str,
    ) -> list[Observation]: ...


class PerceptionAdapter(Protocol):
    def infer(self, frame_set: SynchronizedFrameSet) -> list[Observation]: ...


class MultiViewPerceptionAdapter:
    """Decode four frame references and normalize model output to Observation."""

    def __init__(
        self,
        *,
        session_id: str,
        frame_loader: FrameLoader,
        model: CameraPerceptionModel,
    ) -> None:
        self.session_id = session_id
        self.frame_loader = frame_loader
        self.model = model

    def infer(self, frame_set: SynchronizedFrameSet) -> list[Observation]:
        output: list[Observation] = []
        for position in CameraPosition:
            ref = frame_set.frames.get(position)
            if ref is None:
                continue
            frame = self.frame_loader.load(ref)
            observations = self.model.infer(frame, session_id=self.session_id)
            for observation in observations:
                self._validate_output(observation, ref)
            output.extend(observations)
        return output

    def _validate_output(self, observation: Observation, ref: FrameRef) -> None:
        if observation.session_id != self.session_id:
            raise ValueError("perception model returned observation for another session")
        if observation.camera_id != ref.camera_id:
            raise ValueError("perception model returned observation for another camera")
