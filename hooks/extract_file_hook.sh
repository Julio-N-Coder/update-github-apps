#!/usr/bin/env bash
set -euo pipefail

# Generic bash script to extract a file based on the file extension
# Output path can be specified in the first argument
# Defaults to a new directory inside of archive directory

OUT_DIR="${1:-$UPDATER_FILE_DIR}"

ARCHIVE_PATH="$UPDATER_FILE_PATH"
ARCHIVE_NAME="$UPDATER_FILE_NAME"

# Lowercase name for matching
ARCHIVE_LC="${ARCHIVE_NAME,,}"

# Base name without extensions
BASE_NAME="${ARCHIVE_NAME%.*}"
MAYBE_TAR="${BASE_NAME: -4}"
MAYBE_TAR="${MAYBE_TAR,,}"

if [[ "$MAYBE_TAR" == ".tar" ]]; then
	BASE_NAME="${BASE_NAME%.*}"
fi

DEST_DIR="$OUT_DIR/$BASE_NAME"
mkdir -p "$DEST_DIR"

require_cmd() {
	if ! command -v "$1" >/dev/null 2>&1; then
		echo "Error: required tool '$1' is not installed" >&2
		exit 1
	fi
}

echo "Extracting '$ARCHIVE_NAME' → '$DEST_DIR'"

case "$ARCHIVE_LC" in
*.tar)
	require_cmd tar
	tar -xf "$ARCHIVE_PATH" -C "$DEST_DIR"
	;;
*.tar.gz | *.tgz)
	require_cmd tar
	tar -xzf "$ARCHIVE_PATH" -C "$DEST_DIR"
	;;
*.tar.xz)
	require_cmd tar
	tar -xJf "$ARCHIVE_PATH" -C "$DEST_DIR"
	;;
*.tar.bz2)
	require_cmd tar
	tar -xjf "$ARCHIVE_PATH" -C "$DEST_DIR"
	;;
*.tar.zst)
	require_cmd tar
	tar --zstd -xf "$ARCHIVE_PATH" -C "$DEST_DIR"
	;;
*.zip)
	require_cmd unzip
	unzip -q "$ARCHIVE_PATH" -d "$DEST_DIR"
	;;
*.7z)
	require_cmd 7z
	7z x -y -o"$DEST_DIR" "$ARCHIVE_PATH"
	;;
*.rar)
	if command -v unrar >/dev/null 2>&1; then
		unrar x -o+ "$ARCHIVE_PATH" "$DEST_DIR" >/dev/null
	elif command -v 7z >/dev/null 2>&1; then
		7z x -y -o"$DEST_DIR" "$ARCHIVE_PATH"
	else
		echo "Error: unrar or 7z is not installed" >&2
		exit 1
	fi
	;;
# Archives bellow typically contain only a single file if not archived with tar
*.gz)
	require_cmd gzip
	gzip -dc "$ARCHIVE_PATH" >"$DEST_DIR/$BASE_NAME"
	;;
*.xz)
	require_cmd xz
	xz -dc "$ARCHIVE_PATH" >"$DEST_DIR/$BASE_NAME"
	;;
*.bz2)
	require_cmd bzip2
	bzip2 -dc "$ARCHIVE_PATH" >"$DEST_DIR/$BASE_NAME"
	;;
*.zst)
	require_cmd zstd
	zstd -dc "$ARCHIVE_PATH" >"$DEST_DIR/$BASE_NAME"
	;;
*.lz4)
	require_cmd lz4
	lz4 -dc "$ARCHIVE_PATH" >"$DEST_DIR/$BASE_NAME"
	;;
*)
	echo "Error: unsupported archive format: $ARCHIVE_NAME" >&2
	exit 1
	;;
esac

echo "Extraction complete"
