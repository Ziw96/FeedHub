#!/bin/zsh

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <feedhub-command> [args...]" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="$REPO_ROOT/.venv/bin/python"

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi

mkdir -p "$REPO_ROOT/logs" "$REPO_ROOT/data/digests"

cd "$REPO_ROOT"
exec "$PYTHON_BIN" -m src.feedhub.main "$@"
