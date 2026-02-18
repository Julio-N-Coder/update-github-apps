#!/usr/bin/env bash

# Simple test hook that logs information about the downloaded file

echo "======================================"
echo "POST-DOWNLOAD HOOK EXECUTED"
echo "======================================"
echo "App Name:     $UPDATER_APP_NAME"
echo "Repository:   $UPDATER_REPO"
echo "Version Tag:  $UPDATER_TAG"
echo "Asset Name:   $UPDATER_ASSET_NAME"
echo "File Path:    $UPDATER_FILE_PATH"
echo "File Dir:     $UPDATER_FILE_DIR"
echo "File Name:    $UPDATER_FILE_NAME"
echo "Config Dir:   $UPDATER_CONFIG_DIR"
echo "Arguments:    $@"
echo "======================================"
echo ""

echo "Hook completed successfully!"
