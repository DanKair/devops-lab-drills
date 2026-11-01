from labctl.checks import (
    cfg_path,
    expect,
    http_get,
    sh,
    task,
    terraform,
    text_of,
    tf_expect_no_changes,
    tf_state,
)


def D():
    return cfg_path("tf_dir") / "03"



@task("Module declares its own required_providers")
def module_providers():
    text = text_of(D() / "modules/web/main.tf")
    expect("kreuzwerker/docker" in text, "modules/web/main.tf has no required_providers for kreuzwerker/docker.")


@task("Both module instances are in state")
def state():
    s = tf_state(D())
    for m in ("module.dev.docker_container.this", "module.prod.docker_container.this"):
        expect(m in s, f"{m} missing. Run terraform apply.")


@task("dev answers on 9001 and prod on 9002")
def http():
    for env, port in (("dev", 9001), ("prod", 9002)):
        status, _ = http_get(f"http://localhost:{port}")
        expect(status == 200, f"{env} on :{port} returned {status}.")


@task("prod container has APP_ENV=prod and runs nginx 1.26")
def prod_env():
    r = sh("docker exec prod-web printenv APP_ENV")
    expect(r.out.strip() == "prod", f"APP_ENV is '{r.out.strip()}'.")
    img = sh("docker inspect -f '{{.Config.Image}}' prod-web").out
    expect("1.26" in img, f"prod-web runs {img.strip()}, expected nginx:1.26-alpine.")


@task("Root output `urls` exists and plan shows no changes")
def outputs():
    expect(terraform("output urls", D()).ok, "No root output named urls.")
    tf_expect_no_changes(D())
