from labctl.checks import expect, gitlab, latest_pipeline, pipeline_jobs, project, task


def project_runners():
    return gitlab(f"{project()}/runners?type=project_type")


@task("A project runner is registered and online")
def online():
    runners = project_runners()
    expect(runners, "No project runner registered. Follow the registration steps on node2.")
    expect(any(r.get("status") == "online" for r in runners),
           "Your runner is not online. On node2: `sudo gitlab-runner verify` and `systemctl status gitlab-runner`.")


@task("The runner has the tag `lab`")
def tags():
    tagged = [r for r in project_runners() if "lab" in gitlab(f"/runners/{r['id']}").get("tag_list", [])]
    expect(tagged, "No project runner carries the tag `lab`. Edit the runner in Settings → CI/CD → Runners.")


@task("Instance (shared) runners are disabled for the project")
def shared_off():
    expect(not gitlab(project()).get("shared_runners_enabled"),
           "Instance runners are still enabled. Turn them off in Settings → CI/CD → Runners.")


@task("Latest default-branch pipeline passed on your runner")
def ran_on_mine():
    mine = {r["id"] for r in project_runners()}
    pipe = latest_pipeline()
    expect(pipe["status"] == "success", f"Latest pipeline is {pipe['status']}: {pipe['web_url']}")
    jobs = pipeline_jobs(pipe["id"]).values()
    used = {(j.get("runner") or {}).get("id") for j in jobs}
    expect(used & mine, "The pipeline's jobs did not run on your project runner. Add `tags: [lab]` and push.")
