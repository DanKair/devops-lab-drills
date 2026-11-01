from labctl.checks import (
    expect,
    expect_playbook_clean,
    http_get,
    node,
    playbook,
    ssh,
    task,
)


@task("status.yml targets an inventory group that contains node1")
def hosts():
    r = playbook("status.yml", "--list-hosts")
    expect(r.ok and "node1" in r.out, f"No hosts matched:\n{r.tail(4)}")


@task("Fresh run succeeds, including the handler")
def fresh_run():
    ssh(node(1), "sudo rm -f /var/www/html/status.html")
    r = playbook("status.yml")
    expect_playbook_clean(r)
    expect("RUNNING HANDLER" in r.out, "The handler did not run although the status page changed.")


@task("Status page returns OK")
def page():
    status, body = http_get(f"http://{node(1)}/status.html")
    expect(status == 200 and body.strip() == "OK", f"Got {status}: {body[:80]!r}")


@task("Second run is idempotent")
def idempotent():
    expect_playbook_clean(playbook("status.yml"), idempotent=True)
