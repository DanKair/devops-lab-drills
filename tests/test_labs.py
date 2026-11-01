"""Schema checks for every lab in labs/: these run in CI so a broken lab never ships."""
import re

import pytest

from labctl import catalog, runner

LABS = catalog.all_labs()


def test_ids_unique_and_match_folders():
    ids = [lab.id for lab in LABS]
    assert len(ids) == len(set(ids))
    for lab in LABS:
        assert lab.dir.name == lab.id
        assert lab.dir.parent.name == lab.track


def test_order_is_contiguous():
    assert [lab.order for lab in LABS] == list(range(1, len(LABS) + 1))


def test_tracks_exist():
    track_ids = {t["id"] for t in catalog.tracks()}
    assert {lab.track for lab in LABS} <= track_ids


@pytest.mark.parametrize("lab", LABS, ids=lambda lab: lab.id)
def test_lab_has_checks(lab):
    assert lab.check_file.exists(), f"{lab.id} has no check.py"
    tasks = runner.load_tasks(lab)
    assert tasks, f"{lab.id}: check.py registers no @task"
    assert len({t.title for t in tasks}) == len(tasks), "duplicate task titles"


@pytest.mark.parametrize("lab", LABS, ids=lambda lab: lab.id)
def test_lab_content(lab):
    d = lab.data
    assert d["steps"] and d["verify"] and d["hints"] and d["solution"]
    for s in d["steps"]:
        assert s.get("text") or s.get("code")


@pytest.mark.parametrize("lab", [lab for lab in LABS if lab.breakfix], ids=lambda lab: lab.id)
def test_breakfix_has_setup(lab):
    assert lab.has_setup, f"break-fix lab {lab.id} needs setup.sh"
    script = lab.setup_file.read_text()
    for ref in re.findall(r'\$LAB_DIR/([\w./-]+)', script):
        assert (lab.dir / ref).exists(), f"{lab.id}/setup.sh references missing file {ref}"
