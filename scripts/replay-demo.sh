#!/usr/bin/env bash
set -euo pipefail
python -m video_pose.cli \
  --events "${1:-fixtures/replay/compliant.jsonl}" \
  --rules "${2:-fixtures/rules/assembly-a.yaml}"
