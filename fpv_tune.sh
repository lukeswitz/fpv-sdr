#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/fpv_env.sh"
resolve_fpv_python || { echo "[ERROR] no Python with GNU Radio bindings; set FPV_PYTHON" >&2; exit 1; }
exec "$PYTHON" "$DIR/fpv_tune.py" "$@"
