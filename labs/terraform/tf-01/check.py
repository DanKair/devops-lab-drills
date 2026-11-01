from labctl.checks import (
    cfg_path,
    docker_running,
    expect,
    http_get,
    task,
    terraform,
    text_of,
    tf_expect_no_changes,
    tf_state,
)


def D():
    return cfg_path("tf_dir") / "01"



@task("Configuration in ~/tf-lab/01 is valid and formatted")
def valid():
    r = terraform("validate", D())
    expect(r.ok, f"terraform validate failed (did you run init?):\n{r.tail()}")
    f = terraform("fmt -check", D())
    expect(f.ok, f"Files need formatting: {f.out.strip()}. Run `terraform fmt`.")


@task("State tracks docker_image.nginx and docker_container.web")
def state():
    s = tf_state(D())
    for addr in ("docker_image.nginx", "docker_container.web"):
        expect(addr in s, f"{addr} is not in state. Run terraform apply.")


@task("Container tf-web runs and answers on port 8082")
def http():
    expect(docker_running("tf-web"), "Container tf-web is not running.")
    status, _ = http_get("http://localhost:8082")
    expect(status == 200, f"http://localhost:8082 returned {status}. Did you change external to 8082 and apply?")


@task("Plan shows no changes (code matches reality)")
def no_changes():
    tf_expect_no_changes(D())


@task(".gitignore keeps state and plan files out of Git")
def gitignore():
    text = text_of(D() / ".gitignore")
    for pat in (".terraform", "*.tfstate"):
        expect(pat in text, f".gitignore does not contain {pat}")
