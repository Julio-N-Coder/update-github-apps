#!/usr/bin/env python3
"""
Mock GitHub API Server
Simulates GitHub API endpoints for local testing without hitting rate limits

Usage:
    python3 mock_github_api.py [--port PORT]

Default port: 8080

Configure mock data by editing the MOCK_REPOS dictionary.
"""

import json
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
import argparse


class Colors:
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    LIGHT_BLUE = "\033[0;36m"
    YELLOW = "\033[1;33m"
    NC = "\033[0m"  # No Color


# Mock data for repositories
MOCK_REPOS = {
    "mockorg/variable-asset-app": {
        "releases": [
            {
                "tag_name": "v3.2.1",
                "name": "Variable Asset App 3.2.1",
                "prerelease": False,
                "assets": [
                    {
                        "name": "variable-asset-app-3.2.1-hotfix2.zip",
                        "browser_download_url": "http://localhost:8080/mock-download/variable-asset-app-3.2.1-hotfix2.zip",
                        "size": 1024000,
                    }
                ],
            },
            {
                "tag_name": "v3.2.0",
                "name": "Variable Asset App 3.2.0",
                "prerelease": False,
                "assets": [
                    {
                        "name": "variable-asset-app-3.2.0.zip",
                        "browser_download_url": "http://localhost:8080/mock-download/variable-asset-app-3.2.0.zip",
                        "size": 1020000,
                    }
                ],
            },
            {
                "tag_name": "v3.3.0-beta.1",
                "name": "Variable Asset App 3.3.0 Beta 1",
                "prerelease": True,
                "assets": [
                    {
                        "name": "variable-asset-app-3.3.0-beta.1.zip",
                        "browser_download_url": "http://localhost:8080/mock-download/variable-asset-app-3.3.0-beta.1.zip",
                        "size": 1030000,
                    }
                ],
            },
        ]
    },
    "test-owner/test-app": {
        "releases": [
            {
                "tag_name": "v1.5.0",
                "name": "Test App 1.5.0",
                "prerelease": False,
                "assets": [
                    {
                        "name": "test-app-v1.5.0-linux.tar.gz",
                        "browser_download_url": "http://localhost:8080/mock-download/test-app-v1.5.0-linux.tar.gz",
                        "size": 2048000,
                    },
                    {
                        "name": "test-app-v1.5.0-windows.exe",
                        "browser_download_url": "http://localhost:8080/mock-download/test-app-v1.5.0-windows.exe",
                        "size": 3072000,
                    },
                ],
            },
            {
                "tag_name": "v1.4.0",
                "name": "Test App 1.4.0",
                "prerelease": False,
                "assets": [
                    {
                        "name": "test-app-v1.4.0-linux.tar.gz",
                        "browser_download_url": "http://localhost:8080/mock-download/test-app-v1.4.0-linux.tar.gz",
                        "size": 2000000,
                    }
                ],
            },
        ]
    },
    "another-owner/fixed-name-app": {
        "releases": [
            {
                "tag_name": "v3.2.1",
                "name": "Fixed Name App 3.2.1",
                "prerelease": False,
                "assets": [
                    {
                        "name": "app-release.zip",
                        "browser_download_url": "http://localhost:8080/mock-download/app-release.zip",
                        "size": 5000000,
                    }
                ],
            }
        ]
    },
    "mockorg/tag-template-app": {
        "releases": [
            {
                "tag_name": "v2.3.0",
                "name": "Tag Template App 2.3.0",
                "prerelease": False,
                "assets": [
                    {
                        "name": "template-app-2.3.0-linux.tar.gz",
                        "browser_download_url": "http://localhost:8080/mock-download/template-app-2.3.0-linux.tar.gz",
                        "size": 3500000,
                    },
                    {
                        "name": "template-app-2.3.0-windows.exe",
                        "browser_download_url": "http://localhost:8080/mock-download/template-app-2.3.0-windows.exe",
                        "size": 4000000,
                    },
                ],
            },
            {
                "tag_name": "v2.2.5",
                "name": "Tag Template App 2.2.5",
                "prerelease": False,
                "assets": [
                    {
                        "name": "template-app-2.2.5-linux.tar.gz",
                        "browser_download_url": "http://localhost:8080/mock-download/template-app-2.2.5-linux.tar.gz",
                        "size": 3400000,
                    }
                ],
            },
        ]
    },
}


