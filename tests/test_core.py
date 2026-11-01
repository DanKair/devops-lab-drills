import os
import stat

import pytest

from labctl import catalog, checks, cli, config, progress


def test_find_by_id_prefix_and_number():
    assert catalog.find("ans-01").id == "ans-01"
    assert catalog.find("tf-fix").id == "tf-fix-01"
    assert catalog.find("1").id == "setup-01"
    with pytest.raises(LookupError):
        catalog.find("k8s-fix")  # ambiguous
    with pytest.raises(LookupError):
        catalog.find("nope")


def test_progress_done_and_export_roundtrip():
    progress.record_check("ans-01", 3, 5)
    assert not progress.load()["ans-01"]["done"]
    progress.record_check("ans-01", 5, 5)
    e = progress.load()["ans-01"]
    assert e["done"] and e["attempts"] == 2 and e["best"] == 5
    assert progress.decode_code(progress.export_code())["done"] == ["ans-01"]


def test_config_secret_file_is_private(monkeypatch):
    config.set_value("gitlab_token", "glpat-secret-value")
    f = config.home() / "config.json"
    assert stat.S_IMODE(os.stat(f).st_mode) == 0o600
    assert config.get("gitlab_token") == "glpat-secret-value"
    shown = {k: v for k, v, _ in config.show()}
    assert "secret-value" not in shown["gitlab_token"]
    monkeypatch.setenv("LAB_GITLAB_TOKEN", "from-env")
    assert config.get("gitlab_token") == "from-env"


def test_capstone_project_defaults_to_gitlab_project():
    config.set_value("gitlab_project", "kair/app")
    assert config.get("capstone_project") == "kair/app"


def test_ansible_recap():
    out = """PLAY RECAP *********
node1                      : ok=4    changed=1    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
node2                      : ok=2    changed=0    unreachable=1    failed=0    skipped=0    rescued=0    ignored=0
"""
    recap = checks.ansible_recap(out)
    assert recap["node1"]["changed"] == 1
    assert recap["node2"]["unreachable"] == 1
    with pytest.raises(checks.CheckFailed):
        checks.expect_playbook_clean(checks.Result(0, out, ""))


def test_parse_quantity():
    assert checks.parse_quantity("64Mi") == 64 * 2**20
    assert checks.parse_quantity("200m") == pytest.approx(0.2)
    assert checks.parse_quantity("64Gi") > 2**30


def test_sh_missing_cwd_fails():
    with pytest.raises(checks.CheckFailed):
        checks.sh("true", cwd="/definitely/not/here")


def test_gitlab_without_token_fails_cleanly():
    with pytest.raises(checks.CheckFailed, match="No GitLab token"):
        checks.gitlab("/user")


def test_cli_list_and_show(capsys):
    cli.main(["list"])
    out = capsys.readouterr().out
    assert "ans-fix-01" in out and "Kubernetes" in out
    cli.main(["show", "k8s-fix-02"])
    out = capsys.readouterr().out
    assert "lab start k8s-fix-02" in out and "targetPort: 8080" in out


def test_hints_are_revealed_one_at_a_time(capsys):
    cli.main(["hint", "ans-fix-01"])
    cli.main(["hint", "ans-fix-01"])
    assert progress.load()["ans-fix-01"]["hints"] == 2
    assert "Hint 2/4" in capsys.readouterr().out
