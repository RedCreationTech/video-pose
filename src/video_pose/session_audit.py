from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SessionAuditMetadata(BaseModel):
    session_id: str
    operator_id: str | None = None
    operation: str
    workstation_id: str
    rule_set_version: int
    started_at: str
    config_path: str
    detector_weights: str
    pose_config: str | None = None
    pose_checkpoint: str | None = None
    planar_calibration: str | None = None
    perspective_calibration: str | None = None


class SessionAuditWriter:
    """Durable JSON/JSONL audit writer for one operation session."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self._lock = threading.Lock()

    def start(self, metadata: SessionAuditMetadata) -> Path:
        directory = self.root / metadata.session_id
        directory.mkdir(parents=True, exist_ok=False)
        self._write_json(
            directory / "metadata.json",
            metadata.model_dump(mode="json"),
        )
        (directory / "updates.jsonl").touch()
        return directory

    def append_payload(
        self,
        session_id: str,
        payload: dict[str, Any],
    ) -> None:
        record = {
            "recorded_at": _utc_now(),
            "payload": payload,
        }
        path = self.root / session_id / "updates.jsonl"
        rendered = json.dumps(
            record,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        with self._lock:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(rendered + "\n")

    def finish(
        self,
        session_id: str,
        final_payload: dict[str, Any],
        *,
        status: str,
    ) -> Path:
        path = self.root / session_id / "final.json"
        payload = {
            "status": status,
            "ended_at": _utc_now(),
            "result": final_payload,
        }
        self._write_json(path, payload)
        return path

    def _write_json(
        self,
        path: Path,
        payload: dict[str, Any],
    ) -> None:
        rendered = json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )
        with self._lock:
            path.write_text(rendered + "\n", encoding="utf-8")
