"""Encounter card 5: the mook placer, run in UZDoom alone (no Daggerfall) on Privateer's Hold.

usage: placer_test.py wad | run LEVEL NAME [--drla | --ch] [--spacing S] [--dungeon INDEX TYPE] [--perf TICS] | check NAME... | compare NAME_A NAME_B

--ch     Colourful Hell + DRLA + ch-compat (the project load order); --perf wakes every monster and logs think time

wad      card 4's map (encounter markers) plus the fresh converter's treasure markers
run      starts UZDoom with -ddenctest, places the map's encounters at area level LEVEL with Privateer's Hold's facts,
         logs every mook's spot, and quits
check    leaders on their markers, stuck monsters, timing, points
compare  two runs place the same mooks on the same spots
Game data and generated maps stay outside the repo (review folder).
"""
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKTREE = HERE.parents[1]
sys.path.insert(0, str(WORKTREE / "tools" / "monster_deaths"))
import monster_deaths as md  # noqa: E402

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\encounter-placer")
CARD4 = Path(r"D:\dev\DoomDaggerfall-loop\review\encounter-facts")
UZ = Path(r"D:\dev\DoomDaggerfall-build\uzdoom-encounters\Release\uzdoom.exe")
CONVERTER = Path(r"D:\dev\DoomDaggerfall-build\converter-encounters\bin\Release\net9.0\DungeonConverter.dll")
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
MODS = Path(r"D:\dev\DoomDaggerfall\GameMods")
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
CH = "ColourfulHell_1_04.pk3"
CHCOMPAT = Path(r"D:\dev\DoomDaggerfall-build\ch-compat.pk3")
WAD = "privateershold.wad"
RUNS = REVIEW / "run"
for flag in ("--exe", "--runs"):  # another build and log folder: --exe <uzdoom.exe> --runs <dir>
    if flag in sys.argv:
        at = sys.argv.index(flag)
        if flag == "--exe":
            UZ = Path(sys.argv[at + 1])
        else:
            RUNS = Path(sys.argv[at + 1])
        del sys.argv[at:at + 2]
FATAL = ("Script error", "VM execution aborted", "Unhandled exception", "Execution could not continue", "FATAL")


