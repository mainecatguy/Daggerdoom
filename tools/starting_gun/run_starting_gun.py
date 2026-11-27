"""Checks the starting gun of a bridged New Game (card startgun 01) for each highest gun skill, with and without DRLA.

  run_starting_gun.py STAGE [--drla] [case ...]

A case names the character's class skills, joined by '+', each optionally "=value" (default 40); every other gun skill
keeps a realistic untrained value (3-6). "none": no gun class skill, so the highest untrained rolls (Rifles and Shotguns, 6) pick
the guns. Default: all six skills, the Rifles+Pistols tie, "none", and "EnergyWeapons+Shotguns=30" (Energy Weapons is
left out: the shotgun). Each case is one New Game through tools/new_game/run_new_game.py on a
private desktop, with Daggerfall's -dfstartguntest holding the skills. The DoomerfallStartingGunTest report must show
exactly the owner's guns, the owner's ammo, the first gun drawn in Doom, and Doom's ammo counters agreeing.
Writes every case's result to STAGE/test-run/startgun-<set>.txt.
"""
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
ORDER = ["Pistols", "Rifles", "Automatics", "Shotguns", "Explosives", "Melee"]
GUNS = {  # The owner's table: (DRLA gun, stock gun, ammo type 0-3 or None, divisor of N)
    "Pistols": ("RLPistolPickup", "Pistol", 0, 1),
    "Rifles": ("DoomerfallLightCarbine", "DoomerfallLightCarbine", 0, 1),
    "Automatics": ("RLChaingunPickup", "Chaingun", 0, 1),
    "Shotguns": ("RLShotgunPickup", "Shotgun", 1, 3),
    "Explosives": ("RLRocketLauncherPickup", "RocketLauncher", 2, 5),
    "Melee": ("RLChainsawPickup", "Chainsaw", None, 1),
}
N = {True: 60, False: 50}  # The starter pistol's bullets: DRLA's no-class pistol loadout, stock Doom's player.


UNTRAINED = {"Pistols": 3, "Rifles": 6, "Automatics": 5, "Shotguns": 6, "Explosives": 4, "Melee": 5}  # As the test holds them.


def expected(case, drla):
    named = {} if case == "none" else {p.split("=")[0]: int(p.split("=")[1]) if "=" in p else 40 for p in case.split("+")}
    values = {s: named.get(s, v) for s, v in UNTRAINED.items()}  # Energy Weapons is left out of the comparison.
    best = max(values.values())
    skills = sorted([s for s, v in values.items() if v == best], key=ORDER.index) if best > 0 else ["Pistols"]
    guns = [GUNS[s][0 if drla else 1] for s in skills]
    totals = [0, 0, 0, 0]
    for s in skills:
        kind, div = GUNS[s][2], GUNS[s][3]
        if kind is not None:
            totals[kind] = max(totals[kind], N[drla] // div)
    return guns, totals


def run_case(stage, case, drla):
    cmd = [sys.executable, QUIET, "--timeout", "200", "--", sys.executable, str(HERE.parent / "new_game" / "run_new_game.py"), "create",
           "--inside-quiet", "--review", str(stage), "--dfu-flag", "-dfstartguntest", "--dfu-flag", case, "--wait-df", "startguntest: done"]
    if drla:
        cmd.append("--drla")
    for _ in range(30):  # Never read an earlier case's report. Its Daggerfall may still be closing.
        try:
            (stage / "test-run" / "create-df.log").unlink(missing_ok=True)
            break
        except PermissionError:
            time.sleep(1)
    else:
        return False, "no report (the last case's log is still open)", ""
    done = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    out = done.stdout or done.stderr[-300:]
    df = (stage / "test-run" / "create-df.log").read_text(errors="replace") if (stage / "test-run" / "create-df.log").exists() else ""
    report = re.search(r"startguntest: report active=(\S+) guns=(\S*) \| table=(.*) \| settled=(\S+) totals=(\d+),(\d+),(\d+),(\d+)", df)
    gave = re.search(r"starting gun: Doom's starter.*", df)
    if not report:
        return False, f"no report ({out.strip().splitlines()[0] if out.strip() else 'no output'})", gave.group(0) if gave else ""
    guns, totals = expected(case, drla)
    active, held, table, settled = report.group(1), report.group(2).split("+"), report.group(3), report.group(4)
    got = [int(report.group(i)) for i in range(5, 9)]
    problems = []
    if sorted(held) != sorted(guns):
        problems.append(f"guns {held}, want {guns}")
    if active != guns[0]:
        problems.append(f"drawn {active}, want {guns[0]}")
    if got != totals:
        problems.append(f"ammo {got}, want {totals}")
    if settled != "True":
        problems.append("Doom's ammo counters do not agree")
    for g in guns:
        if g not in table:
            problems.append(f"{g} not on a hotkey")
    return not problems, "; ".join(problems) or f"guns {held}, drawn {active}, ammo {got}, table {table}", gave.group(0) if gave else ""


def main():
    args = sys.argv[1:]
    stage = Path(args.pop(0))
    drla = "--drla" in args
    cases = [a for a in args if a != "--drla"] or ORDER + ["Rifles+Pistols", "none", "EnergyWeapons+Shotguns=30"]
    lines, passed = [], 0
    # run_new_game.py loads doomerfall-drla.pk3 whenever the stage has it, and it needs DRLA: set aside for stock runs.
    drla_pk3, aside = stage / "doomerfall-drla.pk3", stage / "doomerfall-drla.pk3.stock-run"
    if not drla and drla_pk3.exists():
        drla_pk3.rename(aside)
    try:
        for case in cases:
            ok, detail, gave = run_case(stage, case, drla)
            if detail.startswith("no report"):  # The New Game driver sometimes stalls in character creation: one retry.
                print(f"retry {case}: {detail}", flush=True)
                ok, detail, gave = run_case(stage, case, drla)
                detail += " (second try)"
            passed += ok
            line = f"{'PASS' if ok else 'FAIL'} {'drla' if drla else 'stock'} {case}: {detail}\n    {gave}"
            print(line, flush=True)
            lines.append(line)
    finally:
        if aside.exists():
            aside.rename(drla_pk3)
    summary = f"result: {passed}/{len(cases)} pass ({'DRLA' if drla else 'stock'})"
    print(summary)
    (stage / "test-run" / f"startgun-{'drla' if drla else 'stock'}.txt").write_text("\n".join(lines + [summary]) + "\n")
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    sys.exit(main())
