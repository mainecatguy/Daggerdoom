"""Runs the full real-game save suite and prints one line per case. Full output goes to test/suite.txt."""
import re
import statistics
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\synchronized-saving")
TEST = REVIEW / "test"
HORDE, COMBAT = str(REVIEW / "horde2000.pk3"), str(REVIEW / "combat.pk3")
SAVE, INDOOR, CONTROLS = str(HERE / "run_save.py"), str(HERE / "run_indoor.py"), str(HERE / "run_controls.py")
out = open(TEST / "suite.txt", "w", encoding="utf-8")
failed = 0


def run(script, *args):
    result = subprocess.run([sys.executable, script, *args], capture_output=True, text=True, errors="replace")
    out.write(f"\n##### {Path(script).name} {' '.join(args)}\n{result.stdout}{result.stderr}")
    out.flush()
    return result.stdout


def has(text, *needles):
    return all(n in text for n in needles)


def report(name, ok, detail=""):
    global failed
    failed += not ok
    print(f"{'PASS' if ok else 'FAIL'} {name} {detail}", flush=True)


def hitch(text):
    values = [float(v) for v in re.findall(r"committed \(both games saved\), ([\d.]+) ms frozen", text)]
    return f"{len(values)} saves, median {statistics.median(values):.0f} ms, worst {max(values):.0f} ms" if values else "no saves"


def barrier(name):
    """No HP event may leave Doom between the freeze and the commit."""
    inside, leaks = False, 0
    for line in (TEST / name / "uz.log").read_text(errors="replace").splitlines():
        if "Doom frozen" in line:
            inside = True
        elif " committed " in line or "FAILED" in line:
            inside = False
        elif inside and "hp: sent" in line:
            leaks += 1
    return leaks


GOOD = ("zip test: ok", "doom entries present: True", "manifest files match: True", "owner registry key unchanged: True", "leftovers: []")
text = run(SAVE, "real1")
match = re.search(r"'hp': (\d+).*'doom_hp': (\d+)", text)
report("menu save", has(text, *GOOD, "health 80 of 100") and bool(match) and match.group(1) == match.group(2) == "80", hitch(text))
for step in ("df_write", "uz_zip", "uz_commit", "uz_crash"):
    text = run(SAVE, "real1", "--keep-old", "--fail", step)
    report(f"failure {step}", has(text, "previous save byte-identical: True", "owner registry key unchanged: True"))
text = run(SAVE, "auto", "--auto", "6", "--bundle", "auto00.zds", "--timeout", "40")
report("autosaves", has(text, *GOOD) and text.count("autosave committed") == 6, hitch(text))
text = run(SAVE, "auto", "--auto", "3", "--keep-old", "--fail", "df_write", "--bundle", "auto00.zds")
report("failed autosaves, play resumes", has(text, "previous save byte-identical: True") and text.count("autosave FAILED") == 3 and text.count("resumed, paused False, time scale 1") == 3)
text = run(SAVE, "horde", "--auto", "6", "--bundle", "auto00.zds", "--timeout", "45", "--mod", HORDE)
report("2,000 monsters", has(text, *GOOD, "SAVEHORDE placed 2000") and text.count("autosave committed") == 6, hitch(text))
text = run(SAVE, "combat", "--auto", "10", "--bundle", "auto00.zds", "--timeout", "40", "--mod", COMBAT)
leaks = barrier("combat")
report("HP events every tic", has(text, *GOOD) and text.count("autosave committed") == 10 and leaks == 0, f"{hitch(text)}, {leaks} events past the freeze")
for mode, context in (("early", "'context': 1"), ("building", "'context': 2"), ("dungeon", "'context': 3")):
    text = run(INDOOR, mode)
    world = re.search(r"'df_world': \[(\d+), (\d+)\], 'doom_world': \[([\d.]+), ([\d.]+)", text)
    near = bool(world) and abs(float(world.group(1)) - float(world.group(3))) <= 1 and abs(float(world.group(2)) - float(world.group(4))) <= 1
    report(f"autosave {mode}", has(text, *GOOD, context) and near, hitch(text))
text = run(SAVE, "real1")
text = run(CONTROLS, "load")
report("Daggerfall loads the bundle's half", "load test: loaded health 80/100" in text)
text = run(CONTROLS, "plain")
report("normal Daggerfall save", has(text, "plain save test: files", "Screenshot.jpg", "SaveData.txt", "owner registry key unchanged: True"))
for mode in ("stock", "drla"):
    text = run(CONTROLS, mode)
    report(f"no bridge {mode}", has(text, f"{mode} finished", "auto01.zds zip ok doomerfall entries: 0 stock entries: True", "save00.zds zip ok doomerfall entries: 0 stock entries: True", "bridge lines in console: 0"))
print("failed cases:", failed)
out.close()
sys.exit(1 if failed else 0)
