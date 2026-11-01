"""Local progress store (~/.labdrills/progress.json)."""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone

from . import config


def _file():
    return config.home() / "progress.json"


def load() -> dict:
    try:
        return json.loads(_file().read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save(data: dict) -> None:
    config.home().mkdir(parents=True, exist_ok=True)
    tmp = _file().with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
    tmp.replace(_file())


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def entry(data: dict, lab_id: str) -> dict:
    return data.setdefault(lab_id, {"attempts": 0, "best": 0, "total": 0, "done": False, "hints": 0, "solution": False})


def record_check(lab_id: str, passed: int, total: int) -> dict:
    data = load()
    e = entry(data, lab_id)
    e["attempts"] += 1
    e["total"] = total
    e["best"] = max(e["best"], passed)
    e["last"] = passed
    e["last_check"] = now()
    if total and passed == total and not e["done"]:
        e["done"] = True
        e["done_at"] = now()
    save(data)
    return e


def mark(lab_id: str, **fields) -> dict:
    data = load()
    e = entry(data, lab_id)
    e.update(fields)
    save(data)
    return e


def bump_hints(lab_id: str) -> int:
    data = load()
    e = entry(data, lab_id)
    e["hints"] += 1
    save(data)
    return e["hints"]


def export_code() -> str:
    data = load()
    payload = {"v": 1, "done": sorted(k for k, v in data.items() if v.get("done"))}
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return "LD1." + base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_code(code: str) -> dict:
    if not code.startswith("LD1."):
        raise ValueError("not a progress code")
    body = code[4:]
    body += "=" * (-len(body) % 4)
    return json.loads(base64.urlsafe_b64decode(body))
