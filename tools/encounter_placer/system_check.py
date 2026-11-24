"""Encounter card 7: whole-system checks on Privateer's Hold's markers, run in UZDoom alone (no Daggerfall).

usage: system_check.py [group...]      groups: stock drla ch den perf (default: all)

Each run is placer_test.py run (contract check included). Two runs of the same setup must place identical mooks.
Logs: D:\\dev\\DoomDaggerfall-loop\\review\\encounter-placer\\run\\log-<name>.txt and out-<name>.txt (the check output).
"""
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = Path(r"D:\dev\DoomDaggerfall-loop\review\encounter-placer\run")
PT = [sys.executable, str(HERE / "placer_test.py")]

# name, level, extra args; pairs (a, b) are compared.
GROUPS = {
    "stock": [(f"s{l}{r}", l, []) for l in (1, 10, 20, 30) for r in "ab"],
    "drla": [(f"d{l}{r}", l, ["--drla"]) for l in (1, 10, 20, 30) for r in "ab"],
    "ch": [(f"c{l}{r}", l, ["--ch"]) for l in (1, 10, 20, 30) for r in "ab"],
    # Dragon's Den (index 106 is synthetic: the test fakes the area facts on Privateer's Hold's map).
    "den": [(f"den{l}{r}", l, ["--ch", "--dungeon", "106", "DragonsDen"]) for l in (25, 30) for r in "ab"],
    "perf": [("perf30s", 30, ["--perf", "700"]), ("perf30c", 30, ["--ch", "--perf", "700"])],
}


def main():
    groups = [g for g in sys.argv[1:] if g in GROUPS] or list(GROUPS)
    summary = []
    for g in groups:
        for name, level, extra in GROUPS[g]:
            out = subprocess.run(PT + ["run", str(level), name] + extra, capture_output=True, text=True, errors="replace").stdout
            (RUN / f"out-{name}.txt").write_text(out)
            con = re.search(r"CONTRACT \S+: (\w+)", out)
            plan = re.search(r"DDENC plan genes (\d+) theme (\S+) civilwar (\d) pool (\d+) spent (\d+) mooks (\d+).*?bosses (\S+) titan (-?\d+) leftover (-?\d+) titanclass (\S+)", out)
            tim = re.search(r"total ([\d.]+) ms digest (\w+)", out)
            spawn = re.search(r"stuck (\d+) \((\d+) leaders\), ([\d.]+) ms with spawning", out)
            after = re.search(r"after 1 s: (\d+) placed monsters, (\d+) stuck", out)
            crowd = re.search(r"crowded-at-[\d.]+ (\d+)", out)
            perf = re.findall(r"perf (think|tic-to-tic \(minimized window\)) ms: (.*)", out)
            row = f"{name}: contract {con.group(1) if con else 'MISSING'}"
            if plan:
                row += f", theme {plan.group(2)} civilwar {plan.group(3)} pool {plan.group(4)} mooks {plan.group(6)} bosses {plan.group(7)} titan {plan.group(10)}@{plan.group(8)} leftover {plan.group(9)}"
            if crowd:
                row += f", crowded {crowd.group(1)}"
            if spawn:
                row += f", load {spawn.group(3)} ms, stuck at spawn {spawn.group(1)} ({spawn.group(2)} leaders)"
            if after:
                row += f", stuck after 1 s {after.group(2)}"
            if tim:
                row += f", digest {tim.group(2)}"
            for k, v in perf:
                row += f"\n    {k}: {v}"
            if "fatal none" not in out:
                row += "\n    " + (out.splitlines()[0] if out else "no output")
            print(row, flush=True)
            summary.append(row)
            if name.endswith("b"):
                cmp = subprocess.run(PT + ["compare", name[:-1] + "a", name], capture_output=True, text=True).stdout.strip()
                print("  " + cmp, flush=True)
                summary.append("  " + cmp)
    (RUN / ("summary-" + "-".join(groups) + ".txt")).write_text("\n".join(summary) + "\n")


if __name__ == "__main__":
    main()
