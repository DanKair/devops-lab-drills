"""Helpers available to every lab's check.py.

A check file registers tasks with @task. Each task passes by returning,
fails by raising CheckFailed (fail()/expect()) or AssertionError, and can
mark itself not applicable with skip(). Example:

    from labctl.checks import task, sh, expect

    @task("nginx answers on node1")
    def nginx():
        status, body = http_get("http://node1")
        expect(status == 200, f"Expected HTTP 200, got {status}")
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from . import config

# ---------------------------------------------------------------- registry


@dataclass
class Task:
    title: str
    fn: Callable[[], object]
    points: int = 1


_REGISTRY: list[Task] = []


def task(title: str, points: int = 1):
    def deco(fn):
        _REGISTRY.append(Task(title, fn, points))
        return fn

    return deco


class CheckFailed(Exception):
    """The learner's environment does not match the expected state."""


class Skipped(Exception):
    """The task does not apply to this environment (counts as passed)."""


def fail(msg: str):
    raise CheckFailed(msg)


def expect(cond: object, msg: str) -> None:
    if not cond:
        raise CheckFailed(msg)


def skip(msg: str):
    raise Skipped(msg)


cfg = config.get
cfg_path = config.path

# ---------------------------------------------------------------- shell


@dataclass
class Result:
    code: int
    out: str
    err: str

    @property
    def ok(self) -> bool:
        return self.code == 0

    @property
    def text(self) -> str:
        return (self.out + "\n" + self.err).strip()

    def tail(self, n: int = 6) -> str:
        lines = [ln for ln in self.text.splitlines() if ln.strip()]
        return "\n".join(lines[-n:])


def sh(cmd: str, cwd: str | Path | None = None, timeout: int = 120, input: str | None = None,
       env: dict | None = None) -> Result:
    if cwd is not None:
        cwd = Path(cwd).expanduser()
        if not cwd.is_dir():
            fail(f"Folder {cwd} does not exist. Did you create it in the lab tasks?")
    full_env = {**os.environ, **(env or {})}
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout,
                           cwd=cwd, input=input, env=full_env)
    except subprocess.TimeoutExpired:
        fail(f"Timed out after {timeout}s: {cmd}")
    return Result(p.returncode, p.stdout, p.stderr)


def need(binary: str, hint: str = "") -> None:
    if not shutil.which(binary):
        fail(f"`{binary}` is not installed on this machine. {hint}".strip())


SSH_OPTS = "-o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new"


def ssh(host: str, cmd: str, timeout: int = 60) -> Result:
    return sh(f"ssh {SSH_OPTS} {shlex.quote(host)} {shlex.quote(cmd)}", timeout=timeout)


def node(n: int) -> str:
    return cfg(f"node{n}")


def text_of(path: str | Path) -> str:
    p = Path(path).expanduser()
    if not p.exists():
        fail(f"File {p} not found.")
    return p.read_text()


# ---------------------------------------------------------------- http


