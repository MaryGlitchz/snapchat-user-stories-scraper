import argparse
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional

import requests

# Ensure local module imports work even when running as `python src/runner.py`
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)

EXTRACTORS_DIR = os.path.join(CURRENT_DIR, "extractors")
OUTPUTS_DIR = os.path.join(CURRENT_DIR, "outputs")

for _path in (EXTRACTORS_DIR, OUTPUTS_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from snapchat_parser import SnapchatStoryParser  # type: ignore
from exporters import export_to_json  # type: ignore  # noqa: E402

def load_settings(settings_path: str) -> Dict[str, Any]:
    if not os.path.exists(settings_path):
        logging.warning(
            "Settings file '%s' not found. Falling back to built-in defaults.",
            settings_path,
        )
        return {
            "snapchat_base_url": "https://story.snapchat.com",
            "request_timeout_seconds": 15,
            "proxies": None,
            "verify_ssl": True,
        }

    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            settings = json.load(f)
        logging.info("Loaded settings from %s", settings_path)
        return settings
    except json.JSONDecodeError as e:
        logging.error("Failed to parse settings JSON: %s", e)
        raise SystemExit(1)

def load_usernames(usernames_path: str) -> List[str]:
    if not os.path.exists(usernames_path):
        logging.error("Usernames file '%s' does not exist.", usernames_path)
        raise SystemExit(1)

    usernames: List[str] = []
    with open(usernames_path, "r", encoding="utf-8") as f:
        for line in f:
            username = line.strip()
            if not username or username.startswith("#"):
                continue
            usernames.append(username)

    if not usernames:
        logging.error("No usernames found in '%s'.", usernames_path)
        raise SystemExit(1)

    logging.info("Loaded %d usernames from %s", len(usernames), usernames_path)
    return usernames

def fetch_story_page(
    session: requests.Session,
    base_url: str,
    username: str,
    timeout: int,
    proxies: Optional[Dict[str, str]],
    verify_ssl: bool,
) -> Optional[str]:
    """
    Fetches the public Snapchat story page HTML for a given username.

    This uses `https://story.snapchat.com/@{username}`, which is the public
    stories page in most regions. The exact structure may change over time.
    """
    url = f"{base_url.rstrip('/')}/@{username}"
    try:
        logging.info("Fetching stories page for username '%s' ...", username)
        response = session.get(
            url,
            timeout=timeout,
            proxies=proxies,
            verify=verify_ssl,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36"
                )
            },
        )
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        logging.error("Failed to fetch stories for '%s': %s", username, e)
        return None

def aggregate_stories(
    usernames: List[str],
    settings: Dict[str, Any],
) -> List[Dict[str, Any]]:
    base_url = settings.get("snapchat_base_url", "https://story.snapchat.com")
    timeout = int(settings.get("request_timeout_seconds", 15))
    proxies = settings.get("proxies") or None
    verify_ssl = bool(settings.get("verify_ssl", True))

    parser = SnapchatStoryParser()
    all_results: List[Dict[str, Any]] = []

    with requests.Session() as session:
        for username in usernames:
            html = fetch_story_page(
                session=session,
                base_url=base_url,
                username=username,
                timeout=timeout,
                proxies=proxies,
                verify_ssl=verify_ssl,
            )
            if html is None:
                continue

            try:
                parsed = parser.parse_from_html(html, username=username)
                logging.info(
                    "Parsed %d story highlight(s) for '%s'.",
                    len(parsed),
                    username,
                )
                all_results.extend(parsed)
            except Exception as e:  # noqa: BLE001
                logging.exception(
                    "Unexpected error while parsing stories for '%s': %s",
                    username,
                    e,
                )

    return all_results

def parse_args() -> argparse.Namespace:
    default_usernames = os.path.join(PROJECT_ROOT, "data", "usernames.sample.txt")
    default_output = os.path.join(PROJECT_ROOT, "data", "sample_output.json")
    default_settings = os.path.join(CURRENT_DIR, "config", "settings.example.json")

    parser = argparse.ArgumentParser(
        description="Snapchat User Stories Scraper - CLI runner."
    )
    parser.add_argument(
        "--usernames-file",
        type=str,
        default=default_usernames,
        help=f"Path to a text file with Snapchat usernames (one per line). "
        f"Default: {default_usernames}",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default=default_output,
        help=f"Path to the JSON output file. Default: {default_output}",
    )
    parser.add_argument(
        "--settings",
        type=str,
        default=default_settings,
        help=f"Path to the JSON settings file. Default: {default_settings}",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )
    return parser.parse_args()

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(message)s",
    )

    args = parse_args()

    settings = load_settings(args.settings)
    usernames = load_usernames(args.usernames_file)

    logging.info("Starting Snapchat User Stories Scraper for %d usernames ...", len(usernames))
    results = aggregate_stories(usernames, settings)

    if not results:
        logging.warning(
            "No stories were parsed. "
            "Verify that the usernames are public and the Snapchat page format is supported."
        )

    export_to_json(results, args.output_file, pretty=args.pretty)
    logging.info("Finished. Wrote %d story highlight(s) to %s.", len(results), args.output_file)

if __name__ == "__main__":
    main()