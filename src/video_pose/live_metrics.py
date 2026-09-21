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

    sync = snapshot.sync
    if sync is not None:
        lines.extend(
            [
                _metric(
                    "video_pose_sync_reference_frames_total",
                    sync.reference_frames_total,
                ),
                _metric(
                    "video_pose_sync_emitted_total",
                    sync.emitted_total,
                ),
                _metric(
                    "video_pose_sync_miss_total",
                    sync.miss_total,
                ),
                _metric(
                    "video_pose_sync_missing_buffer_total",
                    sync.missing_buffer_total,
                ),
                _metric(
                    "video_pose_sync_tolerance_miss_total",
                    sync.tolerance_miss_total,
                ),
                _metric(
                    "video_pose_sync_stale_reference_total",
                    sync.stale_reference_total,
                ),
                _metric(
                    "video_pose_sync_success_ratio",
                    sync.success_ratio,
                ),
                _metric(
                    "video_pose_sync_skew_ms",
                    sync.last_skew_ms or 0.0,
                ),
                _metric(
                    "video_pose_sync_skew_max_ms",
                    sync.max_skew_ms,
                ),
                _metric(
                    "video_pose_sync_skew_p95_ms",
                    sync.skew_p95_ms,
                ),
                _metric(
                    "video_pose_sync_skew_p99_ms",
                    sync.skew_p99_ms,
                ),
            ]
        )
        for camera_id, offset_ms in sorted(
            sync.camera_offsets_ms.items()
        ):
            lines.append(
                _metric(
                    "video_pose_sync_camera_offset_ms",
                    offset_ms,
                    {"camera": camera_id},
                )
            )
        for camera_id, drift in sorted(
            sync.camera_drift_ms_per_minute.items()
        ):
            lines.append(
                _metric(
                    "video_pose_sync_camera_drift_ms_per_minute",
                    drift,
                    {"camera": camera_id},
                )
            )

    evidence = snapshot.evidence
    if evidence is not None:
        lines.extend(
            [
                _metric(
                    "video_pose_evidence_submitted_total",
                    evidence.submitted_total,
                ),
                _metric(
                    "video_pose_evidence_processed_total",
                    evidence.processed_total,
                ),
                _metric(
                    "video_pose_evidence_dropped_total",
                    evidence.dropped_total,
                ),
                _metric(
                    "video_pose_evidence_errors_total",
                    evidence.errors_total,
                ),
                _metric(
                    "video_pose_evidence_queue_depth",
                    evidence.queue_depth,
                ),
                _metric(
                    "video_pose_evidence_queue_capacity",
                    evidence.queue_capacity,
                ),
                _metric(
                    "video_pose_evidence_drop_ratio",
                    evidence.drop_ratio,
                ),
                _metric(
                    "video_pose_evidence_artifacts",
                    evidence.artifact_count,
                ),
                _metric(
                    "video_pose_evidence_protected_artifacts",
                    evidence.protected_count,
                ),
                _metric(
                    "video_pose_evidence_storage_bytes",
                    evidence.total_bytes,
                ),
                _metric(
                    "video_pose_evidence_storage_limit_bytes",
                    evidence.max_total_bytes,
                ),
                _metric(
                    "video_pose_evidence_over_capacity",
                    1 if evidence.over_capacity else 0,
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
            _metric(
                "video_pose_processing_latency_p95_ms",
                runtime.processing_latency_p95_ms,
            ),
            _metric(
                "video_pose_processing_latency_p99_ms",
                runtime.processing_latency_p99_ms,
            ),
            _metric(
                "video_pose_process_rss_mb",
                runtime.current_rss_mb or 0.0,
            ),
            _metric(
                "video_pose_process_rss_max_mb",
                runtime.max_rss_mb,
            ),
            _metric(
                "video_pose_gpu_memory_allocated_mb",
                runtime.gpu_allocated_mb or 0.0,
            ),
            _metric(
                "video_pose_gpu_memory_reserved_mb",
                runtime.gpu_reserved_mb or 0.0,
            ),
            _metric(
                "video_pose_gpu_memory_reserved_max_mb",
                runtime.max_gpu_reserved_mb,
            ),
        ]
    )
    return "\n".join(lines) + "\n"
