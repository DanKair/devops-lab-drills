"""setup-01: run on the control VM."""
from labctl.checks import expect, need, node, sh, task


@task("This machine is the lab's control VM")
def hostname():
    r = sh("hostname")
    expect(r.out.strip() == "control", f"hostname is '{r.out.strip()}'. Run `lab check` inside `vagrant ssh control`.")


@task("node1 and node2 answer ping over the private network")
def ping():
    for n in (1, 2):
        r = sh(f"ping -c 1 -W 2 {node(n)}")
        expect(r.ok, f"{node(n)} does not answer ping. Is it running (`vagrant status`)? Is /etc/hosts filled?")


@task("node names resolve to the 192.168.56.0/24 addresses")
def hosts():
    for n, ip in ((1, "192.168.56.11"), (2, "192.168.56.12")):
        r = sh(f"getent hosts {node(n)}")
        expect(ip in r.out, f"{node(n)} resolves to '{r.out.strip()}', expected {ip}.")


@task("Ansible is installed on control")
def ansible():
    need("ansible", "The Vagrantfile provisions it; run `vagrant provision control`.")
