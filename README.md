# GitHub Release Updater

A Python script to automatically check and update applications from GitHub releases.

## Features

- **No external dependencies** - Uses only Python standard library
- **Flexible asset matching** - Fixed names, regex patterns, or tag templates
- **Pre-release support** - Choose between stable or pre-release versions
- **GitHub authentication** - Optional token for higher rate limits or private repos
- **Old version management** - Automatically moves old versions to a trash directory
- **Auto-config updates** - Keeps track of current versions in the config file
- **Re-download missing files** - Even if the tag hasn't changed
- **Post-download hooks** - Run custom scripts with arguments after downloads

## Requirements

- Python

## Usage

The script is designed to be reusable.
Simply download update_github_apps.py and use it with multiple config files:

**Step 1: Download**

1. Navigate to the main page of this repository on GitHub
2. Open the update_github_apps.py file by clicking on it
3. Click the **Download raw file** button near the top right of the file view, next to the Raw and Copy raw file buttons

**Step 2: Run the script**

You will need a config file for this script to work

```bash
cd /path/to/script_dir
chmod +x update_github_apps.py
# By Default it looks for updater_config.json config file in the current working directory
./update_github_apps.py
```

## Configuration

Create a `updater_config.json` file in a directory:

```json
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
      "post_download_hook": "./hooks/test_hook.sh",
      "post_download_hook_args": ["--arg1", "--arg2"]
    }
  ]
}
```

**Important: All relative paths are relative to the config file location.**

```
/home/user/directory/
├── updater_config.json          # Config file here
├── downloads/                   # install_path: "./downloads/app.zip"
├── .trash/                      # trash_config.trash_path: ".trash"
└── hooks/                       # post_download_hook: "./hooks/extract.sh"

/home/user/bin/
└── update_github_apps.py        # Script can be anywhere
```

### Configuration Fields

| Field                     | Required | Description                                                                    |
| ------------------------- | -------- | ------------------------------------------------------------------------------ |
| `trash_config`            | No       | trash configuration for old versions (defaults path to ".trash")               |
| `github_token`            | No       | GitHub personal access token for authentication                                |
| `name`                    | Yes      | Display name for the app                                                       |
| `repo`                    | Yes      | GitHub repository in format "owner/repo"                                       |
| `tag`                     | Yes      | Current installed tag/version (can be empty string for new apps)               |
| `asset_pattern`           | Yes      | Fixed filename, regex pattern, or template with `{tag}` placeholder            |
| `asset_match_type`        | Yes      | `"fixed"` for exact match, `"regex"` for pattern, `"tag"` for tag substitution |
| `install_path`            | Yes      | Where to save the file                                                         |
| `use_prerelease`          | No       | `true` to check pre-releases, `false` for stable only (default: `false`)       |
| `post_download_hook`      | No       | Command or script to run after successful download                             |
| `post_download_hook_args` | No       | Argumentst to pass to the post download hook                                   |

## Asset Match Types

The script supports three ways to match asset files:

### 1. Fixed Match (`"asset_match_type": "fixed"`)

Exact string matching - the asset name must match exactly.

**Use when:** Asset name never changes between versions.

```json
{
  "asset_pattern": "app-release.zip",
  "asset_match_type": "fixed"
}
```

Matches: `app-release.zip` ✓  
Doesn't match: `app-release-v1.0.zip` ✗

### 2. Tag Substitution (`"asset_match_type": "tag"`)

Template with `{tag}` placeholder that gets replaced with the version.

**Use when:** Asset name includes the version tag (the most common case for versioned releases).

```json
{
  "asset_pattern": "app-{tag}-linux.zip",
  "asset_match_type": "tag"
}
```

Tag `v1.5.0`:  
Matches: `app-1.5.0-linux.zip` ✓ (strips 'v')  
Matches: `app-v1.5.0-linux.zip` ✓ (keeps 'v')

**Tag substitution automatically handles both `v1.0` and `1.0` tag formats!**

### 3. Regex Match (`"asset_match_type": "regex"`)

Pattern matching using regular expressions.

**Use when:** Asset names vary in complex ways (version numbers, suffixes, etc.).

```json
{
  "asset_pattern": "^myapp-v[0-9]+\\.[0-9]+\\.[0-9]+-linux\\.tar\\.gz$",
  "asset_match_type": "regex"
}
```

Matches: `myapp-v1.2.3-linux.tar.gz` ✓  
Matches: `myapp-v2.0.0-linux.tar.gz` ✓  
Doesn't match: `myapp-v1.2-windows.exe` ✗

## Post-Download Hooks

Post-download hooks allow you to run custom scripts after a file is successfully downloaded. This is useful for:

- Extracting archives (zip, tar.gz, etc.)
- Moving files to specific locations
- Running installation scripts
- Sending notifications
- Custom post-processing

### Hook Execution

Hooks are executed with:

- Shell environment variables containing download information
- Working directory = script directory
- 5 minute timeout
- Output printed to terminal

You can view example hooks in the hooks directory of this project

## GitHub Authentication

By default, the script uses unauthenticated requests. For higher limits or private repositories, use a GitHub personal access token.

### Rate Limits

| Method          | Requests/Hour |
| --------------- | ------------- |
| Unauthenticated | 60            |
| Authenticated   | 5,000         |

### Options to pass a github token

**Option 1: Environment Variable (Recommended)**

```bash
export GITHUB_TOKEN=ghp_your_token_here
python3 update_github_apps.py
```

**Option 2: Secure Prompt (Most Secure)**

```bash
python3 update_github_apps.py --token-prompt
# Enter GitHub token: [hidden input]
```

**Option 3: Config File**

```json
{
  "github_token": "ghp_your_token_here",
  "apps": [...]
}
```

## Troubleshooting

### "No matching asset found"

- Check your `asset_pattern` is correct
- For regex, test your pattern at https://regex101.com/
- Look at the actual release on GitHub to see exact asset names
- Remember to escape backslashes in JSON: `\.` → `\\.`

### "GitHub API error"

- Check your internet connection
- Verify the repo name is correct (format: `owner/repo`)
- GitHub API has rate limits (60 requests/hour for unauthenticated)

### "File not found" after download

- Check that `install_path` is correct
- Make sure you have write permissions to the directory
- For relative paths, they're relative to the config directory

## License

This script is provided as-is for personal use. Feel free to modify and distribute.
