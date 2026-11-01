import os
import stat

from labctl.checks import cfg_path, expect, need, node, sh, ssh, task


@task("ansible.cfg exists and its folder is not world-writable")
def cfg_safe():
    d = cfg_path("ansible_dir")
    expect((d / "ansible.cfg").exists(), f"No ansible.cfg in {d}.")
    mode = os.stat(d).st_mode
    expect(not mode & stat.S_IWOTH, f"{d} is world-writable, so Ansible ignores ansible.cfg there. Use ~/ansible-lab.")


@task("Inventory has groups web, db and parent group lab")
def inventory():
    need("ansible-inventory")
    r = sh("ansible-inventory --graph", cwd=cfg_path("ansible_dir"))
    expect(r.ok, f"ansible-inventory failed:\n{r.tail()}")
    for g in ("@web", "@db", "@lab"):
        expect(g in r.out, f"Group {g[1:]} is missing from the inventory:\n{r.out}")
    expect("node1" in r.out and "node2" in r.out, "node1 and node2 must both be in the inventory.")


@task("Key-based SSH works to both nodes")
def keys():
    for n in (1, 2):
        r = ssh(node(n), "true", timeout=15)
        expect(r.ok, f"`ssh {node(n)}` needs a password or fails: {r.tail(2)}\nRun `ssh-copy-id vagrant@{node(n)}`.")


@task("`ansible all -m ping` returns pong from both nodes")
def ping():
    r = sh("ANSIBLE_NOCOLOR=1 ansible all -m ping -o", cwd=cfg_path("ansible_dir"), timeout=60)
    expect(r.out.count("SUCCESS") >= 2, f"Expected 2 SUCCESS lines:\n{r.tail()}")


@task("Package `tree` is installed on node2 (ad-hoc apt)")
def tree():
    r = ssh(node(2), "command -v tree")
    expect(r.ok, "tree is not installed on node2. Use the `apt` module with -b.")
