from pathlib import Path

from video_pose.adapters.ffmpeg_evidence import FFmpegEvidenceWriter
from video_pose.contracts import (
    ActionEvent,
    ActionObject,
    ReplayResult,
    Severity,
    Violation,
)
from video_pose.evidence import EvidencePlanner
from video_pose.video_manifest import load_manifest

ROOT = Path(__file__).resolve().parents[1]


def test_evidence_planner_applies_camera_clock_offsets() -> None:
    manifest_path = ROOT / "fixtures/replay/session-manifest.yaml"
    manifest = load_manifest(manifest_path)
    action = ActionEvent(
        event_id="action-1",
        session_id="s1",
        sequence=1,
        action="PICK",
        object=ActionObject(id="part-1", **{"class": "component_A"}),
        started_at_ms=5000,
        ended_at_ms=5500,
        confidence=0.95,
    )
    evaluation = ReplayResult(
        session_id="s1",
        operation="demo",
        rule_set_version=1,
        steps=[],
        violations=[
            Violation(
                rule_id="R1",
                step="S1",
                type="WRONG_OBJECT",
                severity=Severity.MAJOR,
                message="wrong",
                event_id="action-1",
                confidence=0.95,
            )
        ],
        score=90,
        passed=False,
    )

    planner = EvidencePlanner(
        manifest,
        manifest_dir=manifest_path.parent,
        pre_roll_ms=3000,
        post_roll_ms=3000,
    )
    plan = planner.plan([action], evaluation)[0]
    rear = next(
        camera for camera in plan.cameras if camera.camera_id == "cam-rear"
    )
    assert plan.normalized_start_ms == 2000
    assert round(rear.source_start_ms, 1) == 1996.8


def test_ffmpeg_clip_command_uses_planned_window() -> None:
    manifest_path = ROOT / "fixtures/replay/session-manifest.yaml"
    manifest = load_manifest(manifest_path)
    action = ActionEvent(
        event_id="action-1",
        session_id="s1",
        sequence=1,
        action="PICK",
        started_at_ms=4000,
        ended_at_ms=5000,
        confidence=0.95,
    )
    evaluation = ReplayResult(
        session_id="s1",
        operation="demo",
        rule_set_version=1,
        steps=[],
        violations=[
            Violation(
                rule_id="R1",
                step="S1",
                type="SPATIAL",
                severity=Severity.MAJOR,
                message="wrong zone",
                event_id="action-1",
                confidence=0.95,
            )
        ],
        score=90,
        passed=False,
    )
    plan = EvidencePlanner(
        manifest,
        manifest_dir=manifest_path.parent,
        pre_roll_ms=1000,
        post_roll_ms=1000,
    ).plan([action], evaluation)[0]
    writer = FFmpegEvidenceWriter()
    command = writer.build_clip_command(plan.cameras[0], "clip.mp4")
    assert command[0] == "ffmpeg"
    assert "-ss" in command
    assert "-t" in command
    assert command[-1] == "clip.mp4"
