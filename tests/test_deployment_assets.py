from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_compose_contains_hardened_edge_and_private_database() -> None:
    payload = yaml.safe_load(
        (
            ROOT / "deploy/compose/docker-compose.yml"
        ).read_text(encoding="utf-8")
    )
    services = payload["services"]
    edge = services["edge"]
    postgres = services["postgres"]

    assert edge["read_only"] is True
    assert "ALL" in edge["cap_drop"]
    assert "no-new-privileges:true" in edge["security_opt"]
    assert edge["healthcheck"]["test"][0] == "CMD"
    assert "ports" not in postgres
    assert edge["depends_on"]["postgres"]["condition"] == "service_healthy"

    mounts = " ".join(edge["volumes"])
    assert "/etc/video-pose:ro" in mounts
    assert "/opt/video-pose/models:ro" in mounts
    assert "/var/lib/video-pose/audit" in mounts
    assert "/var/lib/video-pose/evidence" in mounts


def test_edge_entrypoint_runs_migration_doctor_then_service() -> None:
    script = (
        ROOT / "deploy/edge/entrypoint.sh"
    ).read_text(encoding="utf-8")
    migration = script.index("video-pose-db")
    doctor = script.index("video-pose-doctor")
    serve = script.index("video-pose-serve")
    assert migration < doctor < serve


def test_runtime_directory_is_gitignored() -> None:
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "/deploy/compose/runtime/" in ignore


def test_env_example_contains_no_real_default_secret() -> None:
    env = (
        ROOT / "deploy/compose/.env.example"
    ).read_text(encoding="utf-8")
    assert "CHANGE_ME_STRONG_PASSWORD" in env
    assert "CHANGE_ME_64_HEX_SHA256" in env