def http_get(url: str, timeout: int = 6, headers: dict | None = None) -> tuple[int, str]:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode(errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")
    except (urllib.error.URLError, OSError) as e:
        return 0, str(getattr(e, "reason", e))


# ---------------------------------------------------------------- ansible


def ansible_recap(output: str) -> dict[str, dict[str, int]]:
    recap = {}
    for m in re.finditer(r"^(\S+)\s+:\s+((?:\w+=\d+\s*)+)$", output, re.M):
        recap[m.group(1)] = {k: int(v) for k, v in re.findall(r"(\w+)=(\d+)", m.group(2))}
    return recap


def playbook(name: str, extra: str = "", timeout: int = 600) -> Result:
    need("ansible-playbook")
    return sh(f"ANSIBLE_NOCOLOR=1 ANSIBLE_STDOUT_CALLBACK=default ansible-playbook {name} {extra}",
              cwd=cfg_path("ansible_dir"), timeout=timeout)


def expect_playbook_clean(r: Result, idempotent: bool = False) -> dict:
    recap = ansible_recap(r.out)
    expect(recap, f"Playbook did not finish:\n{r.tail()}")
    for host, s in recap.items():
        expect(s.get("failed", 0) == 0 and s.get("unreachable", 0) == 0,
               f"{host}: failed={s.get('failed')} unreachable={s.get('unreachable')}\n{r.tail()}")
        if idempotent:
            expect(s.get("changed", 0) == 0,
                   f"{host}: changed={s['changed']} on a repeat run. The playbook is not idempotent yet.")
    return recap


# ---------------------------------------------------------------- terraform


def terraform(args: str, cwd: str | Path, timeout: int = 300) -> Result:
    need("terraform", "Install it as described in tf-01.")
    return sh(f"terraform {args} -no-color", cwd=cwd, timeout=timeout,
              env={"TF_IN_AUTOMATION": "1", "TF_INPUT": "0"})


def tf_state(cwd: str | Path) -> list[str]:
    r = terraform("state list", cwd)
    if not r.ok and "No state file" in r.text:
        return []
    expect(r.ok, f"terraform state list failed:\n{r.tail()}")
    return [ln.strip() for ln in r.out.splitlines() if ln.strip()]


def tf_expect_no_changes(cwd: str | Path) -> None:
    r = terraform("plan -detailed-exitcode -lock=false", cwd)
    if r.code == 2:
        changes = [ln for ln in r.out.splitlines() if re.match(r"\s+# ", ln)]
        fail("terraform plan still wants to change things:\n" + "\n".join(changes[:8]))
    expect(r.code == 0, f"terraform plan failed:\n{r.tail()}")


def docker_running(name: str) -> bool:
    r = sh(f"docker inspect -f '{{{{.State.Running}}}}' {shlex.quote(name)}")
    return r.ok and r.out.strip() == "true"


# ---------------------------------------------------------------- kubernetes

_KUBE: list[str] | None = None


def kube_command() -> list[str]:
    """argv prefix for kubectl: ['kubectl'] or ['ssh', ..., host, 'kubectl']."""
    global _KUBE
    if _KUBE is not None:
        return _KUBE
    mode = cfg("k8s")
    ssh_prefix = lambda host: ["ssh", *SSH_OPTS.split(), host, "kubectl"]  # noqa: E731
    if mode == "local":
        _KUBE = ["kubectl"]
    elif mode.startswith("ssh:"):
        _KUBE = ssh_prefix(mode[4:])
    else:
        if shutil.which("kubectl") and sh("kubectl get --raw /readyz", timeout=10).ok:
            _KUBE = ["kubectl"]
        else:
            host = cfg("k8s_ssh_host")
            if ssh(host, "kubectl get --raw /readyz", timeout=15).ok:
                _KUBE = ssh_prefix(host)
            else:
                fail(f"Cannot reach a Kubernetes cluster: no working local kubectl, and `ssh {host} kubectl` "
                     "failed. Install k3s (k8s-01) or set `lab config set k8s ...`.")
    return _KUBE


def kubectl(args: str, input: str | None = None, timeout: int = 60) -> Result:
    prefix = kube_command()
    if prefix[0] == "kubectl":
        return sh(f"kubectl {args}", input=input, timeout=timeout)
    return sh(" ".join(shlex.quote(p) for p in prefix[:-1]) + " " + shlex.quote("kubectl " + args),
              input=input, timeout=timeout)


def ns() -> str:
    return cfg("k8s_namespace")


def k_get(kind: str, name: str | None = None, namespace: str | None = "") -> dict | None:
    """Return the object (or list) as JSON, or None if it does not exist."""
    if namespace == "":
        namespace = ns()
    scope = f"-n {namespace}" if namespace else ""
    target = f"{kind} {name}" if name else kind
    r = kubectl(f"get {target} {scope} -o json")
    if not r.ok:
        if "NotFound" in r.err or "not found" in r.err:
            return None
        fail(f"kubectl get {target} failed:\n{r.tail()}")
    return json.loads(r.out)


def k_require(kind: str, name: str, namespace: str | None = "") -> dict:
    obj = k_get(kind, name, namespace)
    where = namespace if namespace not in ("", None) else ns()
    expect(obj, f"{kind}/{name} not found in namespace {where}.")
    return obj


def deploy_ready(name: str, minimum: int = 1) -> dict:
    d = k_require("deployment", name)
    want = d["spec"].get("replicas", 1)
    ready = d.get("status", {}).get("readyReplicas", 0) or 0
    expect(want >= minimum, f"deployment/{name} has replicas={want}, expected at least {minimum}.")
    expect(ready == want, f"deployment/{name}: {ready}/{want} replicas ready. "
                          f"Look at `kubectl -n {ns()} get pods` and `describe`.")
    return d


def service_get(svc: str, port: int | str, path: str = "/", namespace: str | None = None) -> tuple[bool, str]:
    """HTTP GET through the API server's service proxy (works for k3s, kind, anything)."""
    r = kubectl(f"get --raw /api/v1/namespaces/{namespace or ns()}/services/{svc}:{port}/proxy{path}",
                timeout=20)
    return r.ok, r.out if r.ok else r.err


def containers(deploy: dict) -> list[dict]:
    return deploy["spec"]["template"]["spec"]["containers"]


def parse_quantity(q: str) -> float:
    """Kubernetes quantity -> bytes (memory) or cores (cpu), good enough for checks."""
    units = {"Ki": 2**10, "Mi": 2**20, "Gi": 2**30, "Ti": 2**40, "k": 1e3, "M": 1e6, "G": 1e9, "m": 1e-3}
    m = re.fullmatch(r"([0-9.]+)([A-Za-z]*)", str(q))
    if not m:
        return float("nan")
    return float(m.group(1)) * units.get(m.group(2), 1)


# ---------------------------------------------------------------- gitlab


def gitlab(path: str, method: str = "GET", data: dict | None = None):
    token = cfg("gitlab_token")
    expect(token, "No GitLab token configured. Run `lab config set gitlab_token` (read_api scope).")
    url = cfg("gitlab_url").rstrip("/") + "/api/v4" + path
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method,
                                 headers={"PRIVATE-TOKEN": token, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        if e.code == 401:
            fail("GitLab rejected the token (401). It may be expired; create a new one.")
        if e.code == 403:
            fail(f"GitLab says 403 for {path}. Does the token have read_api scope?")
        if e.code == 404:
            fail(f"GitLab returned 404 for {path}. Check `lab config get gitlab_project`.")
        fail(f"GitLab API error {e.code} for {path}")
    except urllib.error.URLError as e:
        fail(f"Cannot reach {cfg('gitlab_url')}: {e.reason}")


def project(key: str = "gitlab_project") -> str:
    p = cfg(key)
    expect(p, f"Set the project first: `lab config set {key} <namespace>/<project>`.")
    return "/projects/" + urllib.parse.quote(p, safe="")


def latest_pipeline(ref: str | None = None, key: str = "gitlab_project") -> dict:
    proj = project(key)
    if ref is None:
        ref = gitlab(proj)["default_branch"]
    pipes = gitlab(f"{proj}/pipelines?ref={urllib.parse.quote(ref)}&per_page=1")
    expect(pipes, f"No pipelines found on branch {ref}. Push a commit first.")
    return pipes[0]


def pipeline_jobs(pipeline_id: int, key: str = "gitlab_project") -> dict[str, dict]:
    jobs = gitlab(f"{project(key)}/pipelines/{pipeline_id}/jobs?per_page=100&include_retried=false")
    return {j["name"]: j for j in jobs}


def load_yaml(path: str | Path):
    import yaml

    class Loader(yaml.SafeLoader):
        pass

    # GitLab-specific tags such as !reference should not crash the checker
    Loader.add_multi_constructor("!", lambda loader, suffix, node: None)
    try:
        return yaml.load(text_of(path), Loader=Loader)  # noqa: S506 - SafeLoader subclass
    except yaml.YAMLError as e:
        fail(f"{path} is not valid YAML: {e}")
