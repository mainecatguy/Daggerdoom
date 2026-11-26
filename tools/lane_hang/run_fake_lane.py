"""Fake lane: runs queue.ps1 in a throwaway git repo with a fake claude that leaves a "test game" running.

PASS when the lane logs Finished and starts its next card on time, and no fake game outlives the lane.
Costs nothing and touches no real branch. See tools/lane_hang/README.md.

Usage: python tools/lane_hang/run_fake_lane.py [--harness scripts/overnight] [--patch FILE] [--quiet-run]
                                               [--game-seconds 90] [--workdir DIR]
"""
import argparse
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
GIT_ENV = {"GIT_AUTHOR_NAME": "fake", "GIT_AUTHOR_EMAIL": "fake@example.invalid",
           "GIT_COMMITTER_NAME": "fake", "GIT_COMMITTER_EMAIL": "fake@example.invalid"}


def fake_games(seconds):
    """Process ids of fake games: python processes sleeping exactly this long."""
    out = subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                          "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                          "ForEach-Object { \"$($_.ProcessId)`t$($_.CommandLine)\" }"],
                         capture_output=True, text=True).stdout
    return [int(line.split("\t")[0]) for line in out.splitlines()
            if "\t" in line and f"time.sleep({float(seconds)})" in line]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--harness", default=os.path.join(HERE, "..", "..", "scripts", "overnight"))
    parser.add_argument("--game-seconds", type=int, default=90)
    parser.add_argument("--workdir", default=os.path.join(os.environ["TEMP"], "doomerfall-fake-lane"))
    parser.add_argument("--patch", help="apply this patch (paths from the repo root) to the copied harness first")
    parser.add_argument("--quiet-run", action="store_true",
                        help="start the fake game through the harness's quiet_run.py on a private desktop")
    args = parser.parse_args()
    work = os.path.abspath(args.workdir)
    if " " in work or " " in sys.executable:
        sys.exit("The fake lane needs paths without spaces (run.ps1 passes -ClaudePrefix unquoted).")
    env = dict(os.environ, **GIT_ENV)
    if args.quiet_run:
        env["FAKE_LANE_QUIET_RUN"] = os.path.join(work, "repo", "scripts", "overnight", "quiet_run.py")

    if os.path.exists(work):
        shutil.rmtree(work, ignore_errors=True)
    repo, run_dir = os.path.join(work, "repo"), os.path.join(work, "run")
    goals = os.path.join(repo, "work", "queue", "fake")
    os.makedirs(goals)
    os.makedirs(run_dir)
    shutil.copytree(os.path.abspath(args.harness), os.path.join(repo, "scripts", "overnight"))
    with open(os.path.join(repo, "README.md"), "w") as f:
        f.write("fake repo\n")
    setup = [["init", "-q", "-b", "main"]]
    if args.patch:
        setup.append(["apply", "--whitespace=nowarn", os.path.abspath(args.patch)])
    setup += [["add", "-A"], ["commit", "-q", "-m", "init"], ["branch", "integration"]]
    for cmd in setup:
        subprocess.run(["git", "-C", repo] + cmd, check=True, env=env)
    for n in ("01", "02"):
        with open(os.path.join(goals, f"{n}.fake.card{n}.md"), "w") as f:
            f.write(f"# Fake card {n}\n")

    fake = os.path.join(HERE, "fake_claude.py")
    queue = [
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
        os.path.join(repo, "scripts", "overnight", "queue.ps1"), "-Lane", "fake", "-GoalDir", goals,
        "-RunDir", run_dir, "-MaxUsd", "1", "-ClaudeExe", sys.executable,
        "-ClaudePrefix", f"{fake} {args.game_seconds}"]
    limit = max(60, args.game_seconds - 20)
    start = time.monotonic()
    with open(os.path.join(work, "lane.out"), "w") as out:
        lane = subprocess.Popen(queue, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env)
        try:
            lane.wait(limit)
            finished = True
        except subprocess.TimeoutExpired:
            finished = False
    elapsed = round(time.monotonic() - start, 1)

    games = fake_games(args.game_seconds)
    log_path = os.path.join(run_dir, "queue-fake.log")
    log = open(log_path, encoding="utf-8-sig").read() if os.path.exists(log_path) else ""
    print("--- queue log\n" + log)
    print(f"--- lane exited: {finished} after {elapsed} s (limit {limit} s); fake games still running: {len(games)}")
    for pid in games:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    if not finished:
        subprocess.run(["taskkill", "/PID", str(lane.pid), "/T", "/F"], capture_output=True)
    ok = finished and "Starting 02.fake.card02.md" in log and not games
    print("PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
