from labctl.checks import (
    cfg_path,
    expect,
    gitlab,
    latest_pipeline,
    load_yaml,
    project,
    sh,
    task,
    text_of,
)


def CI():
    return cfg_path("app_repo") / ".gitlab-ci.yml"



@task("GitLab's linter accepts the pipeline")
def lint():
    res = gitlab(f"{project()}/ci/lint", method="POST", data={"content": text_of(CI())})
    expect(res.get("valid"), "Linter errors:\n" + "\n".join(res.get("errors", [])))


@task("No job mixes `only` with `rules`, and every stage exists")
def structure():
    ci = load_yaml(CI())
    stages = ci.get("stages", ["build", "test", "deploy"])
    for name, job in ci.items():
        if isinstance(job, dict) and "script" in job:
            expect(not ("only" in job and "rules" in job), f"{name} uses both only and rules.")
            expect(job.get("stage", "test") in stages, f"{name} uses stage {job.get('stage')!r}, not in {stages}.")


@task("Job tags match your runner's tags")
def tags():
    runner_tags = set()
    for r in gitlab(f"{project()}/runners?type=project_type"):
        runner_tags |= set(gitlab(f"/runners/{r['id']}").get("tag_list", []))
    ci = load_yaml(CI())
    for name, job in ci.items():
        if isinstance(job, dict) and job.get("tags"):
            missing = set(job["tags"]) - runner_tags
            expect(not missing, f"{name} asks for tags {sorted(missing)} that no runner has ({sorted(runner_tags)}).")


@task("build-image has a Docker daemon and logs in to the registry")
def docker():
    job = load_yaml(CI()).get("build-image", {})
    expect(any("dind" in str(s) for s in job.get("services", [])), "build-image has no docker:dind service.")
    expect("docker login" in str(job), "build-image never runs `docker login`.")


@task("Latest pipeline on your current branch passed")
def pipeline():
    branch = sh("git rev-parse --abbrev-ref HEAD", cwd=cfg_path("app_repo")).out.strip()
    pipe = latest_pipeline(branch)
    expect(pipe["status"] == "success", f"Pipeline on {branch} is {pipe['status']}: {pipe['web_url']}")
