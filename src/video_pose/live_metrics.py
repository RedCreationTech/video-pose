from __future__ import annotations

from .live_health import LiveHealthSnapshot


def _metric(
    name: str,
    value: int | float,
    labels: dict[str, str] | None = None,
) -> str:
    label_text = ""
    if labels:
        rendered = ",".join(
            f'{key}="{value}"'
            for key, value in sorted(labels.items())
        )
        label_text = f"{{{rendered}}}"
    return f"{name}{label_text} {value}"


def render_prometheus(snapshot: LiveHealthSnapshot) -> str:
    lines = [
        "# TYPE video_pose_ready gauge",
        _metric("video_pose_ready", 1 if snapshot.ready else 0),
        "# TYPE video_pose_camera_frames_total counter",
    ]
    for camera in snapshot.cameras:
        labels = {"camera": camera.camera_id}
        lines.extend(
            [
                _metric(
                    "video_pose_camera_frames_total",
                    camera.frames_total,
                    labels,
                ),
                _metric(
                    "video_pose_camera_read_errors_total",
                    camera.read_errors_total,
                    labels,
                ),
                _metric(
                    "video_pose_camera_reconnect_total",
                    camera.reconnect_total,
                    labels,
                ),
                _metric(
                    "video_pose_camera_fps",
                    round(camera.fps_estimate, 6),
                    labels,
                ),
                _metric(
                    "video_pose_camera_online",
                    1 if camera.state == "ONLINE" else 0,
                    labels,
                ),
            ]
        )

    runtime = snapshot.runtime
    lines.extend(
        [
            _metric(
                "video_pose_frame_sets_received_total",
                runtime.frame_sets_received_total,
            ),
            _metric(
                "video_pose_frame_sets_processed_total",
                runtime.frame_sets_processed_total,
            ),
            _metric(
                "video_pose_frame_sets_dropped_total",
                runtime.frame_sets_dropped_total,
            ),
            _metric(
                "video_pose_processing_errors_total",
                runtime.processing_errors_total,
            ),
            _metric(
                "video_pose_processing_queue_depth",
                runtime.queue_depth,
            ),
            _metric(
                "video_pose_processing_queue_capacity",
                runtime.queue_capacity,
            ),
            _metric(
                "video_pose_processing_latency_ms",
                runtime.last_processing_latency_ms or 0.0,
            ),
            _metric(
                "video_pose_processing_latency_max_ms",
                runtime.max_processing_latency_ms,
            ),
        ]
    )
    return "\n".join(lines) + "\n"
