from labctl.checks import expect, k_get, kube_command, ns, task


@task("kubectl can reach the cluster")
def reach():
    kube_command()


@task("All nodes are Ready")
def ready():
    nodes = k_get("nodes", namespace=None)["items"]
    expect(nodes, "No nodes found.")
    for n in nodes:
        cond = next(c for c in n["status"]["conditions"] if c["type"] == "Ready")
        expect(cond["status"] == "True", f"Node {n['metadata']['name']} is NotReady.")


@task("k3s node uses the private IP (--node-ip), not the Vagrant NAT address")
def node_ip():
    nodes = k_get("nodes", namespace=None)["items"]
    ips = [a["address"] for n in nodes for a in n["status"]["addresses"] if a["type"] == "InternalIP"]
    if any(n["metadata"]["name"].endswith("control-plane") for n in nodes):
        from labctl.checks import skip
        skip("kind cluster detected; node IP check not needed.")
    expect(not any(ip.startswith("10.0.2.") for ip in ips),
           f"Node InternalIP is {ips}. Reinstall k3s with --node-ip 192.168.56.11.")


@task("Namespace for the labs exists")
def namespace():
    expect(k_get("namespace", ns(), namespace=None), f"Namespace {ns()} missing: `kubectl create namespace {ns()}`.")
