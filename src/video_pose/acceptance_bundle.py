from __future__ import annotations

import hashlib
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from .release_acceptance import ReleaseAcceptanceReport


class AcceptanceBundleEntry(BaseModel):
    kind: str
    source_path: str
    archive_path: str
    sha256: str
    size_bytes: int


class AcceptanceBundleManifest(BaseModel):
    schema_version: int = 1
    created_at: str
    release_fingerprint: str
    production_ready: bool
    acceptance_sha256: str
    entries: list[AcceptanceBundleEntry] = Field(
        default_factory=list
    )


class AcceptanceBundleBuildResult(BaseModel):
    bundle_path: str
    bundle_sha256: str
    sha256_sidecar_path: str
    manifest: AcceptanceBundleManifest


class AcceptanceBundleVerification(BaseModel):
    passed: bool
    release_fingerprint: str | None = None
    entries_verified: int = 0
    failures: list[str] = Field(default_factory=list)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_token(value: str) -> str:
    cleaned = re.sub(
        r"[^A-Za-z0-9._-]+",
        "-",
        value,
    ).strip("-")
    return cleaned or "artifact"


def _archive_path(
    *,
    index: int,
    kind: str,
    source: Path,
    sha256: str,
) -> str:
    return (
        f"artifacts/{index:03d}-"
        f"{_safe_token(kind)}-"
        f"{sha256[:12]}-"
        f"{_safe_token(source.name)}"
    )


def _load_acceptance(
    path: str | Path,
) -> tuple[ReleaseAcceptanceReport, bytes]:
    data = Path(path).read_bytes()
    report = ReleaseAcceptanceReport.model_validate_json(
        data
    )
    return report, data


def _verified_report_artifacts(
    report: ReleaseAcceptanceReport,
) -> list[tuple[str, Path, str]]:
    output: list[tuple[str, Path, str]] = []
    seen: set[Path] = set()
    for artifact in report.artifacts:
        source = Path(artifact.path).resolve()
        if source in seen:
            continue
        seen.add(source)
        if not source.is_file():
            raise FileNotFoundError(
                f"acceptance artifact missing: {source}"
            )
        if artifact.sha256 is None:
            raise ValueError(
                f"acceptance artifact has no SHA-256: {source}"
            )
        actual = _sha256_file(source)
        if actual != artifact.sha256:
            raise ValueError(
                f"acceptance artifact SHA-256 mismatch: {source}"
            )
        output.append(
            (artifact.kind, source, actual)
        )
    return output


def create_acceptance_bundle(
    *,
    acceptance_report_path: str | Path,
    output_path: str | Path,
    extra_paths: list[str | Path] | None = None,
    allow_not_ready: bool = False,
) -> AcceptanceBundleBuildResult:
    report, acceptance_bytes = _load_acceptance(
        acceptance_report_path
    )
    if not report.production_ready and not allow_not_ready:
        raise ValueError(
            "acceptance report is not production_ready; "
            "use allow_not_ready only for non-production archives"
        )

    acceptance_sha = _sha256_bytes(acceptance_bytes)
    sources = _verified_report_artifacts(report)

    seen = {path for _kind, path, _sha in sources}
    for extra in extra_paths or []:
        source = Path(extra).resolve()
        if source in seen:
            continue
        if not source.is_file():
            raise FileNotFoundError(
                f"extra bundle artifact missing: {source}"
            )
        sources.append(
            ("extra", source, _sha256_file(source))
        )
        seen.add(source)

    entries: list[AcceptanceBundleEntry] = [
        AcceptanceBundleEntry(
            kind="release-acceptance",
            source_path=str(
                Path(acceptance_report_path).resolve()
            ),
            archive_path="acceptance/release-acceptance.json",
            sha256=acceptance_sha,
            size_bytes=len(acceptance_bytes),
        )
    ]

    for index, (kind, source, sha256) in enumerate(
        sources,
        start=1,
    ):
        entries.append(
            AcceptanceBundleEntry(
                kind=kind,
                source_path=str(source),
                archive_path=_archive_path(
                    index=index,
                    kind=kind,
                    source=source,
                    sha256=sha256,
                ),
                sha256=sha256,
                size_bytes=source.stat().st_size,
            )
        )

    manifest = AcceptanceBundleManifest(
        created_at=datetime.now(UTC).isoformat(),
        release_fingerprint=(
            report.release_identity.release_fingerprint
        ),
        production_ready=report.production_ready,
        acceptance_sha256=acceptance_sha,
        entries=entries,
    )

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        output,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        archive.writestr(
            "acceptance/release-acceptance.json",
            acceptance_bytes,
        )
        for entry in entries[1:]:
            archive.write(
                entry.source_path,
                arcname=entry.archive_path,
            )
        archive.writestr(
            "bundle-manifest.json",
            manifest.model_dump_json(indent=2) + "\n",
        )

    bundle_sha = _sha256_file(output)
    sidecar = Path(str(output) + ".sha256")
    sidecar.write_text(
        f"{bundle_sha}  {output.name}\n",
        encoding="utf-8",
    )

    return AcceptanceBundleBuildResult(
        bundle_path=str(output.resolve()),
        bundle_sha256=bundle_sha,
        sha256_sidecar_path=str(sidecar.resolve()),
        manifest=manifest,
    )


def verify_acceptance_bundle(
    path: str | Path,
) -> AcceptanceBundleVerification:
    bundle = Path(path)
    failures: list[str] = []
    verified = 0
    release_fingerprint: str | None = None

    try:
        with zipfile.ZipFile(bundle, "r") as archive:
            manifest = AcceptanceBundleManifest.model_validate_json(
                archive.read("bundle-manifest.json")
            )
            release_fingerprint = manifest.release_fingerprint
            names = set(archive.namelist())
            for entry in manifest.entries:
                if (
                    entry.archive_path.startswith("/")
                    or ".." in Path(entry.archive_path).parts
                ):
                    failures.append(
                        f"unsafe_archive_path:{entry.archive_path}"
                    )
                    continue
                if entry.archive_path not in names:
                    failures.append(
                        f"missing_entry:{entry.archive_path}"
                    )
                    continue
                data = archive.read(entry.archive_path)
                if len(data) != entry.size_bytes:
                    failures.append(
                        f"size_mismatch:{entry.archive_path}"
                    )
                    continue
                if _sha256_bytes(data) != entry.sha256:
                    failures.append(
                        f"sha256_mismatch:{entry.archive_path}"
                    )
                    continue
                verified += 1

            acceptance = archive.read(
                "acceptance/release-acceptance.json"
            )
            if (
                _sha256_bytes(acceptance)
                != manifest.acceptance_sha256
            ):
                failures.append("acceptance_sha256_mismatch")
    except (
        OSError,
        KeyError,
        zipfile.BadZipFile,
        ValueError,
    ) as exc:
        failures.append(
            f"bundle_invalid:{type(exc).__name__}"
        )

    return AcceptanceBundleVerification(
        passed=not failures,
        release_fingerprint=release_fingerprint,
        entries_verified=verified,
        failures=failures,
    )
