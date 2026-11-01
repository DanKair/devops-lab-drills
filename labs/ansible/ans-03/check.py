from labctl.checks import (
    cfg_path,
    expect,
    expect_playbook_clean,
    http_get,
    node,
    playbook,
    sh,
    ssh,
    task,
)


@task("http_port is 8080 for node1 (from group_vars)")
def port_var():
    r = sh("ANSIBLE_NOCOLOR=1 ansible node1 -m debug -a var=http_port", cwd=cfg_path("ansible_dir"))
    expect('"http_port": 8080' in r.out or "http_port: 8080" in r.out,
           f"http_port is not 8080 for node1:\n{r.tail(4)}")


@task("Templated page on :8080 shows the title, hostname and distribution")
def page():
    status, body = http_get(f"http://{node(1)}:8080/")
    expect(status == 200, f"http://{node(1)}:8080/ returned {status or body}. Is the site enabled?")
    expect("<h1>" in body, "The page has no <h1> title. Check index.html.j2.")
    expect("node1" in body and "Ubuntu" in body, f"Hostname/distribution facts missing: {body[:160]!r}")


@task("Site config is a symlink in sites-enabled")
def symlink():
    r = ssh(node(1), "test -L /etc/nginx/sites-enabled/lab.conf && readlink /etc/nginx/sites-enabled/lab.conf")
    expect(r.ok, "/etc/nginx/sites-enabled/lab.conf is not a symlink.")


@task("site.yml defines a handler and notifies it")
def handler():
    d = cfg_path("ansible_dir")
    text = "".join(p.read_text() for p in [d / "site.yml", *d.glob("roles/*/handlers/main.yml"),
                                           *d.glob("roles/*/tasks/main.yml")] if p.exists())
    expect("notify:" in text, "No task uses `notify:`.")
    expect("reloaded" in text or "restarted" in text, "No handler reloads or restarts nginx.")


@task("Repeat run: changed=0 and the handler does not fire")
def idempotent():
    r = playbook("site.yml")
    expect_playbook_clean(r, idempotent=True)
    expect("RUNNING HANDLER" not in r.out, "A handler ran on a run where nothing changed.")
