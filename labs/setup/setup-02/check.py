"""setup-02: run inside WSL."""
import json

from labctl.checks import expect, need, sh, task


@task("Docker works without sudo")
def docker():
    need("docker")
    r = sh("docker ps", timeout=15)
    expect(r.ok, f"`docker ps` failed: {r.tail(2)}\nAdd yourself to the docker group and reopen the terminal.")


@task("A kind cluster called 'lab' is running")
def kind():
    need("kind")
    r = sh("kind get clusters")
    expect("lab" in r.out.split(), "No kind cluster named 'lab'. Run `kind create cluster --name lab`.")


@task("kubectl talks to the cluster and the node is Ready")
def node_ready():
    need("kubectl")
    r = sh("kubectl get nodes -o json", timeout=20)
    expect(r.ok, f"kubectl failed: {r.tail(2)}")
    nodes = json.loads(r.out)["items"]
    expect(nodes, "The cluster has no nodes.")
    for n in nodes:
        ready = next(c for c in n["status"]["conditions"] if c["type"] == "Ready")
        expect(ready["status"] == "True", f"Node {n['metadata']['name']} is not Ready.")


@task("Ansible is installed with pipx")
def ansible():
    need("ansible", "Run `pipx install --include-deps ansible` and `pipx ensurepath`.")
