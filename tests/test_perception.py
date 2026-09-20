import pytest

from video_pose.frames import DecodedFrame
from video_pose.observations import Observation
from video_pose.perception import MultiViewPerceptionAdapter
from video_pose.video_manifest import CameraPosition
from video_pose.video_replay import FrameRef, SynchronizedFrameSet


def _frame_set() -> SynchronizedFrameSet:
    frames = {
        position: FrameRef(
            camera_id=f"cam-{position.value.lower()}",
            position=position,
            uri=f"{position.value.lower()}.mp4",
            source_timestamp_ms=1000.0,
            normalized_timestamp_ms=1000.0,
        )
        for position in CameraPosition
    }
    return SynchronizedFrameSet(
        reference_timestamp_ms=1000.0,
        frames=frames,
        skew_ms=0.0,
    )


class FakeLoader:
    def load(self, ref: FrameRef) -> DecodedFrame:
        return DecodedFrame(ref=ref, image=f"pixels:{ref.camera_id}")


class FakeModel:
    def infer(
        self,
        frame: DecodedFrame,
        *,
        session_id: str,
    ) -> list[Observation]:
        return [
            Observation.model_validate(
                {
                    "observation_id": f"obs-{frame.ref.camera_id}",
                    "session_id": session_id,
                    "camera_id": frame.ref.camera_id,
                    "timestamp_ms": frame.ref.normalized_timestamp_ms,
                    "type": "OBJECT",
                    "entity_id": f"person-{frame.ref.camera_id}",
                    "entity_class": "person",
                    "confidence": 0.98,
                }
            )
        ]


def test_multi_view_adapter_runs_model_for_all_four_cameras() -> None:
    adapter = MultiViewPerceptionAdapter(
        session_id="session-1",
        frame_loader=FakeLoader(),
        model=FakeModel(),
    )
    observations = adapter.infer(_frame_set())
    assert len(observations) == 4
    assert {item.camera_id for item in observations} == {
        "cam-front",
        "cam-rear",
        "cam-left",
        "cam-right",
    }


class WrongCameraModel(FakeModel):
    def infer(
        self,
        frame: DecodedFrame,
        *,
        session_id: str,
    ) -> list[Observation]:
        output = super().infer(frame, session_id=session_id)
        return [output[0].model_copy(update={"camera_id": "wrong-camera"})]


def test_multi_view_adapter_rejects_wrong_camera_output() -> None:
    adapter = MultiViewPerceptionAdapter(
        session_id="session-1",
        frame_loader=FakeLoader(),
        model=WrongCameraModel(),
    )
    with pytest.raises(ValueError, match="another camera"):
        adapter.infer(_frame_set())
