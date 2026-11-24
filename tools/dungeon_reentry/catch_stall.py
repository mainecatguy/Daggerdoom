"""Repeats one scenario. When its log stops growing, reports whether UZDoom is busy or waiting, and its thread stacks if cdb is installed.

Usage: catch_stall.py EXE SCENARIO [runs] [cycles]
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

exe, scenario = Path(sys.argv[1]).resolve(), sys.argv[2]
runs, cycles = int(sys.argv[3]) if len(sys.argv) > 3 else 4, sys.argv[4] if len(sys.argv) > 4 else "10"
FOLDER = Path(r"D:\dev\DoomDaggerfall-loop\review\dungeon-reentry\test") / f"{exe.parent.parent.name}-{scenario}"
CDB = r"C:\Program Files (x86)\Windows Kits\10\Debuggers\x64\cdb.exe"
QUERY = "Get-CimInstance Win32_Process -Filter \"Name='uzdoom.exe'\" | Select-Object ProcessId,CommandLine,KernelModeTime,UserModeTime,ThreadCount,WorkingSetSize | ConvertTo-Json"


def game():
    out = subprocess.run(["powershell", "-NoProfile", "-Command", QUERY], capture_output=True, text=True).stdout.strip()
    if not out:
        return None
    rows = json.loads(out)
    rows = rows if isinstance(rows, list) else [rows]
    return next((r for r in rows if str(FOLDER) in (r.get("CommandLine") or "")), None)


for attempt in range(runs):
    time.sleep(0.2)
    check = subprocess.Popen([sys.executable, str(Path(__file__).parent / "check.py"), "--exe", str(exe), "--only", scenario, "--cycles", cycles], stdout=subprocess.PIPE, text=True)
    log, size, changed, caught = FOLDER / "log-console.txt", -1, time.time(), False
    while check.poll() is None:
        time.sleep(0.5)
        now = log.stat().st_size if log.exists() else 0
        if now != size:
            size, changed = now, time.time()
        if size > 0 and time.time() - changed > 6 and not caught:
            first = game()
            if not first:
                continue
            caught = True
            time.sleep(2)
            second = game() or first
            busy = (int(second["KernelModeTime"]) + int(second["UserModeTime"]) - int(first["KernelModeTime"]) - int(first["UserModeTime"])) / 1e7
            print(f"attempt {attempt}: log idle, UZDoom pid {first['ProcessId']} used {busy:.2f} CPU-seconds over about 2 s, threads {second['ThreadCount']}, memory {int(second['WorkingSetSize']) // 1048576} MB", flush=True)
            print("last log lines:", log.read_text(errors="replace").splitlines()[-2:], flush=True)
            if os.path.exists(CDB):
                stacks = subprocess.run([CDB, "-p", str(first["ProcessId"]), "-pv", "-c", ".symfix+ nosuch; ~0kc 25; ~*kc 3; q"], capture_output=True, text=True, timeout=60, errors="replace").stdout
                (FOLDER.parent / "stall-stacks.txt").write_text(stacks)
                print("stacks saved", FOLDER.parent / "stall-stacks.txt", flush=True)
            else:
                print("cdb not installed", flush=True)
    print(f"attempt {attempt}:", check.stdout.read().splitlines()[0][:150], flush=True)
    if caught:
        break
