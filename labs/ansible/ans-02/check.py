from labctl.checks import (
    cfg_path,
    expect,
    expect_playbook_clean,
    http_get,
    node,
    playbook,
    ssh,
    task,
)


@task("site.yml exists and passes --syntax-check")
def syntax():
    expect((cfg_path("ansible_dir") / "site.yml").exists(), "No site.yml in your ansible folder.")
    r = playbook("site.yml", "--syntax-check")
    expect(r.ok, f"Syntax check failed:\n{r.tail()}")


@task("nginx serves 'Hello from node1' on port 80")
def homepage():
    status, body = http_get(f"http://{node(1)}/")
    expect(status == 200, f"http://{node(1)}/ returned {status or body}.")
    expect("Hello from node1" in body, f"Unexpected page content: {body[:120]!r}")


@task("nginx is enabled at boot")
def enabled():
    r = ssh(node(1), "systemctl is-enabled nginx")
    expect(r.out.strip() == "enabled", f"nginx is '{r.out.strip() or r.err.strip()}', expected enabled.")


@task("chrony runs on node2 (challenge play)")
def chrony():
    r = ssh(node(2), "systemctl is-active chrony")
    expect(r.out.strip() == "active", "chrony is not active on node2. Add the db play from the challenge.")


@task("A repeat run of site.yml changes nothing (idempotent)")
def idempotent():
    expect_playbook_clean(playbook("site.yml"), idempotent=True)
