from labctl.checks import (
    cfg_path,
    expect,
    gitlab,
    latest_pipeline,
    load_yaml,
    pipeline_jobs,
    project,
    task,
)


@task("GitLab project and token are configured")
def configured():
    p = gitlab(project())
    expect(p.get("default_branch"), "The project has no default branch yet. Push your first commit.")


@task(".gitlab-ci.yml in your clone defines stages lint and test")
def ci_file():
    ci = load_yaml(cfg_path("app_repo") / ".gitlab-ci.yml")
    expect(isinstance(ci, dict), ".gitlab-ci.yml is empty.")
    stages = ci.get("stages", [])
    expect("lint" in stages and "test" in stages, f"stages is {stages}, expected lint and test.")
    test = ci.get("test", {})
    expect("junit" in str(test.get("artifacts", {})), "The test job does not publish a JUnit report.")


@task("Latest pipeline on the default branch passed, with lint and test jobs")
def pipeline():
    pipe = latest_pipeline()
    expect(pipe["status"] == "success", f"Latest pipeline #{pipe['id']} is {pipe['status']}: {pipe['web_url']}")
    jobs = pipeline_jobs(pipe["id"])
    for name in ("lint", "test"):
        expect(name in jobs, f"No job called {name} in pipeline #{pipe['id']}.")
        expect(jobs[name]["status"] == "success", f"Job {name} is {jobs[name]['status']}.")


@task("Test report has at least one test and no failures")
def report():
    pipe = latest_pipeline()
    rep = gitlab(f"{project()}/pipelines/{pipe['id']}/test_report")
    expect(rep.get("total_count", 0) >= 1, "The pipeline has no test report. Check artifacts:reports:junit.")
    expect(rep.get("failed_count", 0) == 0, f"{rep['failed_count']} test(s) failed.")
