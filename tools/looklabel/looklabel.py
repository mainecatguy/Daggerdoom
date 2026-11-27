"""Look label names (test only): every visible Doom pickup is named by the Doomerfall mod's rule (DoomerfallItemName.Of),
which the look label and Daggerfall's inventory use, for stock DOOM.WAD and with the DRLA set. No bridge.

usage: looklabel.py names|e1m1 <uzdoom.exe> [--out <folder>]
  e1m1: DOOM.WAD E1M1 with no Doomerfall files, alone and with the DRLA set; exit 0 and no fatal error.
  Runs E1M1 twice (stock, DRLA) with this worktree's doomerfall.pk3 (and doomerfall-drla.pk3 with DRLA) and
  tools/looklabel/harness.zs, then checks: no name is a pickup message ("Picked up ...", "You got ..."), no name is
  empty or holds a format code, and known items get their plain names (Stimpack, Medikit, ...).
Wrap nothing: this script starts UZDoom through quiet_run.py itself.
"""
import re
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Execution could not continue", "Unable to open map")
# Names the engine shows (after its own CleanTag) for some classes, by set.
EXPECT = {
    "stock": {"Stimpack": "Stimpack", "Medikit": "Medikit", "Clip": None, "Shell": None, "BlueCard": None, "Soulsphere": None},
    "drla": {"RLStimpack": "Stimpack", "RLMedikit": "Medikit"},
}
MESSAGE = re.compile(r"^(picked up|you got|you picked|you found|found|got)\b", re.I)
# A sentence rather than a name: a pronoun or a verb word anywhere ("This Laser Can Fire Through Anything",
# "Cloaking Device Activated", "Your Weapon Has Been Downgraded").
SENTENCE = re.compile(r"\b(you|your|this|these|there|it|its|is|are|was|has|have|had|been|will|now|activated)\b", re.I)  # Not "can": "Fuel Can".


def clean(tag):
    """dd_items.cpp CleanTag: no color codes, no DRLA ' [Pickup]'."""
    tag = re.sub(r"\x1c(\[[^\]]*\]|.)", "", tag)
    return tag[:-9] if tag.endswith(" [Pickup]") and len(tag) > 9 else tag


def run(uzdoom, out, label, files):
    log = out / f"log-names-{label}.txt"
    log.unlink(missing_ok=True)
    command = [sys.executable, QUIET, "--timeout", "40", "--cwd", str(out), "--", str(uzdoom), "-iwad", str(GAME / "wads" / "DOOM.WAD"),
               "-config", str(out / f"{label}.ini"), "-nosound", "-noautoload", "-skill", "3", "-file", *map(str, files),
               "+logfile", f"names-{label}", "+map", "E1M1", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1",
               "+vid_lowerinbackground", "0", "+vid_fullscreen", "0", "+wait 60;quit"]
    code = subprocess.call(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return code, log.read_text(errors="replace") if log.exists() else ""


def names(uzdoom, out):
    out.mkdir(parents=True, exist_ok=True)
    mod, drla_mod, harness = out / "doomerfall.pk3", out / "doomerfall-drla.pk3", out / "looklabel-harness.pk3"
    build = REPO / "scripts" / "doomerfall" / "build_pk3.py"
    subprocess.check_call([sys.executable, str(build), str(mod)], stdout=subprocess.DEVNULL)
    subprocess.check_call([sys.executable, str(build), "--drla", str(drla_mod)], stdout=subprocess.DEVNULL)
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", (HERE / "harness.zs").read_text())
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "LLHarness" }\n')
    ok = True
    for label, base in (("stock", []), ("drla", [MODS / n for n in DRLA])):
        files = base + [mod] + ([drla_mod] if base else []) + [harness]
        code, body = run(uzdoom, out, label, files)
        fatal = [l for l in body.splitlines() if any(k in l for k in FATAL)]
        rows = re.findall(r"^LLNAME class=(\S+) name=(.*?) old=(.*)$", body, re.M)
        done = re.search(r"^LLDONE (\d+)", body, re.M)
        table = {c: (clean(n), clean(o)) for c, n, o in rows}
        bad = [(c, n) for c, (n, _) in table.items() if not n or MESSAGE.match(n) or SENTENCE.search(n) or "%" in n]
        changed = [(c, o, n) for c, (n, o) in table.items() if n != o]
        print(f"{label}: exit {code}, {len(table)} pickups named, fatal {len(fatal)}, done {bool(done)}")
        for l in fatal[:5]:
            print("   ", l[:200])
        print(f"  names that changed ({len(changed)}):")
        for c, o, n in sorted(changed):
            print(f"    {c:40} {o!r} -> {n!r}")
        for c, n in bad:
            print(f"  BAD {c}: {n!r}")
        for c, want in EXPECT[label].items():
            got = table.get(c, (None,))[0]
            good = got is not None and (want is None or got == want)
            print(f"  {c}: {got!r}{'' if good else '  (expected ' + repr(want) + ')'}")
            ok &= good
        (out / f"names-{label}.tsv").write_text("".join(f"{c}\t{n}\t{o}\n" for c, (n, o) in sorted(table.items())), encoding="utf-8")
        ok &= not fatal and bool(done) and not bad and len(table) > 0
    print("LOOK LABEL NAMES", "PASS" if ok else "FAIL")


def e1m1(uzdoom, out):
    """DOOM.WAD E1M1 alone and with play_drlax.bat's DRLA set, no Doomerfall files: the engine change stays inactive."""
    ok = True
    for label, files in (("e1m1-stock", []), ("e1m1-drla", [MODS / n for n in DRLA])):
        log = out / f"log-{label}.txt"
        log.unlink(missing_ok=True)
        command = [sys.executable, QUIET, "--timeout", "30", "--cwd", str(out), "--", str(uzdoom), "-iwad", str(GAME / "wads" / "DOOM.WAD"),
                   "-config", str(out / f"{label}.ini"), "-nosound", "-skill", "3", *(["-file", *map(str, files)] if files else []),
                   "+logfile", label, "+map", "E1M1", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1",
                   "+vid_lowerinbackground", "0", "+vid_fullscreen", "0", "+wait 175;quit"]
        code = subprocess.call(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        body = log.read_text(errors="replace") if log.exists() else ""
        fatal = [l for l in body.splitlines() if any(k in l for k in FATAL)]
        entered = "E1M1" in body
        print(f"{label}: exit {code}, entered E1M1 {entered}, fatal {len(fatal)}, script errors {body.count('Script error')}")
        ok &= code == 0 and entered and not fatal
    print("E1M1", "PASS" if ok else "FAIL")


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("names", "e1m1"):
        sys.exit(__doc__)
    if sys.argv[1] == "e1m1":
        e1m1(Path(sys.argv[2]), Path(r"D:\dev\DoomDaggerfall-loop\review\looklabel-tests"))
        sys.exit()
    folder = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else Path(r"D:\dev\DoomDaggerfall-loop\review\looklabel-tests")
    folder.mkdir(parents=True, exist_ok=True)
    report = open(folder / "summary.txt", "w", encoding="utf-8")  # Everything printed also goes here.
    console = sys.stdout

    class Tee:
        def write(self, s):
            console.write(s)
            report.write(s)

        def flush(self):
            console.flush()
            report.flush()
    sys.stdout = Tee()
    names(Path(sys.argv[2]), folder)
