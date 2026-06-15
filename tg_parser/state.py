import json
import os
import pathlib
import datetime
from typing import Set


STATE_DIR = pathlib.Path("output/state")


def _state_path(group_id: int) -> pathlib.Path:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    return STATE_DIR / f"group_{group_id}.json"


def load_state(group_id: int) -> dict:
    path = _state_path(group_id)
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"group_id": group_id, "last_offset": 0, "fetched_ids": []}


def save_state(group_id: int, last_offset: int, fetched_ids: Set[int]) -> None:
    path = _state_path(group_id)
    tmp = pathlib.Path(str(path) + ".tmp")
    data = {
        "group_id": group_id,
        "last_offset": last_offset,
        "fetched_ids": list(fetched_ids),
        "updated_at": datetime.datetime.utcnow().isoformat(),
    }
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def get_fetched_ids(group_id: int) -> Set[int]:
    state = load_state(group_id)
    return set(state.get("fetched_ids", []))
