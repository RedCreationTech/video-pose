#!/bin/sh
set -eu

CONFIG="${VIDEO_POSE_CONFIG:-/etc/video-pose/runtime.yaml}"
HOST="${VIDEO_POSE_HOST:-0.0.0.0}"
PORT="${VIDEO_POSE_PORT:-8080}"
QUEUE_SIZE="${VIDEO_POSE_QUEUE_SIZE:-2}"
AUDIT_DIR="${VIDEO_POSE_AUDIT_DIR:-/var/lib/video-pose/audit}"
DATABASE_URL="${VIDEO_POSE_DATABASE_URL:-}"

is_true() {
    case "${1:-}" in
        1|true|TRUE|yes|YES|on|ON) return 0 ;;
        *) return 1 ;;
    esac
}

if [ -n "$DATABASE_URL" ] && is_true "${VIDEO_POSE_DB_MIGRATE:-1}"; then
    retries="${VIDEO_POSE_DB_MIGRATION_RETRIES:-30}"
    attempt=1
    until video-pose-db --database-url "$DATABASE_URL" upgrade; do
        if [ "$attempt" -ge "$retries" ]; then
            echo "database migration failed after $attempt attempts" >&2
            exit 2
        fi
        echo "database migration attempt $attempt failed, retrying" >&2
        attempt=$((attempt + 1))
        sleep 2
    done
fi

if is_true "${VIDEO_POSE_RUN_DOCTOR:-1}"; then
    set -- video-pose-doctor --config "$CONFIG"
    if is_true "${VIDEO_POSE_DOCTOR_SKIP_CUDA:-0}"; then
        set -- "$@" --skip-cuda
    fi
    "$@"
fi

set -- video-pose-serve \
    --config "$CONFIG" \
    --host "$HOST" \
    --port "$PORT" \
    --queue-size "$QUEUE_SIZE" \
    --audit-dir "$AUDIT_DIR"

if [ -n "$DATABASE_URL" ]; then
    set -- "$@" --database-url "$DATABASE_URL"
fi

if is_true "${VIDEO_POSE_AUTH_ENABLED:-0}"; then
    set -- "$@" --auth-enabled
fi

exec "$@"
