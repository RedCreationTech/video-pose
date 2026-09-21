from video_pose.acceptance_bundle_cli import build_parser


def test_acceptance_bundle_cli_defaults_to_require_ready() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "create",
            "--acceptance",
            "acceptance.json",
            "--output",
            "bundle.zip",
        ]
    )
    assert args.allow_not_ready is False
    assert args.extra == []
