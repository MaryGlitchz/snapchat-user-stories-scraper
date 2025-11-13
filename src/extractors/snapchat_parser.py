import json
import logging
import re
from typing import Any, Dict, List, Union

from utils_time import normalize_timestamp

JsonType = Union[Dict[str, Any], List[Any], str, int, float, bool, None]

class SnapchatStoryParser:
    """
    Parser for extracting Snapchat story data from public HTML pages.

    The public stories site typically embeds JSON data in a JavaScript object.
    This parser tries to be resilient to changes by:
      - Searching for JSON fragments containing "snapList".
      - Recursively walking the JSON tree to collect story-like objects.

    Returned structure:

    [
      {
        "snapList": [
          {
            "snapIndex": int,
            "createTime": str (ISO8601),
            "mediaPreviewUrl": str,
            "mediaUrl": str
          },
          ...
        ],
        "storyTitle": str,
        "thumbnailUrl": str,
        "highlightId": str,
        "username": str
      },
      ...
    ]
    """

    _JSON_FRAGMENT_RE = re.compile(
        r"({[^{}]*\"snapList\"[^{}]*})", re.DOTALL | re.IGNORECASE
    )

    _STATE_RE = re.compile(
        r"__INITIAL_STATE__\s*=\s*({.*?})\s*;</",
        re.DOTALL | re.IGNORECASE,
    )

    def parse_from_html(self, html: str, username: str) -> List[Dict[str, Any]]:
        # First try to parse a large JSON state object
        state_json = self._extract_state_json(html)
        if state_json is not None:
            logging.debug("Found __INITIAL_STATE__ JSON blob.")
            return self._extract_stories_from_json(state_json, username)

        # Fallback: search for smaller standalone fragments containing "snapList"
        fragments = self._extract_json_fragments(html)
        results: List[Dict[str, Any]] = []
        for frag in fragments:
            try:
                data = json.loads(frag)
            except json.JSONDecodeError:
                continue
            results.extend(self._extract_stories_from_json(data, username))

        # De-duplicate highlights by (highlightId, username)
        dedup: Dict[str, Dict[str, Any]] = {}
        for item in results:
            key = f"{item.get('highlightId')}-{item.get('username')}"
            if key not in dedup:
                dedup[key] = item

        return list(dedup.values())

    def _extract_state_json(self, html: str) -> JsonType:
        match = self._STATE_RE.search(html)
        if not match:
            return None
        raw = match.group(1)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logging.debug("Failed to parse __INITIAL_STATE__ JSON.")
            return None

    def _extract_json_fragments(self, html: str) -> List[str]:
        fragments = [m.group(1) for m in self._JSON_FRAGMENT_RE.finditer(html)]
        logging.debug("Found %d potential JSON fragment(s) with 'snapList'.", len(fragments))
        return fragments

    def _extract_stories_from_json(
        self,
        data: JsonType,
        username: str,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        self._walk_json(data, username=username, out=results)
        return results

    def _walk_json(
        self,
        node: JsonType,
        username: str,
        out: List[Dict[str, Any]],
    ) -> None:
        if isinstance(node, dict):
            # Check if this dict looks like a story highlight object
            if "snapList" in node and isinstance(node["snapList"], list):
                highlight = self._build_highlight(node, username)
                out.append(highlight)

            # Recurse into values
            for value in node.values():
                self._walk_json(value, username=username, out=out)

        elif isinstance(node, list):
            for item in node:
                self._walk_json(item, username=username, out=out)

    def _build_highlight(self, obj: Dict[str, Any], username: str) -> Dict[str, Any]:
        raw_snap_list = obj.get("snapList") or []
        snap_list: List[Dict[str, Any]] = []

        for idx, snap in enumerate(raw_snap_list):
            if not isinstance(snap, dict):
                continue

            snap_index = snap.get("snapIndex", idx)
            create_raw = snap.get("createTime")
            create_time = normalize_timestamp(create_raw)

            snap_list.append(
                {
                    "snapIndex": snap_index,
                    "createTime": create_time,
                    "mediaPreviewUrl": snap.get("mediaPreviewUrl")
                    or snap.get("mediaUrl")
                    or "",
                    "mediaUrl": snap.get("mediaUrl") or "",
                }
            )

        highlight_id = obj.get("highlightId") or obj.get("id") or ""
        story_title = obj.get("storyTitle") or obj.get("title") or ""
        thumbnail_url = obj.get("thumbnailUrl") or obj.get("thumbnail") or ""

        return {
            "snapList": snap_list,
            "storyTitle": story_title,
            "thumbnailUrl": thumbnail_url,
            "highlightId": highlight_id,
            "username": username,
        }