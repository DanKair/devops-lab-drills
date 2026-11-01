from labctl.checks import (
    cfg_path,
    docker_running,
    expect,
    task,
    terraform,
    text_of,
    tf_expect_no_changes,
)


@task("Part A: tf-blue is back and lab 02 shows no drift")
def drift():
    expect(docker_running("tf-blue"), "tf-blue is not running. Apply the plan in ~/tf-lab/02.")
    tf_expect_no_changes(cfg_path("tf_dir") / "02")


@task("Part B: terraform validate passes in ~/tf-lab/fix")
def valid():
    r = terraform("validate", cfg_path("tf_dir") / "fix")
    expect(r.ok, f"Still invalid:\n{r.tail()}")


@task("Part B: the fixes use the right attributes")
def attrs():
    text = text_of(cfg_path("tf_dir") / "fix" / "broken.tf")
    expect("id_image" not in text, "`id_image` is still there.")
    expect("ports[0].external" in text, "The output should read the first ports block: ports[0].external.")
    all_tf = "".join(p.read_text() for p in (cfg_path("tf_dir") / "fix").glob("*.tf"))
    expect('variable "api_port"' in all_tf, "api_port is never declared.")
