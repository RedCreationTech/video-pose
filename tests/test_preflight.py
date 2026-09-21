from video_pose.live_health import (
    AuditHealthSnapshot,
    LiveHealthSnapshot,
    RuntimeHealthSnapshot,
    StorageHealthSnapshot,
)
from video_pose.preflight import build_preflight_report
from video_pose.session_readiness import (
    SessionReadinessCheck,
    SessionReadinessReport,
)


def test_preflight_report_minimizes_sensitive_details() -> None:
    report = build_preflight_report(
        workstation_id="ws-1",
        readiness=SessionReadinessReport(
            policy_enabled=True,
            ready=False,
            checks=[
                SessionReadinessCheck(
                    name="asset:rules",
                    passed=False,
                    detail="/secret/site/rules.yaml",
                )
            ],
        ),
        health=LiveHealthSnapshot(
            cameras=[],
            runtime=RuntimeHealthSnapshot(),
            audit=AuditHealthSnapshot(
                status="DEGRADED",
                write_errors_total=2,
                last_error="/secret/audit path failed",
            ),
            storage=[
                StorageHealthSnapshot(
                    name="audit",
                    configured_path="/secret/audit",
                    probe_path="/secret",
                    total_bytes=1000,
                    used_bytes=500,
                    free_bytes=500,
                    free_ratio=0.5,
                )
            ],
            ready=False,
        ),
        cameras=[
            {
                "camera_id": "front",
                "position": "FRONT",
                "enabled": True,
                "state": "ONLINE",
                "fps": 25,
                "reconnect_total": 0,
                "capture_backend": "gstreamer-native",
                "timestamp_source": "pts",
                "snapshot_available": True,
                "uri": "rtsp://user:pass@camera/private",
            }
        ],
        release_identity={
            "application_version": "0.58.0",
            "git_sha": "abc",
            "image_digest": "sha256:def",
            "release_fingerprint": "f" * 64,
            "runtime_fingerprint": {
                "model_release_id": "model-r1",
            },
        },
        persistence={
            "configured": True,
            "status": "DEGRADED",
            "last_error": "postgresql://user:pass@db",
            "reconciliation": {
                "status": "DIRTY",
                "failed_count": 1,
                "incomplete_count": 0,
            },
        },
    )
    rendered = report.model_dump_json()
    assert report.ready is False
    assert report.failed_checks == ["asset:rules"]
    assert report.checks[0].status == "FAIL"
    assert "/secret" not in rendered
    assert "rtsp://" not in rendered
    assert "postgresql://" not in rendered
