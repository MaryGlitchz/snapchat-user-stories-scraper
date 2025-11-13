import json
import logging
import os
from typing import Any, Dict, List

def ensure_parent_dir(path: str) -> None:
    directory = os.path.dirname(os.path.abspath(path))
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)

def export_to_json(
    records: List[Dict[str, Any]],
    output_path: str,
    pretty: bool = False,
) -> None:
    """
    Export the list of story highlight records to a JSON file.
    """
    ensure_parent_dir(output_path)

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            if pretty:
                json.dump(records, f, ensure_ascii=False, indent=2)
            else:
                json.dump(records, f, ensure_ascii=False, separators=(",", ":"))
        logging.info("Exported %d record(s) to %s", len(records), output_path)
    except OSError as e:
        logging.error("Failed to write JSON output to '%s': %s", output_path, e)
        raise