def make_wad():
    out = REVIEW / "wad"
    out.mkdir(parents=True, exist_ok=True)
    code = subprocess.call(["dotnet", str(CONVERTER), "Privateer's Hold", "--out", str(out)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    if code:
        sys.exit(f"converter failed ({code})")
    fresh = dict(md.read_wad(out / WAD))["TEXTMAP"]
    treasure = re.findall(rb"thing \{[^}]*arg0 = 7366;[^}]*\}\n?", fresh)
    markers = re.findall(rb"thing \{[^}]*arg0 = 7365;[^}]*\}\n?", fresh)
    base = md.read_wad(CARD4 / "wad" / ("ids_" + WAD))
    text = dict(base)["TEXTMAP"]
    old = re.findall(rb"thing \{[^}]*arg0 = 7365;[^}]*\}\n?", text)
    print(f"card 4 map markers {len(old)}, fresh markers {len(markers)}, identical {sorted(old) == sorted(markers)}, treasure markers added {len(treasure)}")
    text += b"".join(treasure)
    md.write_wad(out / ("placer_" + WAD), [(n, text if n == "TEXTMAP" else d) for n, d in base])


def run(level, name, drla, spacing, dungeon=None, ch=False, perf=None):
    runs = RUNS
    runs.mkdir(parents=True, exist_ok=True)
    log = runs / f"log-{name}.txt"   # UZDoom names a relative +logfile log-<name>.txt
    log.unlink(missing_ok=True)
    data = CARD4 / "data"
    drla = drla or ch
    files = ([str(MODS / CH)] if ch else []) + ([str(MODS / n) for n in DRLA] if drla else []) + ([str(CHCOMPAT)] if ch else []) + [str(data / n) for n in ("ddruntime.pk3", "overworld.pk3")] + \
        [str(REVIEW / "wad" / ("placer_" + WAD))] + [str(data / n) for n in ("privateershold_mesh.pk3", "privateershold_doors.pk3")] + \
        [str(WORKTREE / "mods" / "doomerfall" / "src")]
    args = [str(UZ), "-iwad", IWAD, "-file", *files, "-noactivate", "-nosound", "-noautoload", "-config", str(runs / "placer.ini"), "-skill", "3",
            "-ddenctest", str(level), "+logfile", name, "+vid_fullscreen", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1",
            "+vid_lowerinbackground", "0", "+dd_enc_log", "1"] + (["+dd_enc_spacing", str(spacing)] if spacing else []) + \
        (["-ddenctestdungeon", *dungeon] if dungeon else []) + (["-ddenctestperf", str(perf)] if perf else []) + ["+map", "MAP01"]
    timeout = 40 + (int(perf) // 35 if perf else 0)
    code = subprocess.call([sys.executable, QUIET, "--timeout", str(timeout), "--cwd", str(runs), "--", *args], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    body = log.read_text(errors="replace") if log.exists() else ""
    fatal = [k for k in FATAL if k in body and not (drla and k == "Script error")]  # the DRLA set always logs known script errors
    print(f"{name}: exit {code}, log {len(body)} bytes, fatal {fatal or 'none'}, done {'DDENCTEST done' in body}")


def markers():
    text = dict(md.read_wad(REVIEW / "wad" / ("placer_" + WAD)))["TEXTMAP"].decode()
    out = {}
    for t in re.findall(r"thing \{[^}]*arg0 = 7365;[^}]*\}", text):
        hi, lo = int(re.search(r"arg1 = (-?\d+);", t).group(1)), int(re.search(r"arg2 = (-?\d+);", t).group(1))
        placement = ((hi & 0xFFFFFFFF) << 32 | (lo & 0xFFFFFFFF)) & ((1 << 49) - 1)
        leader = (5 << 61) | (placement << 12)
        out[leader] = (float(re.search(r"x = (-?[\d.]+);", t).group(1)), float(re.search(r"y = (-?[\d.]+);", t).group(1)))
    return out


def mooks(name):
    body = (RUNS / f"log-{name}.txt").read_text(errors="replace")
    rows = re.findall(r"DDENC mook ([0-9a-f]+) (\S+) p (\d+) m (\d+) at (-?[\d.]+),(-?[\d.]+),(-?[\d.]+)", body)
    return body, [(int(i, 16), c, int(p), int(m), float(x), float(y), float(z)) for i, c, p, m, x, y, z in rows]


def contract(name):
    """Card 7: every placement has a mook, every leader is on its origin, and the points add up."""
    body = (RUNS / f"log-{name}.txt").read_text(errors="replace")
    plan = re.search(r"DDENC plan .*? pool (\d+) spent (\d+) mooks (\d+) moved-dropped (\d+) bosses (\S+) titan (-?\d+) leftover (-?\d+) titanclass (\S+)", body)
    placer = re.search(r"DDENC placer placements (\d+) mooks (\d+) unplaced (\d+) .*?cheapest-leaders (\d+) \(\+(\d+) pts\).*?dropped-points \(map full\) (\d+)", body)
    con = re.search(r"DDENC contract placed-cost (\d+) empty-placements (\d+)", body)
    if not (plan and placer and con):
        print(f"  CONTRACT {name}: FAIL, summary lines missing (plan {bool(plan)}, placer {bool(placer)}, contract {bool(con)})")
        return False
    pool, spent, nmooks, moved, bosses, titan_at, left, titan_cls = plan.groups()
    pool, spent, nmooks, moved, left = int(pool), int(spent), int(nmooks), int(moved), int(left)
    nplace, placed, unplaced, ncheap, cheap, dropped = map(int, placer.groups())
    cost, empty = map(int, con.groups())
    rows = re.findall(r"DDENC mook ([0-9a-f]+) (\S+) p (\d+) m (\d+) at (-?[\d.]+),(-?[\d.]+),(-?[\d.]+)( leader)? cost (\d+)", body)
    per = {}
    for r in rows:
        per.setdefault(int(r[2]), []).append(int(r[3]))
    no_mook = [i for i in range(nplace) if i not in per]
    no_leader = [i for i, ms in per.items() if 0 not in ms]
    row_cost = sum(int(r[8]) for r in rows)
    mk = markers()
    leaders = {int(r[0], 16): (float(r[4]), float(r[5])) for r in rows if r[3] == "0"}
    off = [hex(i) for i, (x, y) in leaders.items() if i in mk and (abs(x - mk[i][0]) > 0.05 or abs(y - mk[i][1]) > 0.05)]
    unmatched = [hex(i) for i in mk if i not in leaders]
    balance = spent + left + moved - cheap
    checks = [
        ("every placement has a mook", not no_mook and empty == 0, f"{nplace - len(no_mook)}/{nplace}, empty {empty}"),
        ("every placement has its member-0 leader", not no_leader, f"missing {no_leader[:5]}"),
        ("every leader on its origin marker", not off and not unmatched, f"{len(leaders) - len(off)}/{len(mk)} on, off {off[:3]}, markers without leader {unmatched[:3]}"),
        ("no mook left unplaced", unplaced == 0, f"unplaced {unplaced}"),
        ("plan mook count = mooks handed out", nmooks == placed == len(rows), f"plan {nmooks}, placer {placed}, logged {len(rows)}"),
        ("summed mook costs = plan spent", cost == spent == row_cost, f"placer {cost}, plan {spent}, logged {row_cost}"),
        ("pool = spent + leftover + moved-dropped - cheapest-leader additions", balance == pool, f"{spent} + {left} + {moved} - {cheap} = {balance} vs pool {pool}"),
        ("no points dropped for a full map", moved == 0 and dropped == 0, f"moved-dropped {moved}, map full {dropped}"),
    ]
    ok = all(c[1] for c in checks)
    print(f"  CONTRACT {name}: {'PASS' if ok else 'FAIL'} (leftover {left} centipoints, bosses {bosses}, titan {titan_cls} at {titan_at})")
    for what, good, detail in checks:
        print(f"    {'ok  ' if good else 'FAIL'} {what}: {detail}")
    return ok


def check(name):
    body, rows = mooks(name)
    for key in ("DDENCTEST level", "DDENC plan", "DDENC placer", "DDENC timing", "DDENC spawned", "DDENC warning", "DDWAR"):
        for line in body.splitlines():
            if line.startswith(key):
                print(" ", line[:400])
    mk = markers()
    leaders = [r for r in rows if r[3] == 0]
    logged = {int(i, 16): (float(x), float(y)) for i, x, y in re.findall(r"DDENC leader ([0-9a-f]+) \S+ at (-?[\d.]+),(-?[\d.]+),", body)}
    off = [hex(i) for i, (x, y) in logged.items() if i in mk and (abs(x - mk[i][0]) > 0.05 or abs(y - mk[i][1]) > 0.05)]
    missing = [hex(i) for i in mk if i not in logged]
    print(f"  {name}: mooks {len(rows)}, leaders planned {len(leaders)}, leaders spawned {len(logged)}, on marker {len(logged) - len(off)}, off marker {len(off)}, markers without a leader {len(missing)}")
    ids = [r[0] for r in rows]
    print(f"  unique ids {len(set(ids)) == len(ids)}; classes {len({r[1] for r in rows})}")
    for line in body.splitlines():
        if line.startswith(("DDENC contract", "DDENCTEST perf", "DDENCTEST after")):
            print(" ", line)
    contract(name)


def compare(a, b):
    _, ra = mooks(a)
    _, rb = mooks(b)
    same = ra == rb
    print(f"compare {a} vs {b}: {len(ra)} vs {len(rb)} mooks, identical spots and classes: {same}")
    if not same:
        for x, y in zip(ra, rb):
            if x != y:
                print("  first difference:", x, y)
                break


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "wad":
        make_wad()
    elif cmd == "run":
        sp = sys.argv[sys.argv.index("--spacing") + 1] if "--spacing" in sys.argv else None
        dg = sys.argv[sys.argv.index("--dungeon") + 1:sys.argv.index("--dungeon") + 3] if "--dungeon" in sys.argv else None
        pf = sys.argv[sys.argv.index("--perf") + 1] if "--perf" in sys.argv else None
        run(int(sys.argv[2]), sys.argv[3], "--drla" in sys.argv, sp, dg, "--ch" in sys.argv, pf)
        check(sys.argv[3])
    elif cmd == "check":
        for n in sys.argv[2:]:
            check(n)
    elif cmd == "compare":
        compare(sys.argv[2], sys.argv[3])
    else:
        sys.exit(__doc__)
