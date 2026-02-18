#!/usr/bin/env python3
"""
Simple Find Assets Hook example
"""

import sys
import os
import json

print(
    f"""
======================================
FIND-ASSETS HOOK EXECUTED
======================================
App Name:             {os.getenv("UPDATER_APP_NAME")}
Repository:           {os.getenv("UPDATER_REPO")}
Current Version Tag:  {os.getenv("UPDATER_CURRENT_TAG")}
Latest Version Tag:   {os.getenv("UPDATER_LATEST_TAG")}
Installation Dir:     {os.getenv("UPDATER_INSTALL_DIR")}
Config Dir:           {os.getenv("UPDATER_CONFIG_DIR")}
Arguments:            {", ".join(sys.argv[1:])}
======================================
"""
)

# Read json string list from stdin
asset_names = json.load(sys.stdin)
filtered_asset_names = [
    asset_name for asset_name in asset_names if asset_name.endswith(".tar.gz")
]

print("Find Assets Hook completed successfully!")

# Return json string list in the last line
json.dump(filtered_asset_names, sys.stdout)
