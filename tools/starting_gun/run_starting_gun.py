"""Checks the starting gun of a bridged New Game (card startgun 01) for each highest gun skill, with and without DRLA.

  run_starting_gun.py STAGE [--drla] [case ...]

A case is a skill name, or skills joined by '+' (a tie), or "none" (every gun skill 0: the starter pistol). Default: all
six skills, the Rifles+Pistols tie, and "none". Each case is one New Game through tools/new_game/run_new_game.py on a
private desktop, with Daggerfall's -dfstartguntest holding the skills. The DoomerfallStartingGunTest report must show
exactly the owner's guns, the owner's ammo, the first gun drawn in Doom, and Doom's ammo counters agreeing.
Writes every case's result to STAGE/test-run/startgun-<set>.txt.
"""
import re
import subprocess
import sys
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


def expected(case, drla):
    skills = ["Pistols"] if case == "none" else sorted(case.split("+"), key=ORDER.index)
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
    out = subprocess.run(cmd, capture_output=True, text=True, errors="replace").stdout
    df = (stage / "test-run" / "create-df.log").read_text(errors="replace") if (stage / "test-run" / "create-df.log").exists() else ""
    report = re.search(r"startguntest: report active=(\S+) guns=(\S*) \| table=(.*) \| settled=(\S+) totals=(\d+),(\d+),(\d+),(\d+)", df)
    gave = re.search(r"starting gun: .*", df)
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
    cases = [a for a in args if a != "--drla"] or ORDER + ["Rifles+Pistols", "none"]
    lines, passed = [], 0
    # run_new_game.py loads doomerfall-drla.pk3 whenever the stage has it, and it needs DRLA: set aside for stock runs.
    drla_pk3, aside = stage / "doomerfall-drla.pk3", stage / "doomerfall-drla.pk3.stock-run"
    if not drla and drla_pk3.exists():
        drla_pk3.rename(aside)
    try:
        for case in cases:
            ok, detail, gave = run_case(stage, case, drla)
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
