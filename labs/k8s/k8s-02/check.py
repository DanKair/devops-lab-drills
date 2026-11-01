from labctl.checks import (
    containers,
    deploy_ready,
    expect,
    k_get,
    k_require,
    service_get,
    task,
)


@task("Deployment web: at least 3 replicas, all ready")
def ready():
    deploy_ready("web", minimum=3)


@task("Rolled out and rolled back: image is nginx:1.26-alpine at revision 3 or later")
def rollback():
    d = k_require("deployment", "web")
    image = containers(d)[0]["image"]
    rev = int(d["metadata"].get("annotations", {}).get("deployment.kubernetes.io/revision", "0"))
    expect(rev >= 3, f"Revision is {rev}. Do the `set image` and then `rollout undo`.")
    expect(image == "nginx:1.26-alpine", f"Image is {image}. After `rollout undo` it should be nginx:1.26-alpine.")


@task("Service web is NodePort 30080 and selects the pods")
def service():
    s = k_require("service", "web")
    expect(s["spec"]["type"] == "NodePort", f"Service type is {s['spec']['type']}.")
    expect(any(p.get("nodePort") == 30080 for p in s["spec"]["ports"]), "nodePort is not 30080.")
    eps = k_get("endpointslices", None)["items"]
    ready = [e for sl in eps if sl["metadata"].get("labels", {}).get("kubernetes.io/service-name") == "web"
             for e in sl.get("endpoints") or [] if e.get("conditions", {}).get("ready")]
    expect(len(ready) >= 3, f"Service web has {len(ready)} ready endpoints, expected 3 or more.")


@task("Service returns the nginx welcome page")
def http():
    ok, body = service_get("web", 80)
    expect(ok and "Welcome to nginx" in body, f"Request through the service failed: {body[:160]}")
