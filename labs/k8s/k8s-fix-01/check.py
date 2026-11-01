from labctl.checks import (
    containers,
    deploy_ready,
    expect,
    kubectl,
    ns,
    parse_quantity,
    task,
)


@task("api pulls a real image and is ready")
def api():
    d = deploy_ready("api")
    image = containers(d)[0]["image"]
    expect(image.startswith("python:3.12-slim") and "slimm" not in image, f"api image is {image}.")


@task("worker stays up and reads its config")
def worker():
    deploy_ready("worker")
    r = kubectl(f"-n {ns()} logs deploy/worker")
    expect("queue=jobs" in r.out, f"worker logs do not show the config:\n{r.tail(3)}")
    pods = kubectl(f"-n {ns()} get pods -l app=worker -o jsonpath='{{.items[*].status.containerStatuses[0].ready}}'")
    expect("false" not in pods.out, "A worker pod is not ready.")


@task("report is scheduled with a realistic memory request")
def report():
    d = deploy_ready("report")
    mem = containers(d)[0].get("resources", {}).get("requests", {}).get("memory", "0")
    expect(parse_quantity(mem) <= 2**30, f"memory request is {mem}; keep it at 1Gi or less on this node.")
