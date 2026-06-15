import csv
import json
import os
import pathlib
import re
from typing import List

from .models import MemberRecord

OUTPUT_DIR = pathlib.Path("output")


def _slug(title: str) -> str:
    s = re.sub(r"[^\w\s-]", "", title.lower())
    s = re.sub(r"[\s_-]+", "_", s)
    return s[:40].strip("_")


def export(records: List[MemberRecord], group_id: int, group_title: str) -> tuple[str, str]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    base = OUTPUT_DIR / f"{_slug(group_title)}_{group_id}"
    csv_path = str(base) + ".csv"
    json_path = str(base) + ".json"

    rows = [r.to_dict() for r in records]

    # CSV
    if rows:
        tmp_csv = pathlib.Path(csv_path + ".tmp")
        with open(tmp_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        os.replace(tmp_csv, csv_path)

    # JSON
    tmp_json = pathlib.Path(json_path + ".tmp")
    with open(tmp_json, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    os.replace(tmp_json, json_path)

    return csv_path, json_path
