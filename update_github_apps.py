#!/usr/bin/env python3
"""
GitHub Release Updater
Automatically checks and updates applications to the latest version from GitHub releases

Features:
- asset name matching with Fixed, Tag name substitution, or pattern-based (regex support)
- Support for latest releases or pre-releases
- Automatic downloading and updating
- Old version management (moved to a trash directory)
- Optional Post Download Hook with optional arguments
- Mock API support for testing without rate limits
"""

import argparse
import getpass
import json
import os
import re
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path, PurePath
from typing import Dict, Optional, List, Tuple
import atexit


class Colors:
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[0;34m"
    NC = "\033[0m"  # No Color


def log_info(message: str) -> None:
    """Print info message in blue."""
    print(f"{Colors.BLUE}[INFO]{Colors.NC} {message}")


def log_success(message: str) -> None:
    """Print success message in green."""
    print(f"{Colors.GREEN}[SUCCESS]{Colors.NC} {message}")


def log_warning(message: str) -> None:
    """Print warning message in yellow."""
    print(f"{Colors.YELLOW}[WARNING]{Colors.NC} {message}")


def log_error(message: str) -> None:
    """Print error message in red."""
    print(f"{Colors.RED}[ERROR]{Colors.NC} {message}")


class GitHubUpdater:
    """Main updater class for managing GitHub release updates."""

    def __init__(
        self,
        config_path: str,
        api_base_url: Optional[str] = None,
        github_token: Optional[str] = None,
    ):
        """
        Args:
            config_path: Path to the JSON configuration file or '-' for passing config through stdin
            api_base_url: Base URL for GitHub API (for testing with mock server) (optional)
            github_token: GitHub personal access token for authentication (optional)
        """
        if config_path == "-":
            self.config_path = config_path
            self.base_dir = Path.cwd()
        else:
            self.config_path = Path(config_path).resolve()
            self.base_dir = self.config_path.parent
        self.config_data: Dict = None

        # Trash Config will be set after loading config (default path: .trash in base dir)
        # A seperate config object so trash config in config file is not changed when the file is saved
        self.trash_config: Dict = None

        # Set API base URL (default to real GitHub API)
        self.api_base_url = api_base_url or "https://api.github.com"
        if self.api_base_url != "https://api.github.com":
            log_info(f"Using custom API endpoint: {self.api_base_url}")

        # GitHub token will be set after loading config (priority: passed token > env var > config file)
        self.github_token = github_token

    def load_config(self) -> bool:
        """
        Load and validate the configuration file.

        Returns:
            True if config loaded successfully, False otherwise
        """
        if isinstance(self.config_path, PurePath) and not self.config_path.exists():
            log_error(f"Missing config file: {self.config_path}")
            log_error(f"Config file format is as shown below:")
            print(
                """
{
  "trash_config": {
    "trash_path": ".trash",
    "append_tag": true,
    "append_date": false
  },
  "github_token": "ghp_xxxxxxxxxxxx",
  "apps": [
    {
      "name": "App Name",
      "repo": "owner/repo",
      "tag": "current_tag",
      "asset_pattern": "filename.zip",
      "asset_match_type": "fixed",
      "install_path": "./path/filename.zip",
      "use_prerelease": false,
      "post_download_hook": "optional_command_to_run.sh",
      "post_download_hook_args": ["--arg1", "--arg2"]
    }
  ]
}

Field descriptions:
- trash_config: trash configuration for old versions (optional, defaults path to ".trash", relative to config file)
- github_token: GitHub personal access token (optional, for higher rate limits or private repos)
- name: Display name for the app
- repo: GitHub repository in format "owner/repo"
- tag: Current installed tag/version
- asset_pattern: Fixed filename, regex pattern, or template with {tag} placeholder
- asset_match_type: "fixed" for exact match, "regex" for pattern, "tag" for tag substitution
- install_path: Where to save the downloaded file (relative to config file or absolute)
- use_prerelease: true to check pre-releases, false for stable releases only (optional, defaults to false)
- post_download_hook: Command/script to run after successful download (optional, relative to config file or absolute)
- post_download_hook_args: Argumentst to pass to post hook (optional)

Examples of asset_match_type:
- "fixed": asset_pattern = "app-release.zip" (exact match)
- "regex": asset_pattern = "^app-v[0-9.]+\\.zip$" (pattern matching)
- "tag": asset_pattern = "app-{tag}-linux.zip" (replaces {tag} with version)
"""
            )
            return False

        try:
            if self.config_path == "-":
                self.config_data = json.load(sys.stdin)
            else:
                with open(self.config_path, "r") as f:
                    self.config_data = json.load(f)

            if "apps" not in self.config_data:
                log_error("Config file must contain an 'apps' array")
                return False

            # Set up trash config
            # trash config is copied to not modify config file once saved
            self.trash_config = self.config_data.get(
                "trash_config",
                {"trash_path": "./.trash", "append_tag": True, "append_date": False},
            ).copy()
            trash_path = Path(self.trash_config["trash_path"])

            if not trash_path.is_absolute():
                trash_path = self.base_dir / trash_path
            else:
                trash_path = trash_path

            # Create trash directory if it doesn't exist and save trash_path to config
            trash_path.mkdir(parents=True, exist_ok=True)
            log_info(f"Trash directory: {trash_path}")
            self.trash_config["trash_path"] = trash_path

            # Token is already set from CLI flag if passed
            # priority: CLI flag > env var > config file
            if not self.github_token:
                if "GITHUB_TOKEN" in os.environ:
                    self.github_token = os.environ["GITHUB_TOKEN"]
                    log_info("Using GitHub token from environment variable")
                elif "github_token" in self.config_data:
                    self.github_token = self.config_data["github_token"]
                    log_info("Using GitHub token from config file")
            else:
                log_info("Using GitHub token from command-line argument")

            if self.github_token:
                log_success("Authenticated requests enabled (5,000 req/hour limit)")
            else:
                log_info("Using unauthenticated requests (60 req/hour limit)")

            return True
        except json.JSONDecodeError as e:
            log_error(f"Invalid JSON in config file: {e}")
            return False
        except Exception as e:
            log_error(f"Error reading config file: {e}")
            return False

    def save_config(self):
        """
        Save the current configuration back to the file.
        """
        try:
            if self.config_path == "-":
                json.dump(self.config_data, sys.stdout)
                print()
            elif self.config_path.exists():
                with open(self.config_path, "w") as f:
                    json.dump(self.config_data, f, indent=2)
                    f.write("\n")
        except Exception as e:
            log_error(f"Error saving config file: {e}")

    def github_api_request(self, url: str) -> Optional[Dict]:
        """
        Make a request to the GitHub API.

        Args:
            url: The API URL to request

        Returns:
            JSON response as dict, or None on error
        """
        try:
            req = urllib.request.Request(url)
            req.add_header("Accept", "application/vnd.github.v3+json")

            # Add authentication if token is available
            if self.github_token:
                req.add_header("Authorization", f"Bearer {self.github_token}")

            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as e:
            log_error(f"HTTP error {e.code}: {e.reason}")
            if e.code == 401:
                log_error("Authentication failed - check your GitHub token")
            return None
        except urllib.error.URLError as e:
            log_error(f"URL error: {e.reason}")
            return None
        except Exception as e:
            log_error(f"Error making API request: {e}")
            return None

    def get_latest_release(
        self, repo: str, use_prerelease: bool = False
    ) -> Optional[Dict]:
        """
        Get the latest release for a repository.

        Args:
            repo: Repository in format "owner/repo"
            use_prerelease: If True, include pre-releases

        Returns:
            Release info dict, or None on error
        """
        if use_prerelease:
            # Get all releases and find the latest (including pre-releases)
            url = f"{self.api_base_url}/repos/{repo}/releases"
            releases = self.github_api_request(url)

            if not releases or not isinstance(releases, list) or len(releases) == 0:
                log_error(f"No releases found for {repo}")
                return None

            # Return the first release (most recent)
            return releases[0]
        else:
            # Get only the latest stable release
            url = f"{self.api_base_url}/repos/{repo}/releases/latest"
            return self.github_api_request(url)

    def replace_tag(self, string_with_tag: str, tag: str) -> Tuple:
        """
        Replace literal "{tag}" in a string with the actual tag

        Args:
            string_with_tag: String with "{tag}"
            tag: The release tag

        Returns:
            Tuple of size 3 of strings.

            First, Tag as is

            Second without v prefix

            Third with v prefix
        """
        tag_clean = tag.lstrip("v")
        tag_with_v = tag if tag.startswith("v") else f"v{tag}"

        # Multiple substitutions to handle different tag formats
        return (
            string_with_tag.replace("{tag}", tag),
            string_with_tag.replace("{tag}", tag_clean),
            string_with_tag.replace("{tag}", tag_with_v),
        )

    def find_assets(
        self, release: Dict, pattern: str, match_type: str, tag: str = ""
    ) -> Optional[List[Dict]]:
        """
        Find a matching asset in a release.

        Args:
            release: Release info dict from GitHub API
            pattern: Asset name pattern (exact string, regex, or tag template)
            match_type: "fixed" for exact match, "regex" for pattern, "tag" for tag substitution
            tag: The release tag (used for "tag" match_type)

        Returns:
            Asset info dict, or None if not found
        """
        assets = release.get("assets", [])

        if not assets:
            log_error("No assets found in release")
            return None

        if match_type == "all":
            return assets

        for asset in assets:
            asset_name = asset.get("name", "")

            if match_type == "fixed":
                if asset_name == pattern:
                    return [asset]
            elif match_type == "regex":
                try:
                    if re.match(pattern, asset_name):
                        return [asset]
                except re.error as e:
                    log_error(f"Invalid regex pattern '{pattern}': {e}")
                    return None
            elif match_type == "tag":
                if asset_name in self.replace_tag(pattern, tag):
                    return [asset]
            else:
                log_error(f"Unknown match_type: {match_type}")
                return None

        return None

    def download_file(self, url: str, output_path: Path) -> bool:
        """
        Download a file from a URL.

        Args:
            url: URL to download from
            output_path: Where to save the file

        Returns:
            True if successful, False otherwise
        """
        try:
            log_info(f"Downloading from {url}...")

            # Create parent directory if it doesn't exist
            output_path.parent.mkdir(parents=True, exist_ok=True)

            urllib.request.urlretrieve(url, output_path)

            log_success(f"Downloaded to {output_path}")
            return True
        except Exception as e:
            log_error(f"Failed to download file: {e}")
            return False

    def move_to_trash(self, file_path: Path, old_tag: str) -> bool:
        """
        Move an old file to the trash directory.

        Args:
            file_path: Path to the file to move
            old_tag: Old version tag (for trash filename)

        Returns:
            True if successful, False otherwise
        """
        # full trash path name == trash_dir / f"{file_name}_{safe_tag}_{timestamp}" + f"_{count}" + f"{suffix}"
        try:
            suffix = file_path.suffix  # extension
            file_name = file_path.stem
            if file_name[-4:] == ".tar":
                suffix = ".tar" + suffix
                file_name = file_name[:-4]

            trash_name = f"{file_name}"

            if self.trash_config["append_tag"]:
                # Sanitize tag for filename
                safe_tag = old_tag.replace("/", "_")

                trash_name += f"_{safe_tag}"
            if self.trash_config["append_date"]:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                trash_name += f"_{timestamp}"

            trash_dir: Path = self.trash_config["trash_path"]
            trash_path: Path = trash_dir / (trash_name + f"{suffix}")

            # Append an increasing number if the same file name exists
            count = 1
            while trash_path.exists():
                trash_path = trash_dir / (trash_name + f"_{count}" + f"{suffix}")
                count += 1

            log_info(f"Moving old version to trash: {trash_path}")
            file_path.rename(trash_path)
            return True
        except Exception as e:
            log_error(f"Failed to move file to trash: {e}")
            return False

    def run_post_download_hook(
        self,
        hook_command: str,
        app_data: Dict,
        install_path: Path,
        asset_name: str,
        latest_tag: str,
    ) -> bool:
        """
        Run a post-download hook script.

        Args:
            hook_command: Command to execute (relative to config dir or absolute)
            app_data: App configuration dictionary
            install_path: Path to downloaded file
            asset_name: Name of the downloaded asset
            latest_tag: Version tag that was downloaded

        Returns:
            True if successful, False otherwise
        """

        # if relative resolve it from base directory
        hook_path = Path(hook_command)
        if not hook_path.is_absolute() and hook_path.exists():
            resolved_hook = self.base_dir / hook_path
            if resolved_hook.exists():
                hook_command = str(resolved_hook.resolve())

        # Prepare environment variables for the hook
        hook_env = os.environ.copy()
        hook_env.update(
            {
                "UPDATER_APP_NAME": app_data.get("name", ""),
                "UPDATER_REPO": app_data.get("repo", ""),
                "UPDATER_TAG": latest_tag,
                "UPDATER_ASSET_NAME": asset_name,
                "UPDATER_FILE_PATH": str(install_path.resolve()),
                "UPDATER_FILE_DIR": str(install_path.parent.resolve()),
                "UPDATER_FILE_NAME": install_path.name,
                "UPDATER_CONFIG_DIR": str(self.base_dir.resolve()),
            }
        )

        log_info(f"Running post-download hook: {hook_command}")

        try:
            # Run the hook command with optional args in working directory
            hook_list: list = app_data.get("post_download_hook_args", [])
            hook_list.insert(0, hook_command)

            result = subprocess.run(
                hook_list,
                env=hook_env,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                cwd=str(self.base_dir),
            )

            # Print hook output if there is any
            if result.stdout:
                print(result.stdout, end="")
            if result.stderr:
                print(result.stderr, end="", file=sys.stderr)

            if result.returncode == 0:
                log_success("Post-download hook completed successfully")
                return True
            else:
                log_error(
                    f"Post-download hook failed with exit code {result.returncode}"
                )
                return False

        except subprocess.TimeoutExpired:
            log_error("Post-download hook timed out (5 minute limit)")
            return False
        except Exception as e:
            log_error(f"Error running post-download hook: {e}")
            return False

    def run_find_assets_hook(
        self, hook_command: str, app_data: Dict, release: Dict, install_path: Path
    ) -> Optional[List[Dict]]:
        """
        Run a hook to filter for specific assets.

        Args:
            hook_command: Command to execute
            app_data: App configuration dictionary
            release: Release information dictionary with assets
            install_path: Path to Installation Directory

        Returns:
            List of assets if successful, None otherwise
        """
        # if relative resolve it
        hook_path = Path(hook_command)
        if not hook_path.is_absolute() and hook_path.exists():
            resolved_hook = self.base_dir / hook_path
            if resolved_hook.exists():
                hook_command = str(resolved_hook.resolve())

        # Prepare environment variables for the hook
        hook_env = os.environ.copy()
        hook_env.update(
            {
                "UPDATER_APP_NAME": app_data.get("name", ""),
                "UPDATER_REPO": app_data.get("repo", ""),
                "UPDATER_CURRENT_TAG": app_data.get("tag", ""),
                "UPDATER_LATEST_TAG": release.get("tag_name", ""),
                "UPDATER_INSTALL_DIR": install_path,
                "UPDATER_CONFIG_DIR": str(self.base_dir.resolve()),
            }
        )

        log_info(f"Running find assets hook: {hook_command}")

        assets = release.get("assets", [])
        asset_names = [asset["name"] for asset in assets]

        try:
            # Run the hook command with optional args
            hook_list: list = app_data.get("find_assets_hook_args", [])
            hook_list.insert(0, hook_command)

            result = subprocess.run(
                hook_list,
                input=json.dumps(
                    asset_names
                ),  # Passing a json string list of asset names to stdin
                env=hook_env,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                cwd=str(self.base_dir),
            )

            if result.stderr:
                print(result.stderr, end="", file=sys.stderr)

            if result.returncode == 0 and result.stdout:
                # Everything but the last line is printed to stdout
                split_stdout = result.stdout.split("\n")
                print("\n".join(split_stdout[:-1]))

                # Last line Should be a json string list of asset names
                filtered_asset_names = json.loads(split_stdout[-1])
                if type(filtered_asset_names) == list:
                    log_success("Find-assets hook completed successfully")
                    return [
                        asset
                        for asset in assets
                        if asset["name"] in filtered_asset_names
                    ]
                else:
                    log_error("Find-assets hook did not return a json string list")
                    return False
            else:
                log_error(f"Find-assets hook failed with exit code {result.returncode}")
                return False

        except subprocess.TimeoutExpired:
            log_error("Find-assets hook timed out (5 minute limit)")
            return False
        except Exception as e:
            log_error(f"Error running find-assets hook: {e}")
            return False

    def update_app(self, app_index: int) -> bool:
        """
        Check and update a single app.

        Args:
            app_index: Index of the app in the config

        Returns:
            True if successful or no update needed, False on error
        """
        app: Dict = self.config_data["apps"][app_index]

        # Get app configuration
        name = app.get("name", "Unknown")
        repo = app.get("repo")
        current_tag = app.get("tag", "")
        asset_pattern = app.get("asset_pattern")
        match_type = app.get("asset_match_type", "fixed")
        install_path_str = app.get("install_path")
        use_prerelease = app.get("use_prerelease", False)
        install_path_match_type: str = app.get("install_path_match_type", "fixed")
        find_assets_hook = app.get("find_assets_hook")

        # Validate fields
        # only "repo" and "install_path_str" are required with match_type == "all" or find_assets_hook
        if (match_type == "all" or find_assets_hook) and not all(
            [repo, install_path_str]
        ):
            log_error(f"App '{name}' is missing required fields")
            return False
        elif (match_type != "all" and not find_assets_hook) and not all(
            [repo, asset_pattern, install_path_str]
        ):
            log_error(f"App '{name}' is missing required fields")
            return False

        # Resolve relative install path from base dir
        install_path = Path(install_path_str)
        if not install_path.is_absolute():
            install_path = self.base_dir / install_path

        print()
        log_info(f"Checking {name}...")
        log_info(f"Current tag: {current_tag}")
        log_info(f"Repository: {repo}")
        log_info(f"Check pre-releases: {use_prerelease}")

        # Get latest release
        latest_release = self.get_latest_release(repo, use_prerelease)
        if not latest_release:
            log_warning(f"Skipping {name} due to error")
            return False

        latest_tag = latest_release.get("tag_name", "")
        log_info(f"Latest tag: {latest_tag}")

        needs_download = False
        is_update = False

        # Check if update is available
        if current_tag != latest_tag:
            log_success("New version available!")
            needs_download = True
            is_update = True
        else:
            log_info("Already on latest version")

            # Check if file exists
            if not install_path.exists():
                log_warning(f"File not found at {install_path}, will re-download")
                needs_download = True
            else:
                log_success("File exists, no action needed")

        if needs_download:
            # Find matching assets
            if find_assets_hook:
                assets = self.run_find_assets_hook(
                    find_assets_hook, app, latest_release, install_path
                )
            else:
                assets = self.find_assets(
                    latest_release, asset_pattern, match_type, latest_tag
                )

            if not assets:
                log_error(
                    f"No matching assets found for pattern '{asset_pattern}' (type: {match_type})"
                )
                return False

            for asset in assets:
                asset_name: str = asset.get("name")
                download_url: str = asset.get("browser_download_url")

                if not download_url:
                    log_error("Asset has no download URL")
                    continue

                log_info(f"Matched asset: {asset_name}")

                # Handle output_path and prev_file_path
                output_path = install_path
                prev_file_path = install_path
                if (
                    match_type == "all"
                    or install_path_match_type == "asset_name"
                    or find_assets_hook
                ):
                    # Install_path is a directory here
                    output_path = output_path / asset_name
                    prev_file_path = prev_file_path / asset_name
                elif install_path_match_type == "tag":
                    # Use previous tag to move old file
                    prev_file_path = (
                        output_path.parent
                        / self.replace_tag(str(output_path.name), current_tag)[0]
                    )
                    output_path = (
                        output_path.parent
                        / self.replace_tag(str(output_path.name), latest_tag)[0]
                    )

                # Move old version to trash if it exists and if updating
                # If install_path_match_type == "asset_name" or asset_match_type == "all" or find_assets_hook:
                #   Can't move old file to trash since we don't know the old file name
                if is_update and prev_file_path.exists():
                    if not self.move_to_trash(prev_file_path, current_tag):
                        log_warning(
                            "Failed to move old version to trash, continuing anyway..."
                        )

                # Download new version
                if self.download_file(download_url, output_path):
                    # Update config with new tag
                    app["tag"] = latest_tag

                    if is_update:
                        log_success(
                            f"{name} updated from {current_tag} to {latest_tag}"
                        )
                    else:
                        log_success(f"{name} downloaded (version {latest_tag})")

                    post_hook = app.get("post_download_hook")
                    if post_hook:
                        self.run_post_download_hook(
                            post_hook, app, output_path, asset_name, latest_tag
                        )
                else:
                    log_error(f"Failed to download {name}")

        return True

    def run(self, apps_arg=[], repos_arg=[]) -> int:
        """
        Run the updater for apps

        Args:
            apps_arg: List of app names to check
            repos_arg: List of repo names to check

        Returns:
            Exit code (0 for success, 1 for error)
        """
        print("=========================================")
        print("  GitHub Release Updater (Python)")
        print("=========================================")

        # Load configuration
        if not self.load_config():
            return 1

        apps = self.config_data.get("apps", [])
        app_count = len(apps)

        if app_count == 0:
            log_warning(f"No apps configured in {self.config_path}")
            return 0

        log_info(f"Found {app_count} app(s) in config")

        # Check all app if both apps_arg and repos_arg are empty
        # Otherwise check if app name is specified in apps_arg
        # or if repo is specified in repos_arg
        for i in range(app_count):
            if (not apps_arg and not repos_arg) or (
                apps[i]["name"] in apps_arg or apps[i]["repo"] in repos_arg
            ):
                try:
                    self.update_app(i)
                except Exception as e:
                    log_error(f"Unexpected error updating app {i}: {e}")

        print()
        print("=========================================")
        log_success("Update check complete!")
        print("=========================================")

        return 0


def main():
    parser = argparse.ArgumentParser(
        description="GitHub Release Updater - Automatically update apps from GitHub releases",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
  GITHUB_API_BASE_URL    Custom GitHub API base URL (for testing)
  GITHUB_TOKEN           GitHub personal access token for authentication

Examples:
  # Normal usage
  ./update_github_apps.py

  # With GitHub token (environment variable - recommended)
  export GITHUB_TOKEN=ghp_your_token_here
  ./update_github_apps.py

  # With GitHub token (secure prompt)
  ./update_github_apps.py --token-prompt

  # With GitHub token (CLI flag - saved in bash history)
  ./update_github_apps.py --token ghp_your_token_here

  # Use mock API server for testing (via flag)
  ./update_github_apps.py --mock-api http://localhost:8080

  # Use mock API server for testing (via environment variable)
  export GITHUB_API_BASE_URL=http://localhost:8080
  ./update_github_apps.py

  # Custom config file location
  ./update_github_apps.py --config /path/to/config.json

  # Only Check for updates on specific apps and repos
  ./update_github_apps.py --apps app_name_1 "app name 2" --repos repo_name_1 "repo name 2"

Token Priority (highest to lowest):
  1. --token or --token-prompt (CLI flags)
  2. GITHUB_TOKEN environment variable
  3. "github_token" in config file
        """,
    )
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default=None,
        help="Path to config file (default: updater_config.json in config directory)",
    )
    parser.add_argument(
        "--mock-api",
        "-m",
        type=str,
        default=None,
        help="Mock API base URL for testing (e.g., http://localhost:8080)",
    )
    parser.add_argument(
        "--token",
        "-t",
        type=str,
        default=None,
        help="GitHub personal access token (WARNING: will be saved in shell history)",
    )
    parser.add_argument(
        "--token-prompt",
        "-T",
        action="store_true",
        help="Prompt for GitHub token securely (recommended, not saved in history)",
    )
    parser.add_argument(
        "--apps",
        "-A",
        nargs="+",
        default=[],
        help="Only check for updates on specific apps via their name (works with --repos)",
    )
    parser.add_argument(
        "--repos",
        "-R",
        nargs="+",
        default=[],
        help="Only check for updates on specific apps via their repo name (works with --apps)",
    )

    args = parser.parse_args()

    # Determine config file path. '-' == stdin
    if args.config and args.config != "-":
        config_file = Path(args.config)
    elif args.config == "-":
        config_file = args.config
    else:
        config_file = Path.cwd() / "updater_config.json"

    # Determine API base URL (priority: CLI flag > env var)
    api_base_url = None
    if args.mock_api:
        api_base_url = args.mock_api.rstrip("/")
    elif "GITHUB_API_BASE_URL" in os.environ:
        api_base_url = os.environ["GITHUB_API_BASE_URL"].rstrip("/")

    # Determine GitHub token (priority: Secure Prompt > Direct flag)
    github_token = None
    if args.token_prompt:
        github_token = getpass.getpass("Enter GitHub token: ")
        if not github_token:
            log_warning("No token entered, continuing without authentication")
    elif args.token:
        github_token = args.token

    updater = GitHubUpdater(
        config_file, api_base_url=api_base_url, github_token=github_token
    )

    atexit.register(updater.save_config)

    exit_code = updater.run(args.apps, args.repos)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
