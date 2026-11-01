from labctl.checks import (
    containers,
    expect,
    gitlab,
    k_get,
    k_require,
    kubectl,
    latest_pipeline,
    pipeline_jobs,
    project,
    service_get,
    task,
)

NS = "shop"
P = "capstone_project"


@task("Namespace shop has a ResourceQuota")
def quota():
    expect(k_get("namespace", NS, namespace=None), "Namespace shop does not exist. Create it with Terraform.")
    rq = kubectl(f"-n {NS} get resourcequota -o name")
    expect(rq.out.strip(), "No ResourceQuota in namespace shop.")


@task("Deployment shop is ready with 2+ replicas, probes and a non-root securityContext")
def deployment():
    d = k_require("deployment", "shop", namespace=NS)
    want, ready = d["spec"].get("replicas", 1), d.get("status", {}).get("readyReplicas", 0) or 0
    expect(want >= 2 and ready == want, f"{ready}/{want} ready (need at least 2).")
    pod_spec = d["spec"]["template"]["spec"]
    for c in containers(d):
        expect("readinessProbe" in c and "livenessProbe" in c, f"Container {c['name']} needs both probes.")
        sc = {**pod_spec.get("securityContext", {}), **c.get("securityContext", {})}
        expect(sc.get("runAsNonRoot") is True, f"{c['name']}: set runAsNonRoot: true.")
        expect(sc.get("allowPrivilegeEscalation") is False, f"{c['name']}: set allowPrivilegeEscalation: false.")


@task("Running image matches the latest commit on the default branch")
def image_sha():
    pipe = latest_pipeline(key=P)
    expect(pipe["status"] == "success", f"Latest pipeline is {pipe['status']}: {pipe['web_url']}")
    jobs = pipeline_jobs(pipe["id"], key=P)
    expect(any(j["stage"] == "deploy" and j["status"] == "success" for j in jobs.values()),
           "No successful deploy-stage job in the latest pipeline.")
    image = containers(k_require("deployment", "shop", namespace=NS))[0]["image"]
    tag = image.rsplit(":", 1)[-1]
    expect(pipe["sha"].startswith(tag), f"Cluster runs {image}, latest commit is {pipe['sha'][:8]}.")


@task("GitLab environment production shows a deployment")
def environment():
    envs = gitlab(f"{project(P)}/environments?name=production")
    expect(envs, "No environment called production. Add `environment: production` to the deploy job.")
    env = gitlab(f"{project(P)}/environments/{envs[0]['id']}")
    last = env.get("last_deployment") or {}
    expect(last.get("status") == "success", f"Last production deployment status: {last.get('status')}.")


@task("App answers through its Service")
def http():
    svcs = kubectl(f"-n {NS} get svc -o jsonpath='{{.items[0].metadata.name}}:{{.items[0].spec.ports[0].port}}'")
    expect(svcs.ok and ":" in svcs.out, "No Service in namespace shop.")
    name, port = svcs.out.strip().split(":")
    ok, body = service_get(name, port, namespace=NS)
    expect(ok, f"Request through service {name} failed: {body[:160]}")
