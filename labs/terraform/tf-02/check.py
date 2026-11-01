import json

from labctl.checks import (
    cfg_path,
    expect,
    http_get,
    task,
    terraform,
    tf_expect_no_changes,
    tf_state,
)


def D():
    return cfg_path("tf_dir") / "02"

SITES = {"blue": 8091, "green": 8092, "red": 8093}


@task("Three containers are managed with for_each (keyed by name)")
def keyed():
    s = tf_state(D())
    for name in SITES:
        addr = f'docker_container.site["{name}"]'
        expect(addr in s, f"{addr} is not in state. Is `red` in terraform.tfvars and applied?")


@task("Every site answers on its port")
def ports():
    for name, port in SITES.items():
        status, _ = http_get(f"http://localhost:{port}")
        expect(status == 200, f"{name} on :{port} returned {status}.")


@task("Output `urls` lists all three sites")
def outputs():
    r = terraform("output -json urls", D())
    expect(r.ok, f"No output named urls:\n{r.tail(3)}")
    urls = json.loads(r.out)
    expect(set(urls) >= set(SITES), f"urls has {sorted(urls)}, expected {sorted(SITES)}.")


@task("Validation rejects port 80")
def validation():
    r = terraform("plan -lock=false -var=sites={x=80}", D())
    expect(not r.ok and "Invalid value for variable" in r.text,
           "Plan with port 80 did not fail on validation. Add the validation block to var.sites.")


@task("Plan shows no changes")
def no_changes():
    tf_expect_no_changes(D())
