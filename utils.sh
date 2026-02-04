#!/usr/bin/env bash
set -euo pipefail

# Utility script for the following features
# running update_github_apps.py with mock_github_api.py in background
# cleaning up directories and files made by update_github_apps.py

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
TRASH_DIR="$SCRIPT_DIR/.trash"
DOWNLOADS_DIR="$SCRIPT_DIR/test-downloads"
CONFIG_FILE="$SCRIPT_DIR/updater_config.json"
URL="http://localhost:8080"

KEEP_CHANGES=false
WRITE_CONFIG=false
CLEANUP=false

show_help() {
    cat <<EOF
Usage: ./utils.sh [OPTIONS]

Utility script for update_github_apps.py

Options:
  -k, --keep				Keep the generated files and directories
  -c --config				Write config to updater_config.json rather than stdout
  -h, --help				Show this help message
  -C, --clean, --cleanup	Cleanup generated files and directories if any

Examples:
  ./utils.sh			Run update_github_apps.py with mock in the background
  				Pipeing config in stdout and receiving via stdout
  ./utils.sh --keep --config
  ./utils.sh --cleanup
EOF
}

for arg in "$@"; do
	case "$arg" in
	-h | --help)
		show_help
		exit 0
		;;
	-k | --keep) KEEP_CHANGES=true ;;
	-c | --config) WRITE_CONFIG=true ;;
	-C |--clean | --cleanup) CLEANUP=true ;;
	esac
done

if $CLEANUP; then
	rm -fr "$TRASH_DIR" "$DOWNLOADS_DIR"
	exit 0
fi

"$SCRIPT_DIR/mock_github_api.py" &
MOCK_PID="$!"

# ping mock until available or timeout
TIMEOUT=10   # seconds
INTERVAL=0.5 # seconds
START_TIME=$(date +%s)

until curl -fs "$URL/status" >/dev/null 2>&1; do
	NOW=$(date +%s)
	if ((NOW - START_TIME >= TIMEOUT)); then
		echo "Timeout: mock_github_api.py did not start in ${TIMEOUT}s" >&2
		kill "$MOCK_PID"
		exit 1
	fi

	sleep "$INTERVAL"
done

if "$WRITE_CONFIG"; then
	"$SCRIPT_DIR/update_github_apps.py" --config "$CONFIG_FILE" --mock-api "$URL"
else
	cat "$SCRIPT_DIR/updater_config.json" | "$SCRIPT_DIR/update_github_apps.py" --config - --mock-api "$URL"
fi
kill "$MOCK_PID"

if ! $KEEP_CHANGES; then
	rm -fr "$TRASH_DIR" "$DOWNLOADS_DIR"
fi
