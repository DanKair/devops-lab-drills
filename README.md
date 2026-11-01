# DevOps Lab Drills

Free, hands-on DevOps labs with automatic checking. You run them on your own machines; nothing is hosted for you.

You read a lab on the website, do the work in your own homelab (three Vagrant VMs), and run `lab check <id>`. The CLI inspects the real state of your machines and reports which tasks pass. The workflow copies [Test My Code](https://www.mooc.fi/en/installation/vscode/) (the MOOC.fi exercise checker), and the content style follows KodeKloud and LabEx: scenario-driven tasks plus break-fix troubleshooting.

```
$ lab check k8s-fix-02

Checking k8s-fix-02 · Break-fix: the Service with no endpoints
  ✓ shop pods are ready  0.4s
  ✗ Service selector matches the pod labels  0.2s
      Selector {'app': 'shop-frontend'} does not match pod labels {'app': 'shop', 'tier': 'frontend'}.
  ✗ Service has 2 ready endpoints on port 80  0.2s
      0 ready endpoints.
  ✗ Request through the Service returns the nginx page  0.3s
      Request failed: Error from server (ServiceUnavailable): no endpoints available for service "shop"

  1/4 tasks passed  █████░░░░░░░░░░░░░░░  25%
  Fix the failed tasks and run `lab check k8s-fix-02` again. Stuck? `lab hint k8s-fix-02`
```

## What's inside

| Track | Labs | Break-fix |
|---|---|---|
| Lab environment | Vagrant + VirtualBox homelab, or WSL2 + Docker + kind | |
| Ansible | inventory and ad-hoc, playbooks, templates and handlers, roles and Vault | broken status-page playbook (4 bugs) |
| Terraform | Docker provider, variables and `for_each`, modules | drift + `import`, invalid config (3 bugs) |
| Kubernetes | k3s, pods, Deployments and rollouts, ConfigMaps, Secrets, probes, limits | ImagePullBackOff, CrashLoopBackOff and Pending; Service with no endpoints |
| GitLab CI/CD | GitHub Actions → GitLab mapping, own runner, build + SAST + registry | pipeline that never builds (5 bugs) |
| Capstone | Ansible + Terraform + GitLab CI deploying to k3s, then game day | |

That is 21 labs, 5 of them break-fix, with 93 automated check tasks and about 19 hours of work.

## How it fits together

```
labs/<track>/<id>/
├── lab.yaml     # scenario, tasks, hints, solution (Markdown)
├── check.py     # automated checks (@task functions)
├── setup.sh     # optional: builds the broken state for break-fix labs
├── reset.sh     # optional: removes what setup created
└── *.yaml/*.tf  # files used by setup.sh

labctl/          # the `lab` CLI (Python, only dependency: PyYAML)
scripts/build_site.py  # labs/ → _site/index.html (one static page)
site/            # page template
.github/workflows/
├── ci.yml       # ruff, pytest (incl. schema checks on every lab), shellcheck, site build
└── pages.yml    # builds the site and deploys it to GitHub Pages
Vagrantfile      # control + node1 + node2; installs the CLI on control
```

The same `lab.yaml` file feeds both the website and `lab show` in the terminal. Each check task's title is shown on the website under "Checked automatically", so you know what the target state is without seeing the solution.

## Setup guide

### 1. Put the repo on GitHub

```bash
# on your computer, in the unzipped folder
git init -b main
git add -A
git commit -m "DevOps Lab Drills: labs, lab CLI, site"
gh repo create devops-lab-drills --public --source . --push
# or create an empty repo on github.com and:
# git remote add origin https://github.com/<you>/devops-lab-drills.git && git push -u origin main
```

### 2. Turn on GitHub Pages

1. Go to the repo → **Settings → Pages**, and under **Build and deployment → Source** choose **GitHub Actions**.
2. Go to **Actions** and open the "Deploy site to GitHub Pages" run (re-run it if it ran before you changed the setting).
3. Your site is at `https://<you>.github.io/devops-lab-drills/`.

The site rebuilds on every push to `main`. GitHub Pages is free for public repositories.

### 3. Build the homelab

You need VirtualBox 7.x, Vagrant, and at least 8 GB of RAM (16 GB is comfortable).

```bash
git clone https://github.com/<you>/devops-lab-drills.git
cd devops-lab-drills
vagrant up                 # ~10 min the first time
vagrant snapshot save clean
vagrant ssh control
lab doctor                 # shows what is ready
lab show setup-01
lab check setup-01
```

The repo folder is synced into the control VM at `/vagrant`, and the CLI is installed from there in editable mode. When you edit a lab on your host, the change applies immediately inside the VM.

**On Windows:** clone with Git for Windows in a normal folder. `.gitattributes` forces LF line endings so the shell scripts still run inside Linux.

### 4. Daily loop

```bash
lab status              # progress and the next lab
lab show ans-01         # read it in the terminal (or on the website)
lab start ans-fix-01    # break-fix labs: build the broken state
lab check ans-01        # run the checks; exit code 0 = all passed
lab hint ans-01         # one hint at a time (counted)
lab solution ans-01     # asks first; recorded in progress
lab reset k8s-fix-01    # undo what setup created
lab export              # code to paste into the website to sync progress
```

### 5. GitLab labs

The GitLab labs read your pipelines through the GitLab API:

```bash
git clone https://gitlab.com/<you>/<project>.git ~/gitlab-app
lab config set gitlab_project <you>/<project>
lab config set gitlab_token        # prompts with hidden input
lab doctor
```

Create the token under User settings → Access tokens with **only the `read_api` scope** and a short expiry. It is stored in `~/.labdrills/config.json` with mode 600. You can also pass it per command with `LAB_GITLAB_TOKEN=...`.

### Without VirtualBox (WSL2)

Follow `setup-02`, then install the CLI with `pipx install git+https://github.com/<you>/devops-lab-drills.git`. The Terraform, Kubernetes (kind) and GitLab labs work there. The Ansible checks expect `node1` and `node2` over SSH; point them elsewhere with `lab config set node1 <host>`.

## Configuration

`lab config show` lists every setting. Change one with `lab config set <key> <value>`, or override it for a single command with `LAB_<KEY>=value lab check ...`.

| Key | Default | Used by |
|---|---|---|
| `ansible_dir` | `~/ansible-lab` | Ansible labs |
| `tf_dir` | `~/tf-lab` | Terraform labs (`01`, `02`, `03`, `fix` inside) |
| `k8s` | `auto` | `auto` tries local kubectl, then `ssh node1 kubectl`; or set `local` / `ssh:<host>` |
| `k8s_namespace` | `lab` | Kubernetes labs |
| `node1`, `node2` | `node1`, `node2` | SSH targets |
| `app_repo` | `~/gitlab-app` | GitLab labs |
| `gitlab_url`, `gitlab_project`, `gitlab_token` | gitlab.com, empty, empty | GitLab labs |
| `capstone_project` | same as `gitlab_project` | Capstone |

Progress lives in `~/.labdrills/progress.json`.

## Writing a new lab

1. Create `labs/<track>/<new-id>/lab.yaml`. Copy an existing one and give it the next `order` number. Orders must be 1..N with no gaps, so shift the later labs if you insert one.
2. Write `check.py`. Each `@task` describes one piece of the end state:

```python
from labctl.checks import task, expect, deploy_ready, service_get

@task("Deployment api is ready with 2 replicas")
def ready():
    deploy_ready("api", minimum=2)

@task("api answers through its Service")
def http():
    ok, body = service_get("api", 80)
    expect(ok and "healthy" in body, f"Unexpected response: {body[:100]}")
```

   Available helpers (see `labctl/checks.py`): `sh`, `ssh`, `need`, `text_of`, `http_get`, `playbook`, `expect_playbook_clean`, `terraform`, `tf_state`, `tf_expect_no_changes`, `docker_running`, `kubectl`, `k_get`, `k_require`, `deploy_ready`, `service_get`, `gitlab`, `latest_pipeline`, `pipeline_jobs`, `load_yaml`, `expect`, `fail`, `skip`.

   Write failure messages that say what is wrong and where to look, not just "failed".
3. For break-fix labs, add `setup.sh`. It runs with `bash -euo pipefail` and gets `$LAB_DIR`, `$ANSIBLE_DIR`, `$TF_DIR`, `$APP_REPO`, `$K8S_NS`, `$NODE1`, `$NODE2`, `$SSH_OPTS`, and `$KUBECTL` (for k8s and capstone labs). Pass manifests through stdin, `$KUBECTL apply -f - < "$LAB_DIR/x.yaml"`, so this works over SSH too.
4. Run `pytest` (it validates every lab), then `lab show <id>`, then do the lab yourself and `lab check <id>`.

Run the site locally with `python scripts/build_site.py && python -m http.server -d _site 8000`.

## What it does and does not do

**Does**
- Checks real end state: HTTP responses, file modes over SSH, Ansible idempotency, Terraform drift, Kubernetes readiness and endpoints, GitLab pipelines, registry tags and environments.
- Creates broken environments for break-fix labs, and resets them.
- Tracks attempts, best score, hints used and solutions viewed locally.
- Publishes a static, searchable site for free with a single workflow.
- Includes AppSec checks along the way: Vault use, no secrets in output, 0600 secret files, non-root containers, `.gitignore` for state files, minimal-scope tokens.

**Does not**
- Run a terminal in the browser or host VMs. Everything runs on your machine.
- Sync progress between devices automatically. The website keeps progress per browser; `lab export` gives you a code to import there.
- Prevent cheating. The checks run on your own machine, so they help you learn rather than grade you.
- Randomize faults yet. Each break-fix lab has a fixed set of bugs.
- Come with end-to-end tests against live VMs. CI runs unit tests, schema checks and shellcheck. The first time through each lab, a check may be stricter or looser than intended; fix it and send a PR.
- Cover cloud providers. Terraform uses the local Docker provider, so it costs nothing.

## Ideas for next

- `lab break <track> --random`: a pool of faults per topic for replayable troubleshooting.
- Theory primer per lab (a short `theory.md` rendered above the tasks).
- Quizzes and interview questions per track.
- A timed mock exam mode (CKA-style): `lab exam k8s`.
- More labs: Ingress, PV/PVC, RBAC, NetworkPolicy, Helm, Prometheus/Grafana, Trivy/Kyverno, Terraform state in GitLab.
- Mirror the repo to GitLab and deploy the site with GitLab Pages as extra CI practice.

## License

MIT
