"""User config and state directory (~/.labdrills by default).

Every key can be overridden with an environment variable LAB_<KEY>,
e.g. LAB_ANSIBLE_DIR=/srv/ansible lab check ans-01.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULTS: dict[str, str] = {
    "ansible_dir": "~/ansible-lab",
    "tf_dir": "~/tf-lab",
    "k8s": "auto",  # auto | local | ssh:<host>
    "k8s_ssh_host": "node1",
    "k8s_namespace": "lab",
    "node1": "node1",
    "node2": "node2",
    "app_repo": "~/gitlab-app",
    "gitlab_url": "https://gitlab.com",
    "gitlab_project": "",
    "gitlab_token": "",
    "capstone_project": "",
}

SECRET_KEYS = {"gitlab_token"}

DESCRIPTIONS: dict[str, str] = {
    "ansible_dir": "Folder with ansible.cfg, inventory and playbooks (Ansible track)",
    "tf_dir": "Parent folder of the Terraform labs (01, 02, 03, fix)",
    "k8s": "How to reach kubectl: auto, local, or ssh:<host>",
    "k8s_ssh_host": "Host used when k8s=auto falls back to SSH",
    "k8s_namespace": "Namespace the Kubernetes labs use",
    "node1": "SSH name of the first node",
    "node2": "SSH name of the second node",
    "app_repo": "Local clone of your GitLab project",
    "gitlab_url": "GitLab instance URL",
    "gitlab_project": "Project path, e.g. kair/devops-app",
    "gitlab_token": "Personal access token with read_api scope (stored with mode 600)",
    "capstone_project": "Capstone project path (defaults to gitlab_project)",
}


def home() -> Path:
    return Path(os.environ.get("LAB_DRILLS_HOME", "~/.labdrills")).expanduser()


def _file() -> Path:
    return home() / "config.json"


def _read() -> dict[str, str]:
    try:
        return json.loads(_file().read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write(data: dict[str, str]) -> None:
    h = home()
    h.mkdir(parents=True, exist_ok=True)
    os.chmod(h, 0o700)
    f = _file()
    tmp = f.with_suffix(".tmp")
    # create with 0600 from the start so the token is never world-readable
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        json.dump(data, fh, indent=2)
    os.replace(tmp, f)


def get(key: str) -> str:
    env = os.environ.get("LAB_" + key.upper())
    if env is not None:
        return env
    value = _read().get(key)
    if value is None:
        value = DEFAULTS.get(key, "")
    if key == "capstone_project" and not value:
        return get("gitlab_project")
    return value


def set_value(key: str, value: str) -> None:
    if key not in DEFAULTS:
        raise KeyError(key)
    data = _read()
    data[key] = value
    _write(data)


def unset(key: str) -> None:
    data = _read()
    data.pop(key, None)
    _write(data)


def path(key: str) -> Path:
    return Path(get(key)).expanduser()


def show() -> list[tuple[str, str, str]]:
    """Rows of (key, value, source) with secrets masked."""
    stored = _read()
    rows = []
    for key in DEFAULTS:
        value = get(key)
        if "LAB_" + key.upper() in os.environ:
            source = "env"
        elif key in stored:
            source = "config"
        else:
            source = "default"
        if key in SECRET_KEYS and value:
            value = value[:6] + "…" + f" ({len(value)} chars)"
        rows.append((key, value or "(empty)", source))
    return rows