class MockGitHubAPIHandler(BaseHTTPRequestHandler):
    """HTTP request handler that mimics GitHub API responses."""

    def log_message(self, format, *args):
        """Override to add color to logs."""
        print(f"{Colors.LIGHT_BLUE}[MOCK API]{Colors.NC} {format % args}")

    def send_json_response(self, data, status=200):
        """Send a JSON response."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode("utf-8"))

    def send_error_response(self, message, status=404):
        """Send an error response."""
        self.send_json_response({"message": message}, status)

    def send_mock_file(self, filename):
        """Send a mock file download (just dummy data)."""
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        # Send dummy data (repeating "MOCK DATA" to simulate a file)
        mock_data = f"MOCK FILE DATA for {filename}\n".encode("utf-8") * 1000
        self.wfile.write(mock_data)

    def do_GET(self):
        """Handle GET requests."""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        path = path.rstrip("/")

        # Handle mock file downloads
        if path.startswith("/mock-download/"):
            filename = path.split("/")[-1]
            self.log_message(f"Serving mock download: {filename}")
            self.send_mock_file(filename)
            return

        # Parse GitHub API paths
        # Format: /repos/{owner}/{repo}/releases or /repos/{owner}/{repo}/releases/latest
        parts = path.split("/")

        # Status check for utils script
        if len(parts) == 2 and parts[-1] == "status":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"Status: UP\n")
            return

        if len(parts) < 5 or parts[1] != "repos":
            self.send_error_response("Invalid API endpoint", 404)
            return

        owner = parts[2]
        repo = parts[3]
        repo_key = f"{owner}/{repo}"

        # Check if this repo is in our mock data
        if repo_key not in MOCK_REPOS:
            self.send_error_response(
                f"Repository {repo_key} not found in mock data", 404
            )
            return

        releases = MOCK_REPOS[repo_key]["releases"]

        # Handle /repos/{owner}/{repo}/releases/latest
        if len(parts) >= 6 and parts[5] == "latest":
            # Get the latest non-prerelease
            latest = None
            for release in releases:
                if not release.get("prerelease", False):
                    latest = release
                    break

            if latest:
                self.log_message(
                    f"Serving latest release for {repo_key}: {latest['tag_name']}"
                )
                self.send_json_response(latest)
            else:
                self.send_error_response("No releases found", 404)
            return

        # Handle /repos/{owner}/{repo}/releases (all releases)
        if len(parts) >= 5 and parts[4] == "releases":
            self.log_message(f"Serving all releases for {repo_key}")
            self.send_json_response(releases)
            return

        self.send_error_response("Unknown endpoint", 404)

    def do_HEAD(self):
        """Handle HEAD requests (same as GET but no body)."""
        self.do_GET()


def run_server(port=8080):
    """Run the mock GitHub API server."""
    server_address = ("localhost", port)
    httpd = HTTPServer(server_address, MockGitHubAPIHandler)

    print("=" * 60)
    print("  Mock GitHub API Server")
    print("=" * 60)
    print(f"\n{Colors.GREEN}✓ Server running on http://localhost:{port}{Colors.NC}\n")
    print("Available mock repositories:")
    for repo in MOCK_REPOS.keys():
        print(f"  • {repo}")
    print("\nEndpoints:")
    print(f"  • http://localhost:{port}/repos/{{owner}}/{{repo}}/releases")
    print(f"  • http://localhost:{port}/repos/{{owner}}/{{repo}}/releases/latest")
    print("\nTo use with updater script:")
    print(f"  export GITHUB_API_BASE_URL=http://localhost:{port}")
    print(f"  python3 update_github_apps.py")
    print("\n  OR")
    print(f"  python3 update_github_apps.py --mock-api http://localhost:{port}")
    print("\nPress Ctrl+C to stop the server\n")
    print("=" * 60)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Shutting down server...{Colors.NC}")
        httpd.shutdown()
        print(f"{Colors.GREEN}✓ Server stopped{Colors.NC}\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Mock GitHub API Server for testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 mock_github_api.py                 # Run on default port 8080
  python3 mock_github_api.py --port 9000     # Run on custom port
  
Edit the MOCK_REPOS dictionary in this file to add your own test repositories.
        """,
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=8080,
        help="Port to run the server on (default: 8080)",
    )

    args = parser.parse_args()

    try:
        run_server(args.port)
    except OSError as e:
        if e.errno == 48 or e.errno == 98:  # Address already in use
            print(
                f"\n{Colors.RED}✗ Error: Port {args.port} is already in use{Colors.NC}"
            )
            print(
                f"Try a different port: python3 mock_github_api.py --port {args.port + 1}\n"
            )
            sys.exit(1)
        else:
            raise


if __name__ == "__main__":
    main()
