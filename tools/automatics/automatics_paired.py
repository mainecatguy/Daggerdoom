"""Automatics perks, Daggerfall and Doom together: Daggerfall's skill decides the rules and Doom applies them.

usage: automatics_paired.py <play folder> assemble <base play folder> <uzdoom build Release dir> <bridge dll>
       automatics_paired.py <play folder> run

  assemble  like tools/perk_popup (base play folder of the same bridge layout, this repo's Unity build), then this
            branch's UZDoom build, doomerfall.pk3 and bridge DLL replace the base's.
  run       Daggerfall city with -dfperktest Automatics -dfperksteps 20,26,50,75,100: Daggerfall sets the Automatics
            skill to each value in turn and opens a perk window at 25, 50, 75 and 100, which the script clicks shut.
            The Doom harness (automatics_paired.zs) fires DRLA's Chaingun at a target in cycles and logs each one.
Checks, per cycle: the rules Doom read match Daggerfall's skill (DoomerfallAutomaticsRules.cs); every hit carries the
right factor (damage bonus, and the burst bonus on shots 1-3); ammo use follows one ammo per 1, 2 or 4 shots; the probe
hit shows the sunder stacks. Wrap the whole script in quiet_run.py. Output goes to <play folder>/../automatics-paired.
"""
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / "perk_popup"))
sys.path.insert(0, str(HERE.parent / "new_game"))
import perk_popup as pp  # noqa: E402
import run_new_game as ng  # noqa: E402

TIMEOUT = 170
STEPS = "20,26,50,75,100"
HIT = re.compile(r"automatics: hit (\S+) with (\S+) shot (\d+)( burst)?: (\d+) -> (\d+) \(x([\d.]+)\)")


def rules(skill):
    s = max(0, min(skill, 100))
    return {"dmg": 6000 * s // 100, "burstbp": 3000 if skill >= 25 else 0, "burstn": 3 if skill >= 25 else 0,
            "per": 4 if skill >= 100 else 2 if skill >= 50 else 1,
            "sunder": "200/3000" if skill >= 100 else "100/1500" if skill >= 75 else "0/0"}


def free_every(skill):
    return 3 if 25 <= skill < 50 else 0  # skillperks 09: every third shot free at 25, replaced by 50's one per 2


def assemble(play, base, build, dll):
    pp.assemble(play, base)
    for f in Path(build).iterdir():
        if f.suffix.lower() in (".exe", ".pk3", ".dll"):
            shutil.copy2(f, play / "uzdoom" / f.name)
    subprocess.run([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(play / "doomerfall.pk3")], check=True)
    shutil.copy2(dll, play / "dfu" / "DaggerfallUnity_Data" / "Plugins" / "x86_64" / "doomerfall_bridge.dll")


