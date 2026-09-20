from video_pose.contracts import ActionEvent, ActionObject
from video_pose.debug_video import (
    action_overlay_primitives,
    estimate_trace_fps,
)
from video_pose.trace import FrameTrace
from video_pose.video_manifest import CameraPosition
from video_pose.video_replay import FrameRef, SynchronizedFrameSet


def _trace(timestamp: float, with_action: bool = False) -> FrameTrace:
    frame = FrameRef(
        camera_id="cam-front",
        position=CameraPosition.FRONT,
        uri="front.mp4",
        source_timestamp_ms=timestamp,
        normalized_timestamp_ms=timestamp,
    )
    actions = ()
    if with_action:
        actions = (
            ActionEvent(
                event_id="a1",
                session_id="s1",
                sequence=1,
                action="PICK",
                object=ActionObject(id="tool", **{"class": "torque_wrench"}),
                started_at_ms=round(timestamp),
                confidence=0.9,
            ),
        )
    return FrameTrace(
        frame_set=SynchronizedFrameSet(
            reference_timestamp_ms=timestamp,
            frames={CameraPosition.FRONT: frame},
            skew_ms=0,
        ),
        observations=(),
        actions=actions,
    )


def test_estimate_trace_fps() -> None:
    fps = estimate_trace_fps([_trace(0), _trace(40), _trace(80)])
    assert fps == 25.0


def test_action_overlay_uses_camera_id() -> None:
    primitives = action_overlay_primitives(_trace(40, with_action=True))
    assert len(primitives) == 1
    assert primitives[0].camera_id == "cam-front"
    assert "PICK" in primitives[0].label
