"""`lab` command line interface."""

from __future__ import annotations

import argparse
import getpass
import os
import re
import shutil
import sys
import textwrap

from . import __version__, catalog, checks, config, progress, runner

# ---------------------------------------------------------------- output helpers

COLOR = sys.stdout.isatty() and "NO_COLOR" not in os.environ


def c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if COLOR else text


def green(t): return c(t, "32")
def red(t): return c(t, "31")
def yellow(t): return c(t, "33")
def dim(t): return c(t, "2")
def bold(t): return c(t, "1")
def cyan(t): return c(t, "36")


WIDTH = min(shutil.get_terminal_size((100, 20)).columns, 100)


def md_to_term(s: str) -> str:
    s = re.sub(r"\*\*(.+?)\*\*", lambda m: bold(m.group(1)), s)
    s = re.sub(r"`([^`]+)`", lambda m: cyan(m.group(1)), s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", s)
    s = s.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    return s


def para(s: str, indent: int = 2) -> str:
    pad = " " * indent
    out = []
    for block in s.split("\n"):
        if block.startswith("|"):  # markdown table: print as-is
            out.append(pad + block)
        else:
            out.append(textwrap.fill(block, WIDTH - indent, initial_indent=pad, subsequent_indent=pad) or "")
    return md_to_term("\n".join(out))


def code(block: str, label: str = "") -> str:
    head = dim(f"  ┌─ {label}") if label else dim("  ┌─")
    body = "\n".join(dim("  │ ") + ln for ln in block.rstrip("\n").splitlines())
    return f"{head}\n{body}\n{dim('  └─')}"


def bar(passed: int, total: int, width: int = 20) -> str:
    filled = round(width * passed / total) if total else 0
    return green("█" * filled) + dim("░" * (width - filled))


def die(msg: str, code_: int = 1):
    print(red("error: ") + msg, file=sys.stderr)
    sys.exit(code_)


def confirm(question: str, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        die("This needs confirmation. Re-run with -y.")
    return input(f"{question} [y/N] ").strip().lower() in ("y", "yes")


def get_lab(query: str) -> catalog.Lab:
    try:
        return catalog.find(query)
    except LookupError as e:
        die(str(e))


def status_icon(e: dict | None) -> str:
    if not e:
        return dim("○")
    if e.get("done"):
        return green("●")
    if e.get("best"):
        return yellow("◐")
    return yellow("○")


def track_name(track_id: str) -> str:
    return next((t["name"] for t in catalog.tracks() if t["id"] == track_id), track_id)


def next_lab(prog: dict) -> catalog.Lab | None:
    return next((lab for lab in catalog.all_labs() if not prog.get(lab.id, {}).get("done")), None)


# ---------------------------------------------------------------- commands


def cmd_list(args):
    prog = progress.load()
    for t in catalog.tracks():
        if args.track and t["id"] != args.track:
            continue
        labs = [lab for lab in catalog.all_labs() if lab.track == t["id"]]
        done = sum(1 for lab in labs if prog.get(lab.id, {}).get("done"))
        print(bold(f"\n{t['name']}") + dim(f"  {done}/{len(labs)}"))
        for lab in labs:
            e = prog.get(lab.id)
            score = f"{e['best']}/{e['total']}" if e and e.get("total") else ""
            tag = yellow(" break-fix") if lab.breakfix else ""
            print(f"  {status_icon(e)} {lab.id:<12} {lab.title}{tag}  {dim(score)}")
    print(dim("\n● done  ◐ some tasks pass  ○ not started.  `lab show <id>` to read a lab."))


def cmd_show(args):
    lab = get_lab(args.lab)
    d = lab.data
    print(bold(f"\n{lab.id} · {lab.title}"))
    print(dim(f"  {track_name(lab.track)} · ~{lab.minutes} min" + (" · break-fix" if lab.breakfix else "")))
    print("\n" + bold("Scenario") + "\n" + para(d["scenario"]))
    print("\n" + bold("Tasks"))
    n = 0
    for st in d["steps"]:
        if st.get("text"):
            n += 1
            print(para(f"{n}. " + st["text"]))
        if st.get("code"):
            print(code(st["code"], st.get("lang", "")))
    print("\n" + bold("When you are done"))
    if lab.has_setup:
        print(para(f"Start with `lab start {lab.id}` (sets up the broken state)."))
    print(para(f"Run `lab check {lab.id}`. Stuck? `lab hint {lab.id}`."))
    print()


def cmd_start(args):
    lab = get_lab(args.lab)
    progress.mark(lab.id, started=progress.now())
    if not lab.has_setup:
        print(f"{lab.id} has no setup script: follow the tasks in `lab show {lab.id}`.")
        return
    print(bold(f"Setting up {lab.id} · {lab.title}"))
    if lab.breakfix and not confirm("This changes your lab machines to create the broken state. Continue?",
                                    args.yes):
        return
    try:
        rc = runner.run_script(lab, "setup")
    except checks.CheckFailed as e:
        die(str(e))
    if rc != 0:
        die(f"setup.sh exited with code {rc}")
    print(green("✓ Ready.") + f" Read the scenario with `lab show {lab.id}`, then `lab check {lab.id}`.")


def cmd_reset(args):
    lab = get_lab(args.lab)
    if not lab.has_reset:
        print(f"{lab.id} has no reset script. Restore your VMs with `vagrant snapshot restore clean`"
              + (f" and run `lab start {lab.id}` again." if lab.has_setup else "."))
        return
    if not confirm(f"Reset {lab.id}? This removes what the lab created.", args.yes):
        return
    try:
        rc = runner.run_script(lab, "reset")
    except checks.CheckFailed as e:
        die(str(e))
    if rc != 0:
        die(f"reset.sh exited with code {rc}")
    print(green("✓ Reset done."))


def cmd_check(args):
    lab = get_lab(args.lab)
    print(bold(f"\nChecking {lab.id} · {lab.title}"))
    try:
        tasks = runner.load_tasks(lab)
    except Exception as e:  # broken check.py
        die(f"Could not load the checks for {lab.id}: {type(e).__name__}: {e}")

    def show(r: runner.TaskResult):
        icon = {"pass": green("✓"), "skip": dim("–"), "fail": red("✗"), "error": yellow("!")}[r.status]
        print(f"  {icon} {r.title}  {dim(f'{r.seconds:.1f}s')}")
        if r.message and (r.status != "pass"):
            for line in r.message.splitlines():
                print("      " + (dim(line) if r.status == "skip" else line))
        if r.trace and args.verbose:
            print(dim(textwrap.indent(r.trace, "      ")))

    results = runner.run_tasks(tasks, fail_fast=args.fail_fast, on_result=show)
    total = len(tasks)
    passed = sum(1 for r in results if r.passed)
    was_done = progress.load().get(lab.id, {}).get("done", False)
    e = progress.record_check(lab.id, passed, total)
    pct = round(100 * passed / total) if total else 0
    print(f"\n  {passed}/{total} tasks passed  {bar(passed, total)}  {pct}%")
    if passed == total:
        nxt = next_lab(progress.load())
        msg = "All tasks passed." + ("" if was_done else f" {lab.id} marked complete.")
        print("  " + green(msg))
        if e.get("hints") or e.get("solution"):
            print(dim(f"  Hints used: {e.get('hints', 0)}" + (", solution viewed" if e.get("solution") else "")))
        if nxt:
            print(f"  Next: {bold(nxt.id)} · {nxt.title}  (`lab show {nxt.id}`)")
        else:
            print("  " + green("That was the last lab. You finished every track."))
    else:
        if any(r.status == "error" for r in results):
            print(yellow("  ! = the checker itself hit an error. Run with -v for details."))
        print(f"  Fix the failed tasks and run `lab check {lab.id}` again. Stuck? `lab hint {lab.id}`")
    print()
    sys.exit(0 if passed == total else 1)


def cmd_hint(args):
    lab = get_lab(args.lab)
    hints = lab.data["hints"]
    if not hints:
        print("This lab has no hints.")
        return
    e = progress.load().get(lab.id, {})
    shown = e.get("hints", 0)
    if args.all:
        upto = len(hints)
    elif shown >= len(hints):
        upto = len(hints)
        print(dim(f"All {len(hints)} hints are already revealed. Next step: `lab solution {lab.id}`."))
    else:
        upto = progress.bump_hints(lab.id)
    if args.all and upto > shown:
        progress.mark(lab.id, hints=upto)
    for i, h in enumerate(hints[:upto], 1):
        print(bold(f"Hint {i}/{len(hints)}") + "\n" + para(h) + "\n")


def cmd_solution(args):
    lab = get_lab(args.lab)
    if not confirm("Show the solution? Try `lab hint` first; it is recorded in your progress.", args.yes):
        return
    progress.mark(lab.id, solution=True)
    print(bold(f"\nSolution · {lab.id}"))
    for s in lab.data["solution"]:
        if s.get("text"):
            print(para(s["text"].replace("\n", "\n")))
        if s.get("code"):
            print(code(s["code"], s.get("lang", "")))
    print()


def cmd_status(args):
    prog = progress.load()
    labs = catalog.all_labs()
    done = sum(1 for lab in labs if prog.get(lab.id, {}).get("done"))
    print(bold("\nDevOps Lab Drills") + f"   {done}/{len(labs)} labs   {bar(done, len(labs), 30)}")
    for t in catalog.tracks():
        tl = [lab for lab in labs if lab.track == t["id"]]
        td = sum(1 for lab in tl if prog.get(lab.id, {}).get("done"))
        print(f"  {t['name']:<18} {bar(td, len(tl), 12)} {td}/{len(tl)}")
    hints = sum(v.get("hints", 0) for v in prog.values())
    sols = sum(1 for v in prog.values() if v.get("solution"))
    print(dim(f"\n  Hints used: {hints} · solutions viewed: {sols}"))
    nxt = next_lab(prog)
    if nxt:
        print(f"  Next up: {bold(nxt.id)} · {nxt.title}  (`lab show {nxt.id}`)")
    print()


def cmd_config(args):
    if args.action == "show" or args.action is None:
        for key, value, source in config.show():
            print(f"  {key:<17} {value:<40} {dim(source)}")
        print(dim("\n  Set with `lab config set <key> <value>`. Env vars LAB_<KEY> override everything."))
    elif args.action == "get":
        print(config.get(args.key))
    elif args.action == "set":
        if args.key not in config.DEFAULTS:
            die(f"Unknown key '{args.key}'. Known keys: {', '.join(config.DEFAULTS)}")
        value = args.value
        if value is None:
            if args.key in config.SECRET_KEYS:
                value = getpass.getpass(f"{args.key} (input hidden): ")
            else:
                die("Give a value: lab config set <key> <value>")
        config.set_value(args.key, value)
        print(green("✓ ") + f"{args.key} saved" + (" (file mode 600)" if args.key in config.SECRET_KEYS else ""))
    elif args.action == "unset":
        config.unset(args.key)
        print(green("✓ ") + f"{args.key} reset to default")


def cmd_doctor(args):
    print(bold("\nChecking your lab environment\n"))
    ok = lambda m: print(f"  {green('✓')} {m}")  # noqa: E731
    bad = lambda m: print(f"  {red('✗')} {m}")  # noqa: E731
    na = lambda m: print(f"  {dim('–')} {dim(m)}")  # noqa: E731

    print(f"  {dim('python ' + sys.version.split()[0] + ', labs at ' + str(catalog.labs_root()))}")
    for tool, track in [("ansible", "Ansible"), ("terraform", "Terraform"), ("docker", "Terraform"),
                        ("git", "GitLab"), ("ssh", "Ansible")]:
        (ok if shutil.which(tool) else na)(f"{tool} {'found' if shutil.which(tool) else 'not installed'} "
                                            f"({track} track)")
    if shutil.which("docker"):
        r = checks.sh("docker ps", timeout=10)
        (ok if r.ok else bad)("docker usable without sudo" if r.ok
                              else "docker needs sudo: `sudo usermod -aG docker $USER`, then log in again")
    for n in (1, 2):
        host = checks.node(n)
        r = checks.ssh(host, "true", timeout=10)
        (ok if r.ok else na)(f"key-based SSH to {host}" + ("" if r.ok else " not working yet (set up in ans-01)"))
    try:
        cmd = " ".join(checks.kube_command())
        ok(f"Kubernetes reachable via `{cmd}`")
    except checks.CheckFailed:
        na("No Kubernetes cluster reachable yet (set up in k8s-01)")
    if config.get("gitlab_token"):
        try:
            user = checks.gitlab("/user")
            ok(f"GitLab token works (user {user['username']})")
            if config.get("gitlab_project"):
                p = checks.gitlab(checks.project())
                ok(f"GitLab project {p['path_with_namespace']} found")
            else:
                na("gitlab_project not set")
        except checks.CheckFailed as e:
            bad(str(e))
    else:
        na("GitLab token not set (needed from gl-01)")
    repo = config.path("app_repo")
    (ok if (repo / ".git").exists() else na)(f"app repo {repo}" + ("" if (repo / ".git").exists() else " not cloned yet"))
    print()


def cmd_export(args):
    code_ = progress.export_code()
    if args.json:
        import json
        print(json.dumps(progress.load(), indent=2))
        return
    print(code_)
    print(dim("Paste this into the website's 'Import progress from the CLI' box to sync completed labs."),
          file=sys.stderr)


# ---------------------------------------------------------------- parser


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="lab", description="Start, check and track DevOps Lab Drills.")
    p.add_argument("--version", action="version", version=f"lab {__version__}")
    sub = p.add_subparsers(dest="cmd", metavar="<command>")

    s = sub.add_parser("list", help="list labs and your progress")
    s.add_argument("-t", "--track", help="only this track (setup, ansible, terraform, k8s, gitlab, capstone)")
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("show", help="print a lab: scenario, tasks, code")
    s.add_argument("lab")
    s.set_defaults(func=cmd_show)

    s = sub.add_parser("start", help="prepare a lab (break-fix labs create the broken state)")
    s.add_argument("lab")
    s.add_argument("-y", "--yes", action="store_true")
    s.set_defaults(func=cmd_start)

    s = sub.add_parser("check", help="run the automated checks for a lab")
    s.add_argument("lab")
    s.add_argument("-x", "--fail-fast", action="store_true", help="stop at the first failed task")
    s.add_argument("-v", "--verbose", action="store_true", help="show tracebacks for checker errors")
    s.set_defaults(func=cmd_check)

    s = sub.add_parser("hint", help="reveal the next hint")
    s.add_argument("lab")
    s.add_argument("--all", action="store_true")
    s.set_defaults(func=cmd_hint)

    s = sub.add_parser("solution", help="show the solution (recorded in progress)")
    s.add_argument("lab")
    s.add_argument("-y", "--yes", action="store_true")
    s.set_defaults(func=cmd_solution)

    s = sub.add_parser("reset", help="undo what a lab's setup created")
    s.add_argument("lab")
    s.add_argument("-y", "--yes", action="store_true")
    s.set_defaults(func=cmd_reset)

    s = sub.add_parser("status", help="progress summary and next lab")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("config", help="show or change settings")
    s.add_argument("action", nargs="?", choices=["show", "get", "set", "unset"])
    s.add_argument("key", nargs="?")
    s.add_argument("value", nargs="?")
    s.set_defaults(func=cmd_config)

    s = sub.add_parser("doctor", help="check which tools and machines are ready")
    s.set_defaults(func=cmd_doctor)

    s = sub.add_parser("export", help="print a progress code for the website")
    s.add_argument("--json", action="store_true", help="print the full progress JSON instead")
    s.set_defaults(func=cmd_export)
    return p


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        cmd_status(args)
        parser.print_usage()
        return
    if args.cmd == "config" and args.action in ("get", "set", "unset") and not args.key:
        die("Which key? Run `lab config show` to list keys.")
    try:
        args.func(args)
    except KeyboardInterrupt:
        print()
        sys.exit(130)
    except BrokenPipeError:  # e.g. `lab show x | head`
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(0)


if __name__ == "__main__":
    main()
