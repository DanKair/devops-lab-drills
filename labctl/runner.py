"""Load a lab's check.py, run its tasks, and run setup/reset scripts."""

from __future__ import annotations

import importlib.util
import os
import shlex
import subprocess
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass

from . import checks, config
from .catalog import Lab


@dataclass
class TaskResult:
    title: str
    status: str  # pass | fail | skip | error
    message: str
    points: int
    seconds: float
    trace: str = ""

    @property
    def passed(self) -> bool:
        return self.status in ("pass", "skip")


def load_tasks(lab: Lab) -> list[checks.Task]:
    checks._REGISTRY.clear()
    checks._KUBE = None
    spec = importlib.util.spec_from_file_location(f"labcheck_{lab.id.replace('-', '_')}", lab.check_file)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {lab.check_file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    tasks = list(checks._REGISTRY)
    checks._REGISTRY.clear()
    return tasks


def run_tasks(tasks: list[checks.Task], fail_fast: bool = False,
              on_result: Callable[[TaskResult], None] | None = None) -> list[TaskResult]:
    results = []
    for t in tasks:
        start = time.monotonic()
        try:
            t.fn()
            r = TaskResult(t.title, "pass", "", t.points, 0)
        except checks.Skipped as e:
            r = TaskResult(t.title, "skip", str(e), t.points, 0)
        except (checks.CheckFailed, AssertionError) as e:
            r = TaskResult(t.title, "fail", str(e) or "Assertion failed", 0, 0)
        except Exception as e:  # a bug in the check or an unexpected environment
            r = TaskResult(t.title, "error", f"{type(e).__name__}: {e}", 0, 0, traceback.format_exc())
        r.seconds = time.monotonic() - start
        results.append(r)
        if on_result:
            on_result(r)
        if fail_fast and not r.passed:
            break
    return results


def script_env(lab: Lab) -> dict[str, str]:
    env = {
        "LAB_ID": lab.id,
        "LAB_DIR": str(lab.dir),
        "ANSIBLE_DIR": str(config.path("ansible_dir")),
        "TF_DIR": str(config.path("tf_dir")),
        "APP_REPO": str(config.path("app_repo")),
        "K8S_NS": config.get("k8s_namespace"),
        "NODE1": config.get("node1"),
        "NODE2": config.get("node2"),
        "SSH_OPTS": checks.SSH_OPTS,
    }
    if lab.track in ("k8s", "capstone"):
        env["KUBECTL"] = " ".join(shlex.quote(p) for p in checks.kube_command())
    return env


def run_script(lab: Lab, which: str) -> int:
    path = lab.setup_file if which == "setup" else lab.reset_file
    env = {**os.environ, **script_env(lab)}
    return subprocess.run(["bash", "-euo", "pipefail", str(path)], env=env).returncode
