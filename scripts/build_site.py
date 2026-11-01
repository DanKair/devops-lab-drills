"""Build the static website from labs/ into _site/index.html.

Usage: python scripts/build_site.py [--repo https://github.com/<you>/devops-lab-drills] [--out _site]
In GitHub Actions the repo URL is taken from GITHUB_REPOSITORY automatically.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from labctl import catalog  # noqa: E402


def md(text: str) -> str:
    return markdown.markdown(text or "", extensions=["tables"])


def check_titles(path: Path) -> list[str]:
    """Read @task("...") titles without importing the check file."""
    tree = ast.parse(path.read_text())
    titles = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            for dec in node.decorator_list:
                if (isinstance(dec, ast.Call) and getattr(dec.func, "id", "") == "task" and dec.args
                        and isinstance(dec.args[0], ast.Constant)):
                    titles.append(dec.args[0].value)
    return titles


def lab_payload(lab: catalog.Lab) -> dict:
    d = lab.data
    return {
        "id": lab.id, "title": lab.title, "track": lab.track, "minutes": lab.minutes,
        "breakfix": lab.breakfix, "has_setup": lab.has_setup,
        "scenario": md(d["scenario"]),
        "steps": [{"html": md(s.get("text", "")), "code": s.get("code"), "lang": s.get("lang")} for s in d["steps"]],
        "verify": [{"run": v["run"], "html": md(v["expect"])} for v in d["verify"]],
        "hints": [md(h) for h in d["hints"]],
        "solution": [{"html": md(s.get("text", "")), "code": s.get("code"), "lang": s.get("lang")}
                     for s in d["solution"]],
        "checks": check_titles(lab.check_file),
    }


def build(repo: str, out: Path) -> Path:
    data = {"repo": repo.rstrip("/"), "tracks": catalog.tracks(),
            "labs": [lab_payload(lab) for lab in catalog.all_labs()]}
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    site = ROOT / "site"
    html = (site / "head.html").read_text() + (site / "body.html").read_text().replace(
        "/*__DATA__*/", f"const DATA = {blob};")
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(html)
    (out / ".nojekyll").write_text("")
    return out / "index.html"


def main() -> None:
    gh = os.environ.get("GITHUB_REPOSITORY")
    default_repo = f"https://github.com/{gh}" if gh else "https://github.com/YOUR-USER/devops-lab-drills"
    p = argparse.ArgumentParser()
    p.add_argument("--repo", default=default_repo)
    p.add_argument("--out", default=str(ROOT / "_site"))
    a = p.parse_args()
    path = build(a.repo, Path(a.out))
    print(f"Built {path} ({path.stat().st_size // 1024} KB, {len(catalog.all_labs())} labs)")


if __name__ == "__main__":
    main()
