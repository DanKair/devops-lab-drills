from labctl.checks import (
    containers,
    deploy_ready,
    expect,
    k_require,
    kubectl,
    ns,
    parse_quantity,
    task,
)


@task("ConfigMap site and Secret app-secret exist")
def objects():
    k_require("configmap", "site")
    s = k_require("secret", "app-secret")
    expect("API_KEY" in s.get("data", {}), "app-secret has no API_KEY key.")


@task("Deployment app is ready with 2 replicas")
def ready():
    deploy_ready("app", minimum=2)


@task("Container has readiness and liveness probes on path /")
def probes():
    c = containers(k_require("deployment", "app"))[0]
    for p in ("readinessProbe", "livenessProbe"):
        expect(p in c, f"{p} is missing.")
        expect(c[p].get("httpGet", {}).get("path") == "/", f"{p} should httpGet path / (did you revert /healthz?).")


@task("Requests and limits are set, limit at least the request")
def resources():
    r = containers(k_require("deployment", "app"))[0].get("resources", {})
    for kind in ("requests", "limits"):
        for res in ("cpu", "memory"):
            expect(res in r.get(kind, {}), f"resources.{kind}.{res} is missing.")
            if kind == "limits":
                expect(parse_quantity(r["limits"][res]) >= parse_quantity(r["requests"][res]),
                       f"{res} limit is below the request.")


@task("API_KEY comes from the Secret, and the page comes from the ConfigMap (v2)")
def wiring():
    c = containers(k_require("deployment", "app"))[0]
    env = {e["name"]: e for e in c.get("env", [])}
    expect("secretKeyRef" in env.get("API_KEY", {}).get("valueFrom", {}), "API_KEY must use secretKeyRef.")
    mounts = [m for m in c.get("volumeMounts", []) if m["mountPath"] == "/usr/share/nginx/html"]
    expect(mounts and "subPath" not in mounts[0], "Mount the ConfigMap at /usr/share/nginx/html without subPath.")
    r = kubectl(f"-n {ns()} exec deploy/app -- cat /usr/share/nginx/html/index.html")
    expect(r.ok and "v2" in r.out, f"index.html is {r.out.strip()[:60]!r}. Update the ConfigMap to v2 and wait ~1 min.")
