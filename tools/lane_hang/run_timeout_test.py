"""Timeout path of the patched Invoke-Logged (run.ps1): the child never exits, so Invoke-Logged waits its 60 s minimum,
ends the child, and must close the test game it left while keeping the build helper. See tools/lane_hang/README.md.

PASS when Invoke-Logged returns -1, the child and the fake game are gone, and the fake MSBuild.exe is still running.
Takes about 65 s and costs nothing.
Usage: python tools/lane_hang/run_timeout_test.py [--patch tools/lane_hang/harness-fix.patch] [--workdir DIR]
"""
import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from run_fake_lane import build_helper, fake_games, fake_helpers, GIT_ENV  # noqa: E402

GAME_SECONDS = 91
CHILD = f"""import subprocess, sys, time
subprocess.Popen([sys.executable, "-c", "import time; time.sleep({float(GAME_SECONDS)})"], close_fds=False)
helper = subprocess.Popen([sys.argv[1], "{GAME_SECONDS}"], close_fds=False)
print("helper", helper.pid, sys.argv[1], flush=True)
time.sleep(300)  # never finishes in time: Invoke-Logged must time it out
"""
# Loads only Write-Text and Invoke-Logged from the patched run.ps1, as run.ps1 defines them.
DRIVER = r"""param([string]$RunPs1, [string]$Child, [string]$Helper, [string]$Log)
. (Join-Path (Split-Path $RunPs1) 'lane_job.ps1')
$ast = [Management.Automation.Language.Parser]::ParseFile($RunPs1, [ref]$null, [ref]$null)
$ast.FindAll({ param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst] -and
        $n.Name -in 'Write-Text', 'Invoke-Logged' }, $false) | ForEach-Object { . ([scriptblock]::Create($_.Extent.Text)) }
$Worktree = Split-Path $Child
$Deadline = Get-Date
$code = Invoke-Logged ((Get-Command python).Source) "`"$Child`" `"$Helper`"" '' $Log
Write-Output "code=$code"
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--patch", default=os.path.join(HERE, "harness-fix.patch"))
    parser.add_argument("--workdir", default=os.path.join(os.environ["TEMP"], "doomerfall-timeout-test"))
    args = parser.parse_args()
    work = os.path.abspath(args.workdir)
    shutil.rmtree(work, ignore_errors=True)
    repo = os.path.join(work, "repo")
    os.makedirs(repo)
    shutil.copytree(os.path.join(HERE, "..", "..", "scripts", "overnight"), os.path.join(repo, "scripts", "overnight"))
    env = dict(os.environ, **GIT_ENV)
    subprocess.run(["git", "-C", repo, "init", "-q"], check=True, env=env)
    subprocess.run(["git", "-C", repo, "apply", "--whitespace=nowarn", os.path.abspath(args.patch)], check=True, env=env)
    helper = os.path.join(work, "helper", "MSBuild.exe")
    os.makedirs(os.path.dirname(helper))
    build_helper(helper)
    child, driver = os.path.join(work, "child.py"), os.path.join(work, "driver.ps1")
    open(child, "w").write(CHILD)
    open(driver, "w").write(DRIVER)

    # Driver output goes to a file, as patched queue.ps1 sends run.ps1's. (With a pipe here, the fake helper died when
    # the driver exited, even though the cleanup had left it running.)
    log = os.path.join(work, "driver.out")
    with open(log, "w") as f:
        subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", driver,
                        "-RunPs1", os.path.join(repo, "scripts", "overnight", "run.ps1"), "-Child", child,
                        "-Helper", helper, "-Log", os.path.join(work, "child.log")],
                       stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, timeout=180)
    out = subprocess.CompletedProcess([], 0, open(log).read(), "")
    print(out.stdout + out.stderr)
    games, helpers = fake_games(GAME_SECONDS), fake_helpers(helper)
    children = [l for l in subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command",
         "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | ForEach-Object { $_.CommandLine }"],
        capture_output=True, text=True).stdout.splitlines() if "child.py" in l]
    print(f"--- games left: {len(games)}; child left: {len(children)}; fake build helpers alive: {len(helpers)} of 1")
    for pid in games + helpers:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    ok = "code=-1" in out.stdout and not games and not children and len(helpers) == 1
    print("PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
