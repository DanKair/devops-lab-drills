from labctl.checks import deploy_ready, expect, k_get, k_require, service_get, task


@task("shop pods are ready")
def pods():
    deploy_ready("shop", minimum=2)


@task("Service selector matches the pod labels")
def selector():
    sel = k_require("service", "shop")["spec"].get("selector", {})
    labels = {"app": "shop", "tier": "frontend"}
    expect(sel and all(labels.get(k) == v for k, v in sel.items()),
           f"Selector {sel} does not match pod labels {labels}.")


@task("Service has 2 ready endpoints on port 80")
def endpoints():
    slices = [s for s in k_get("endpointslices", None)["items"]
              if s["metadata"].get("labels", {}).get("kubernetes.io/service-name") == "shop"]
    ready = [e for s in slices for e in s.get("endpoints") or [] if e.get("conditions", {}).get("ready")]
    ports = {p.get("port") for s in slices for p in s.get("ports") or []}
    expect(len(ready) >= 2, f"{len(ready)} ready endpoints.")
    expect(ports == {80}, f"Endpoints point to port(s) {ports}; nginx listens on 80 (check targetPort).")


@task("Request through the Service returns the nginx page")
def http():
    ok, body = service_get("shop", 80)
    expect(ok and "Welcome to nginx" in body, f"Request failed: {body[:160]}")