def run(play, out):
    harness = out / "autopair-harness.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.write(HERE / "automatics_paired.zs", "zscript.txt")
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "AutoPairHarness" }\n')
    uz_log, df_log, console, launcher = out / "uz.log", out / "df.log", out / "log-autopair.txt", out / "launcher.log"
    for path in (uz_log, df_log, console, launcher):
        path.unlink(missing_ok=True)
    data = play / "data"
    uz = ["-noactivate", "-nosound", "-config", str(out / "autopair.ini"), "-savedir", str(out / "saves"), "-dfbridgelog", str(uz_log),
          "-ddtowncache", str(data / "cache"), "-ddconverter", str(data / "converter" / "DungeonConverter.exe"), "-ddarena2", ng.DAGGER + r"\ARENA2",
          "+logfile", "autopair", "+vid_fullscreen", "0", "+wipetype", "0", "+set", "dd_perklog", "1",
          "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "-skill", "3", "+map", "DDOVER01"]
    df = ["-dfbridgelog", str(df_log), "-dfmute", "-screen-fullscreen", "0", "-screen-width", "1280", "-screen-height", "800",
          "-dfsynctest", ng.DAGGER, "-dfperktest", "Automatics", "-dfperksteps", STEPS]
    command = [str(play / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
               "--uzdoom", str(play / "uzdoom" / "uzdoom.exe"), "--dfu", str(play / "dfu" / "DaggerfallUnity.exe"), "--iwad", ng.IWAD,
               "--uzdoom-cwd", str(out), "--log", str(launcher)]
    for mod in pp.DRLA + [data / n for n in pp.DATA] + [play / "dfitems.pk3", play / "doomerfall.pk3", harness]:
        command += ["--mod", str(mod)]
    for arg in uz:
        command += ["--uzdoom-arg", arg]
    for arg in df:
        command += ["--dfu-arg", arg]

    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline, hwnd, clicked, fatal = time.time() + TIMEOUT, None, 0, False
    try:
        while time.time() < deadline and proc.poll() is None:
            time.sleep(0.3)
            text, uzt, dft = ng.read(console), ng.read(uz_log), ng.read(df_log)
            if any(k in text for k in pp.FATAL) or re.search(r"Script error.*(autopair-harness|doomerfall\.pk3)", text):
                fatal = True
                break
            hwnd = hwnd or ng.doom_window(launcher)
            opened = dft.count("ui: menu 7 opened")
            if hwnd and opened > clicked:
                time.sleep(1.0)
                size = re.findall(r"opened menu 7 at (\d+)x(\d+)", uzt)
                if size:
                    ng.SURFACE[:] = [int(size[-1][0]), int(size[-1][1])]
                ng.click(hwnd, 160, 100)
                clicked = opened
            if "raised to 100" in dft and len(re.findall(r"PAIRED end \d+ skill=100 ", text)) >= 2:
                break
    finally:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    analyse(out, ng.read(console), ng.read(df_log), fatal)


def analyse(out, text, dft, fatal):
    report, checks = [], {}

    def check(name, ok, detail=""):
        checks[name] = checks.get(name, True) and bool(ok)
        if not ok:
            report.append(f"FAIL {name}: {detail}")

    check("no fatal or script error", not fatal)
    cycles, cur, hits = [], None, []
    for l in text.splitlines():
        if m := re.search(r"PAIRED start (\d+) skill=(-?\d+) dmg=(-?\d+) burstbp=(-?\d+) burstn=(-?\d+) per=(-?\d+) sunder=(-?\d+/-?\d+)", l):
            cur = {"skill": int(m.group(2)), "read": {"dmg": int(m.group(3)), "burstbp": int(m.group(4)), "burstn": int(m.group(5)),
                                                      "per": int(m.group(6)), "sunder": m.group(7)}, "shots": [], "line": l, "all": []}
            cycles.append(cur)
        elif "AUTOTEST fire" in l:
            hits = []
        elif (h := HIT.search(l)) and cur:
            hits.append(h)
            cur["all"].append(h)  # every landed bullet of the cycle, including those fired in the tics after a pull
        elif (s := re.search(r"PAIRED shot \d+ n=(\d+) ammo=(-?\d+)->(-?\d+) lost=(\d+)", l)) and cur:
            cur["shots"].append((int(s.group(1)), int(s.group(4)), hits))
            hits = []
        elif (e := re.search(r"PAIRED end \d+ skill=(-?\d+) shots=(\d+) hits=(\d+) ammo=(-?\d+)->(-?\d+) probe=(\d+)", l)) and cur:
            cur["end"] = {"skill": int(e.group(1)), "shots": int(e.group(2)), "hits": int(e.group(3)),
                          "used": int(e.group(4)) - int(e.group(5)), "probe": int(e.group(6))}
    done = [c for c in cycles if "end" in c and c["end"]["skill"] == c["skill"]]  # skip cycles the skill changed in
    seen = sorted({c["skill"] for c in done})
    report.append(f"skills seen in whole cycles: {seen}")
    # 20 lasts only one second (the test lowers then raises), so whole cycles are needed at 26 and up.
    check("cycles at every step (26, 50, 75, 100)", all(s in seen for s in (26, 50, 75, 100)), seen)
    # Ammo per trigger pull without ammo saving (cycles below 50), the baseline for one ammo per n shots.
    # (Skill 25-49 spends ammo on two shots of three, so its use is scaled back up to the baseline.)
    base = [c["end"]["used"] / c["end"]["shots"] * (1.5 if free_every(c["skill"]) else 1)
            for c in done if rules(c["skill"])["per"] == 1 and c["end"]["shots"]]
    per_pull = sum(base) / len(base) if base else 1
    report.append(f"ammo per pull without saving: {per_pull:.2f}")
    for c in done:
        want = rules(c["skill"])
        check("Doom read Daggerfall's rules for the skill", c["read"] == want, f"skill {c['skill']}: read {c['read']} want {want}")
        f_base = 1 + want["dmg"] / 10000
        for n, lost, hl in c["shots"]:
            f = f_base * (1 + want["burstbp"] / 10000 if want["burstn"] and n <= want["burstn"] else 1)
            for h in hl:
                check("every hit has the right factor", abs(float(h.group(7)) - f) < 1e-3, f"skill {c['skill']} shot {n}: x{h.group(7)} want x{f:.4f}")
            if lost > 0 and f != 1:
                check("every hit that landed was boosted", hl, f"skill {c['skill']} shot {n} lost {lost} with no hit line")
        e = c["end"]
        # A DRLA Chaingun pull fires a short string; every landed bullet has a hit line (all skills here have a bonus).
        bullets = len(c["all"])
        expect_used = e["shots"] * per_pull / want["per"] * (2 / 3 if free_every(c["skill"]) else 1)
        check("ammo follows one ammo per n shots", abs(e["used"] - expect_used) <= 1.01, f"skill {c['skill']}: used {e['used']} for {e['shots']} pulls, want {expect_used:.1f} (per {want['per']})")
        expect_probe = 100 + (min(2 * bullets, 30) if want["sunder"] == "200/3000" else min(bullets, 15) if want["sunder"] != "0/0" else 0)
        check("sunder: the probe hit shows the stacks", e["probe"] == expect_probe, f"skill {c['skill']}: probe {e['probe']} want {expect_probe} ({bullets} bullets hit)")
        report.append(f"skill {c['skill']}: pulls {e['shots']} bullets hit {bullets} ammo used {e['used']} probe {e['probe']} "
                      f"bonus shots {sum(1 for _, _, hl in c['shots'] if hl)}")
    report.append(f"perk windows: {dft.count('ui: menu 7 opened')} opened, {dft.count('ui: menu 7 closed')} closed")
    report += [l for l in dft.splitlines() if "perktest" in l or "perks: " in l]
    result = "AUTOMATICS PAIRED " + ("PASS" if checks and all(checks.values()) else "FAIL")
    lines = [result] + [f"{'ok  ' if v else 'FAIL'} {k}" for k, v in checks.items()] + [""] + report
    (out / "result.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    play = Path(sys.argv[1]).resolve()
    out = play.parent / "automatics-paired"
    out.mkdir(parents=True, exist_ok=True)
    if sys.argv[2] == "assemble":
        assemble(play, Path(sys.argv[3]).resolve(), sys.argv[4], sys.argv[5])
    else:
        run(play, out)
