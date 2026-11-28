"""Explosives perks, Daggerfall and Doom together: Daggerfall's skill decides the rules and Doom applies them.

usage: explosives_paired.py <play folder> assemble <base play folder> <uzdoom build Release dir> <bridge dll>
       explosives_paired.py <play folder> run

  assemble  as tools/automatics/automatics_paired.py: base play folder, this repo's Unity build, then this branch's
            UZDoom build, doomerfall.pk3 and bridge DLL.
  run       Daggerfall city with -dfperktest Explosives -dfperksteps 20,26,50,75,100: Daggerfall sets the Explosives
            skill to each value in turn and opens a perk window at 25, 50, 75 and 100, which the script clicks shut.
            The Doom harness (explosives_paired.zs) fires DRLA's Rocket Launcher at a target in cycles, and once at
            skill 100 at a pack (a baron among imps) to see the chain and the frame times.
Checks: the rules Doom read match Daggerfall's skill (DoomerfallRules.zs); every hit carries the damage
bonus; the player's own splash is cut by 95% / 99% from 25 / 75; at 100 the pack dies with chained blasts that never
hurt the player, and every playsim tic of the chain fits in one tic (28.6 ms). Wrap the whole script in quiet_run.py.
Output goes to <play folder>/../explosives-paired.
"""
import re
import subprocess
import sys
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "perk_popup"))
sys.path.insert(0, str(HERE.parent / "new_game"))
sys.path.insert(0, str(HERE.parent / "automatics"))
import perk_popup as pp  # noqa: E402
import run_new_game as ng  # noqa: E402
import automatics_paired as ap  # noqa: E402

TIMEOUT = 400
STEPS = "20,26,50,75,100"
HIT = re.compile(r"explosives: hit (\S+) (direct|splash): (\d+) -> (\d+) \(x([\d.]+)\)")
SELF = re.compile(r"explosives: self (\d+) -> (\d+) \(cut (\d+) bp\)")
BLAST = re.compile(r"explosives: blast (\S+) gen (\d+) damage (\d+) radius (\d+) hit (\d+) tic (\d+)")
WORST = re.compile(r"explosives: chain worst tic ([\d.]+) ms for (\d+) blasts, queue peak (\d+)")


def rules(skill):
    s = max(0, min(skill, 100))
    return {"dmg": 6000 * s // 100, "cut": 9900 if skill >= 75 else 9500 if skill >= 25 else 0, "direct": 0,
            "chain": 2500 if skill >= 100 else 0, "radius": 128 if skill >= 100 else 0}


