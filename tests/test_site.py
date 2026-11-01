import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import build_site

from labctl import catalog


def test_site_builds(tmp_path):
    index = build_site.build("https://github.com/u/devops-lab-drills", tmp_path)
    html = index.read_text()
    assert html.startswith("<!doctype html>")
    blob = re.search(r"const DATA = (.*?);\n", html).group(1)
    data = json.loads(blob.replace("<\\/", "</"))
    assert len(data["labs"]) == len(catalog.all_labs())
    assert all(lab["checks"] for lab in data["labs"])
    assert "</script" not in blob  # data cannot close the script tag early
    assert (tmp_path / ".nojekyll").exists()
