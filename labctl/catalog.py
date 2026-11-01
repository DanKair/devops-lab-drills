"""Find and load lab definitions (labs/<track>/<id>/lab.yaml)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

REQUIRED = ("id", "title", "track", "order", "minutes", "scenario", "steps", "verify", "hints", "solution")


def labs_root() -> Path:
    env = os.environ.get("LAB_DRILLS_LABS")
    if env:
        return Path(env).expanduser()
    here = Path(__file__).resolve().parent
    for candidate in (here / "labs", here.parent / "labs"):  # installed wheel, then repo checkout
        if (candidate / "tracks.yaml").exists():
            return candidate
    raise FileNotFoundError("Could not find the labs folder. Set LAB_DRILLS_LABS to the repo's labs/ path.")


@dataclass
class Lab:
    id: str
    title: str
    track: str
    order: int
    minutes: int
    breakfix: bool
    dir: Path
    data: dict = field(repr=False)

    @property
    def check_file(self) -> Path:
        return self.dir / "check.py"

    @property
    def setup_file(self) -> Path:
        return self.dir / "setup.sh"

    @property
    def reset_file(self) -> Path:
        return self.dir / "reset.sh"

    @property
    def has_setup(self) -> bool:
        return self.setup_file.exists()

    @property
    def has_reset(self) -> bool:
        return self.reset_file.exists()


def load_lab(path: Path) -> Lab:
    data = yaml.safe_load(path.read_text())
    missing = [k for k in REQUIRED if k not in data]
    if missing:
        raise ValueError(f"{path}: missing keys {missing}")
    return Lab(
        id=data["id"], title=data["title"], track=data["track"], order=int(data["order"]),
        minutes=int(data["minutes"]), breakfix=bool(data.get("breakfix")), dir=path.parent, data=data,
    )


@lru_cache(maxsize=1)
def tracks() -> list[dict]:
    return yaml.safe_load((labs_root() / "tracks.yaml").read_text())


@lru_cache(maxsize=1)
def all_labs() -> list[Lab]:
    labs = [load_lab(p) for p in labs_root().glob("*/*/lab.yaml")]
    return sorted(labs, key=lambda lab: lab.order)


def find(query: str) -> Lab:
    labs = all_labs()
    exact = [lab for lab in labs if lab.id == query]
    if exact:
        return exact[0]
    if query.isdigit():
        by_order = [lab for lab in labs if lab.order == int(query)]
        if by_order:
            return by_order[0]
    prefix = [lab for lab in labs if lab.id.startswith(query)]
    if len(prefix) == 1:
        return prefix[0]
    if prefix:
        raise LookupError(f"'{query}' matches several labs: {', '.join(lab.id for lab in prefix)}")
    raise LookupError(f"No lab called '{query}'. Run `lab list` to see all labs.")