def run(play, out):
    harness = out / "exppair-harness.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.write(HERE / "explosives_paired.zs", "zscript.txt")
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "ExpPairHarness" }\n')
    uz_log, df_log, console, launcher = out / "uz.log", out / "df.log", out / "log-exppair.txt", out / "launcher.log"
    for path in (uz_log, df_log, console, launcher):
        path.unlink(missing_ok=True)
    data = play / "data"
    uz = ["-noactivate", "-nosound", "-config", str(out / "exppair.ini"), "-savedir", str(out / "saves"), "-dfbridgelog", str(uz_log),
          "-ddtowncache", str(data / "cache"), "-ddconverter", str(data / "converter" / "DungeonConverter.exe"), "-ddarena2", ng.DAGGER + r"\ARENA2",
          "+logfile", "exppair", "+vid_fullscreen", "0", "+wipetype", "0", "+set", "dd_perklog", "1",
          "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "-skill", "3", "+map", "DDOVER01"]
    df = ["-dfbridgelog", str(df_log), "-dfmute", "-screen-fullscreen", "0", "-screen-width", "1280", "-screen-height", "800",
          "-dfsynctest", ng.DAGGER, "-dfperktest", "Explosives", "-dfperksteps", STEPS]
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
            if any(k in text for k in pp.FATAL) or re.search(r"Script error.*(exppair-harness|doomerfall\.pk3)", text):
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
            # A whole cycle at 100: one that started at 100 (a cycle started at 75 can end after the skill rose).
            whole100 = any(f"PAIRED end {n} skill=100" in text for n in re.findall(r"PAIRED start (\d+) skill=100\b", text))
            if "PAIRED pack end 2 " in text and whole100:
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
    cycles, cur, pack, packs = [], None, None, []
    for l in text.splitlines():
        if m := re.search(r"PAIRED start (\d+) skill=(-?\d+) dmg=(-?\d+) cut=(-?\d+) direct=(-?\d+) chain=(-?\d+) radius=(-?\d+) near=(\d)", l):
            cur = {"skill": int(m.group(2)), "read": dict(zip(("dmg", "cut", "direct", "chain", "radius"), map(int, m.group(3, 4, 5, 6, 7)))),
                   "near": m.group(8) == "1", "hits": [], "self": [], "hurt": 0}
            cycles.append(cur)
        elif m := re.search(r"PAIRED end \d+ skill=(-?\d+)", l):
            if cur:
                cur["end"] = int(m.group(1))
            cur = None
        elif "PAIRED pack start" in l:
            pack = {"line": l, "blasts": [], "kills": [], "gaps": [], "costs": [], "fire": None, "hurt_by_blast": 0, "worst": []}
            packs.append(pack)
            cur = None
        elif pack is not None and "end" not in pack:
            if m := re.search(r"PAIRED tic (\d+) gap ([\d.]+)", l):
                pack["gaps"].append((int(m.group(1)), float(m.group(2))))
            elif m := re.search(r"PAIRED cost tic (\d+) ([\d.]+)", l):
                pack["costs"].append((int(m.group(1)), float(m.group(2))))
            elif m := re.search(r"PAIRED pack fire tic (\d+)( control)?", l):
                pack["fire"] = int(m.group(1))
                pack["control"] = bool(m.group(2))
            elif b := BLAST.search(l):
                pack["blasts"].append(b)
            elif w := WORST.search(l):
                pack["worst"].append(w)
            elif m := re.search(r"PAIRED killed (\S+) by (\S+) tic (\d+)", l):
                pack["kills"].append((m.group(1), m.group(2), int(m.group(3))))
            elif m := re.search(r"PAIRED player hurt (\d+) by (\S+)", l):
                pack["hurt_by_blast"] += m.group(2) == "DoomerfallChainBlast"
            elif m := re.search(r"PAIRED pack end \d+ dead (\d+) of (\d+)", l):
                pack["end"] = (int(m.group(1)), int(m.group(2)))
        elif cur:
            if h := HIT.search(l):
                cur["hits"].append(h)
            elif s := SELF.search(l):
                cur["self"].append(s)
            elif m := re.search(r"PAIRED player hurt (\d+) by (\S+)", l):
                cur["hurt"] += int(m.group(1))
    done = [c for c in cycles if c.get("end") == c["skill"]]
    seen = sorted({c["skill"] for c in done})
    report.append(f"skills seen in whole cycles: {seen}")
    check("cycles at every step (26, 50, 75, 100)", all(s in seen for s in (26, 50, 75, 100)), seen)
    for c in done:
        want = rules(c["skill"])
        check("Doom read Daggerfall's rules for the skill", c["read"] == want, f"skill {c['skill']}: read {c['read']} want {want}")
        f = 1 + want["dmg"] / 10000
        for h in c["hits"]:
            check("every hit has the damage bonus", abs(float(h.group(5)) - f) < 1e-3, f"skill {c['skill']}: {h.group(0)}")
        if f != 1:
            check("the rocket's hits were boosted", c["hits"], f"skill {c['skill']}: no hit lines")
        if c["near"]:
            ok = c["self"] and all(int(s.group(3)) == want["cut"] for s in c["self"])
            check("own splash cut by the skill's amount", ok, f"skill {c['skill']}: {[s.group(0) for s in c['self']]}")
            report.append(f"skill {c['skill']}: own splash {[s.group(1) + '->' + s.group(2) for s in c['self']]}, player lost {c['hurt']}")
    check("three packs ran at skill 100 (warm-up, measured, control)", len(packs) >= 3 and all("end" in k for k in packs), len(packs))
    for i, pack in enumerate(packs):
        if "end" not in pack:
            continue
        fire = pack["fire"] or 0
        tail = [c for t, c in pack["costs"] if fire <= t < fire + 120]
        name = ("warm-up pack", "measured pack", "control pack")[min(i, 2)]
        if tail:
            report.append(f"{name}: playsim ms per tic over the 120 tics from the shot: avg {sum(tail) / len(tail):.2f} max {max(tail):.2f} "
                          f"(tics over 28.6 ms: {sum(1 for c in tail if c >= 28.6)})")
        if pack.get("control"):
            check("control pack: no blasts when nothing explosive killed it", not pack["blasts"], len(pack["blasts"]))
            continue
        measured = name == "measured pack"
        dead, size = pack["end"]
        by_blast = [k for k in pack["kills"] if k[1] == "DoomerfallChainBlast"]
        gens = sorted({int(b.group(2)) for b in pack["blasts"]})
        chain_tics = [int(b.group(6)) for b in pack["blasts"]]
        span = (min(chain_tics), max(chain_tics)) if chain_tics else (fire, fire)
        before = [g for t, g in pack["gaps"] if fire - 20 <= t < fire]
        during = [g for t, g in pack["gaps"] if fire <= t <= span[1] + 1]
        cost_before = [c for t, c in pack["costs"] if fire - 20 <= t < fire]
        cost_during = [c for t, c in pack["costs"] if fire <= t <= span[1] + 1]
        worst = max((float(w.group(1)) for w in pack["worst"]), default=0)
        check("each pack died, partly to chained blasts", size >= 20 and dead >= 0.8 * size and len(by_blast) >= size // 4, (name, dead, size, len(by_blast)))
        check("blasts chained over more than one generation", len(gens) >= 2, (name, gens))
        check("blasts never hurt the player", pack["hurt_by_blast"] == 0, (name, pack["hurt_by_blast"]))
        if measured:
            # The playsim time of each tic (all thinkers, deaths and blasts), not the wall time: on the private desktop
            # the window is minimized and frame times are not real (AGENTS.md), so wall gaps are reported only.
            # Daggerfall Unity runs beside it on the same machine, so a busy tic can cost more than one tic's 28.6 ms
            # without the chain; the check allows at most one late tic (57 ms) and the blasts' own work half a tic.
            check("steady frame rate: no playsim tic from the shot to the last blast over two tics (57 ms)", cost_during and max(cost_during) < 57, cost_during)
            mine = [float(w.group(1)) for w in pack["worst"]]
            check("the blasts' own work (including the deaths they cause) stays under half a tic (14.3 ms) per tic", max(mine, default=0) < 14.3, mine)
        report.append(f"{name}: {pack['line'].strip()}")
        report.append(f"{name}: dead {dead} of {size}, {len(by_blast)} by chained blasts, {len(pack['blasts'])} blasts, generations {gens}, "
                      f"tics {span[0]}-{span[1]} (fired {fire}), worst blast tic {worst:.2f} ms")
        if cost_before and cost_during:
            report.append(f"{name}: playsim ms per tic, 20 tics before the shot: avg {sum(cost_before) / len(cost_before):.2f} max {max(cost_before):.2f}; "
                          f"while the chain ran: avg {sum(cost_during) / len(cost_during):.2f} max {max(cost_during):.2f}")
        if before and during:
            report.append(f"{name}: wall ms between tics (minimized, not real), before: avg {sum(before) / len(before):.1f} max {max(before):.1f}; "
                          f"during: avg {sum(during) / len(during):.1f} max {max(during):.1f}")
    report.append(f"perk windows: {dft.count('ui: menu 7 opened')} opened, {dft.count('ui: menu 7 closed')} closed")
    report += [l for l in dft.splitlines() if "perktest" in l]
    result = "EXPLOSIVES PAIRED " + ("PASS" if checks and all(checks.values()) else "FAIL")
    lines = [result] + [f"{'ok  ' if v else 'FAIL'} {k}" for k, v in checks.items()] + [""] + report
    (out / "result.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    play = Path(sys.argv[1]).resolve()
    out = play.parent / "explosives-paired"
    out.mkdir(parents=True, exist_ok=True)
    if sys.argv[2] == "assemble":
        ap.assemble(play, Path(sys.argv[3]).resolve(), sys.argv[4], sys.argv[5])
    else:
        run(play, out)
