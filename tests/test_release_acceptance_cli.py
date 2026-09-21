from video_pose.release_acceptance_cli import build_parser


def test_release_acceptance_cli_defaults_to_full_gate() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "--config",
            "runtime.yaml",
            "--output",
            "acceptance.json",
        ]
    )
    assert args.quick is False
    assert args.min_soak_hours == 72.0
    assert args.min_soak_completed_sessions == 2
