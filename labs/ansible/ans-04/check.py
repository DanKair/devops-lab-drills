import re

from labctl.checks import (
    cfg_path,
    expect,
    expect_playbook_clean,
    node,
    playbook,
    sh,
    ssh,
    task,
    text_of,
)


@task("Role webserver exists and site.yml uses it")
def role():
    d = cfg_path("ansible_dir")
    expect((d / "roles/webserver/tasks/main.yml").exists(), "roles/webserver/tasks/main.yml is missing.")
    expect("webserver" in text_of(d / "site.yml"), "site.yml does not reference the webserver role.")


@task("group_vars/web/vault.yml is encrypted with Ansible Vault")
def encrypted():
    head = text_of(cfg_path("ansible_dir") / "group_vars/web/vault.yml").splitlines()[0]
    expect(head.startswith("$ANSIBLE_VAULT;"), "vault.yml is plain text. Encrypt it with `ansible-vault encrypt`.")


@task("Vault password file is outside the project")
def vault_pass_location():
    d = cfg_path("ansible_dir")
    leaked = [p.name for p in d.iterdir() if "vault" in p.name.lower() and "pass" in p.name.lower()]
    expect(not leaked, f"Found {leaked} inside the project. Keep the password file in your home folder.")
    if (d / ".git").exists():
        r = sh("git ls-files", cwd=d)
        expect("vault_pass" not in r.out, "A vault password file is tracked by Git. Remove it and rotate the password.")


@task("/etc/lab/app.env on node1 is owned by root with mode 600")
def secret_file():
    r = ssh(node(1), "sudo stat -c '%a %U' /etc/lab/app.env")
    expect(r.out.strip() == "600 root", f"Got '{r.out.strip() or r.err.strip()}', expected '600 root'.")


@task("Playbook is idempotent and never prints the secret, even with -v")
def no_leak():
    d = cfg_path("ansible_dir")
    v = sh("ansible-vault view group_vars/web/vault.yml", cwd=d)
    expect(v.ok, f"Cannot decrypt vault.yml: {v.tail(2)}\nIs vault_password_file set in ansible.cfg?")
    m = re.search(r"vault_api_key:\s*['\"]?([^'\"\n]+)", v.out)
    expect(m, "vault.yml has no vault_api_key.")
    r = playbook("site.yml", "-v")
    expect_playbook_clean(r, idempotent=True)
    expect(m.group(1).strip() not in r.out, "The secret value appears in playbook output. Add `no_log: true`.")
