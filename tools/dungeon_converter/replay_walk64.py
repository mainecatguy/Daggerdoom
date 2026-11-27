"""The 64 runs of paired_walk.py (4 spots x 16 headings), replayed Doom-only with walk_replay.py and scored by
paired_walk.py --analyse, for when a paired New Game is not available.

usage: replay_walk64.py <play folder> <wad> --out DIR
Writes DIR/log-walk.txt in paired_walk's format, DIR/replay.txt (raw replay with blocking lines) and DIR/summary.txt.
Validate it first: on a WAD with a real paired run, its per-heading lines must match that run's summary.txt.
"""
import subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
SPOTS = "700,860;52,620;931,1490;690,-300"


def main():
    play, wad = sys.argv[1], sys.argv[2]
    out = Path(sys.argv[sys.argv.index("--out") + 1])
    out.mkdir(parents=True, exist_ok=True)
    spots = [s.split(",") for s in SPOTS.split(";")]
    spec = ";".join(f"{x},{y},{h}" for x, y in spots for h in range(16))
    # paired_walk.py's player arrives at Privateer's Hold's entrance marker before the first spot.
    raw = subprocess.run([sys.executable, str(HERE / "walk_replay.py"), play, wad, spec, "--from", "510,1672,0"],
                         capture_output=True, text=True).stdout
    (out / "replay.txt").write_text(raw)
    log, run = [], -1
    for line in raw.splitlines():
        p = line.split()
        if line.startswith("WRRUN"):
            run += 1
            log.append(f"PWWALK {run // 16} {run % 16} {p[5]} {p[6]} {p[7]}")
        elif line.startswith("WRT"):
            log.append(f"PWT {p[2]} {p[3]} {p[4]} {p[5]}")
    if run != 63:
        sys.exit(f"replay finished {run + 1} of 64 runs")
    (out / "log-walk.txt").write_text("\n".join(log) + "\n")
    for name in ("df.log", "uz.log"):
        (out / name).touch()
    subprocess.run([sys.executable, str(HERE / "paired_walk.py"), play, "--out", str(out), "--analyse"], check=True,
                   stdout=subprocess.DEVNULL)


if __name__ == "__main__":
    main()
