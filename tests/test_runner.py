import textwrap

import pytest

from labctl import catalog, runner

CHECK = '''
from labctl.checks import task, expect, skip, sh

@task("passes")
def a():
    expect(sh("true").ok, "true should succeed")

@task("fails with a message")
def b():
    expect(False, "nginx is not running")

@task("skipped counts as passed")
def c():
    skip("not applicable")

@task("checker bug is reported as error")
def d():
    {}["missing"]
'''


@pytest.fixture
def fake_lab(tmp_path):
    root = tmp_path / "labs"
    lab_dir = root / "demo" / "demo-01"
    lab_dir.mkdir(parents=True)
    (root / "tracks.yaml").write_text("- {id: demo, name: Demo, blurb: x}\n")
    (lab_dir / "lab.yaml").write_text(textwrap.dedent("""
        id: demo-01
        title: Demo
        track: demo
        order: 1
        minutes: 5
        scenario: s
        steps: [{text: do it}]
        verify: [{run: 'true', expect: ok}]
        hints: [h]
        solution: [{text: s}]
    """))
    (lab_dir / "check.py").write_text(CHECK)
    return root


def test_results(fake_lab, monkeypatch):
    monkeypatch.setenv("LAB_DRILLS_LABS", str(fake_lab))
    lab = catalog.find("demo-01")
    results = runner.run_tasks(runner.load_tasks(lab))
    assert [r.status for r in results] == ["pass", "fail", "skip", "error"]
    assert results[1].message == "nginx is not running"
    assert "KeyError" in results[3].message
    assert sum(r.passed for r in results) == 2


def test_fail_fast(fake_lab, monkeypatch):
    monkeypatch.setenv("LAB_DRILLS_LABS", str(fake_lab))
    lab = catalog.find("demo-01")
    assert len(runner.run_tasks(runner.load_tasks(lab), fail_fast=True)) == 2


def test_cli_check_exit_code_and_progress(fake_lab, monkeypatch, capsys):
    from labctl import cli, progress
    monkeypatch.setenv("LAB_DRILLS_LABS", str(fake_lab))
    with pytest.raises(SystemExit) as exc:
        cli.main(["check", "demo-01"])
    assert exc.value.code == 1
    assert "2/4 tasks passed" in capsys.readouterr().out
    assert progress.load()["demo-01"]["best"] == 2
