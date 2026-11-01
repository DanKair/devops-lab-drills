import re

from labctl.checks import (
    cfg_path,
    expect,
    gitlab,
    latest_pipeline,
    load_yaml,
    pipeline_jobs,
    project,
    task,
    text_of,
)


@task("Dockerfile runs the app as a non-root user")
def nonroot():
    text = text_of(cfg_path("app_repo") / "Dockerfile")
    users = re.findall(r"^\s*USER\s+(\S+)", text, re.MULTILINE)
    expect(users, "The Dockerfile has no USER instruction, so the container runs as root.")
    expect(users[-1] not in ("root", "0"), f"Final USER is {users[-1]}.")


@task("Pipeline has workflow rules, SAST and secret detection")
def pipeline_config():
    raw = text_of(cfg_path("app_repo") / ".gitlab-ci.yml")
    ci = load_yaml(cfg_path("app_repo") / ".gitlab-ci.yml")
    expect("workflow" in ci, "No workflow: rules block (prevents duplicate branch + MR pipelines).")
    expect("Jobs/SAST" in raw, "SAST template is not included.")
    expect("Secret-Detection" in raw, "Secret detection template is not included.")


@task("build job only runs on the default branch")
def build_rules():
    ci = load_yaml(cfg_path("app_repo") / ".gitlab-ci.yml")
    build = ci.get("build", {})
    expect(build, "No job called build.")
    expect("CI_DEFAULT_BRANCH" in str(build.get("rules", "")), "build should have a rule on $CI_DEFAULT_BRANCH.")


@task("Latest default-branch pipeline passed, including build")
def pipeline():
    pipe = latest_pipeline()
    expect(pipe["status"] == "success", f"Latest pipeline is {pipe['status']}: {pipe['web_url']}")
    jobs = pipeline_jobs(pipe["id"])
    expect(jobs.get("build", {}).get("status") == "success", "The build job did not succeed in that pipeline.")


@task("Registry has an image tagged with that commit's short SHA")
def registry():
    pipe = latest_pipeline()
    repos = gitlab(f"{project()}/registry/repositories?tags=true")
    expect(repos, "The container registry is empty.")
    tags = {t["name"] for r in repos for t in r.get("tags") or []}
    expect(any(pipe["sha"].startswith(t) for t in tags if len(t) >= 7),
           f"No tag matches commit {pipe['sha'][:8]}. Tags found: {sorted(tags)[:5]}")
