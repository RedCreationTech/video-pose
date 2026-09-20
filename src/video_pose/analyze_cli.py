from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .adapters.ffmpeg_evidence import EvidenceArtifact, FFmpegEvidenceWriter
from .debug_video import OpenCVDebugVideoWriter
from .evidence import EvidencePlanner
from .offline_runtime import build_offline_runtime
from .runtime_config import load_analysis_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze synchronized multi-view videos with Video Pose"
    )
    parser.add_argument("--config", required=True, help="Offline analysis YAML")
    parser.add_argument(
        "--max-frame-sets",
        type=int,
        default=None,
        help="Limit synchronized frame sets for smoke tests",
    )
    parser.add_argument("--output", help="Write JSON result to this file")
    parser.add_argument(
        "--evidence-dir",
        help="Render violation evidence clips into this directory",
    )
    parser.add_argument(
        "--debug-overlay-dir",
        help="Render four per-camera debug overlay videos",
    )
    return parser


def _artifact_dict(artifact: EvidenceArtifact) -> dict[str, Any]:
    return {
        "evidence_id": artifact.evidence_id,
        "directory": artifact.directory,
        "camera_clips": artifact.camera_clips,
        "multiview_clip": artifact.multiview_clip,
    }


def _serialize(
    actions: list[Any],
    evaluation: Any | None,
    evidence: list[EvidenceArtifact],
    debug_videos: dict[str, str],
) -> dict[str, Any]:
    return {
        "actions": [
            action.model_dump(mode="json", by_alias=True) for action in actions
        ],
        "evaluation": (
            evaluation.model_dump(mode="json", by_alias=True)
            if evaluation is not None
            else None
        ),
        "evidence": [_artifact_dict(item) for item in evidence],
        "debug_videos": debug_videos,
    }


def main() -> int:
    args = build_parser().parse_args()
    loaded = load_analysis_config(args.config)
    evidence_artifacts: list[EvidenceArtifact] = []
    debug_videos: dict[str, str] = {}

    with build_offline_runtime(loaded) as runtime:
        frame_sets = runtime.planner.plan()
        if args.max_frame_sets is not None:
            frame_sets = frame_sets[: args.max_frame_sets]

        traces = runtime.pipeline.process_with_trace(frame_sets)
        actions = [
            action
            for trace in traces
            for action in trace.actions
        ]
        session_end_ms = (
            round(traces[-1].frame_set.reference_timestamp_ms)
            if traces
            else None
        )
        evaluation = (
            runtime.rule_engine.evaluate(
                actions,
                session_end_ms=session_end_ms,
            )
            if actions
            else None
        )

        if args.debug_overlay_dir:
            debug_videos = OpenCVDebugVideoWriter().write(
                traces,
                frame_loader=runtime.frame_loader,
                output_dir=args.debug_overlay_dir,
            )

        if args.evidence_dir and evaluation is not None:
            planner = EvidencePlanner(
                runtime.planner.manifest,
                manifest_dir=runtime.planner.manifest_dir,
            )
            writer = FFmpegEvidenceWriter()
            evidence_artifacts = [
                writer.write_bundle(plan, args.evidence_dir)
                for plan in planner.plan(actions, evaluation)
            ]

    payload = _serialize(
        actions,
        evaluation,
        evidence_artifacts,
        debug_videos,
    )
    rendered = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)

    if evaluation is None:
        return 3
    return 0 if evaluation.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
