"""Stands in for the claude CLI in a fake overnight run (see tools/lane_hang/README.md).

It leaves behind a "test game": a child process that inherits every inheritable handle, as quiet_run.py's games do,
and that outlives this fake agent. With FAKE_LANE_HELPER set it also leaves a fake build helper that must survive.
Then it reports BLOCKED, like a real round that gives up.
Usage (as queue.ps1's -ClaudeExe python -ClaudePrefix "<this file> <seconds>"): python fake_claude.py SECONDS [claude args...]
"""
import json
import os
import subprocess
import sys

seconds = float(sys.argv[1])
sys.stdin.read()
sleeper = [sys.executable, "-c", f"import time; time.sleep({seconds})"]
if os.environ.get("FAKE_LANE_QUIET_RUN"):
    # The realistic case: the game runs on quiet_run.py's private desktop, with a timeout longer than the run.
    sleeper = [sys.executable, os.environ["FAKE_LANE_QUIET_RUN"], "--timeout", "600", "--"] + sleeper
# close_fds=False keeps handle inheritance on, the same as CreateProcessW(..., bInheritHandles=True) in quiet_run.py.
game = subprocess.Popen(sleeper, close_fds=False,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
if os.environ.get("FAKE_LANE_HELPER"):
    # A fake build helper (named MSBuild.exe, like an MSBuild reuse node) that the harness must leave running.
    helper = subprocess.Popen([os.environ["FAKE_LANE_HELPER"], str(int(seconds))], close_fds=False,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    with open(os.environ["FAKE_LANE_HELPER"] + ".started", "a") as f:
        f.write(f"{helper.pid}\n")
print(json.dumps({"type": "result", "subtype": "success", "session_id": None, "total_cost_usd": 0.01,
                  "num_turns": 1, "permission_denials": [],
                  "structured_output": {"status": "BLOCKED", "summary": f"fake run; left game pid {game.pid}"}}))
