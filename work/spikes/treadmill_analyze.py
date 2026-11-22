"""Summarize treadmill frame logs. Usage: treadmill_analyze.py NAME [NAME...]"""
import csv, os, re, sys

REVIEW = r"D:\dev\DoomDaggerfall-loop\review\terrain-treadmill"
SKIP_FRAMES = 300


def pct(values, p):
    v = sorted(values)
    return v[min(len(v) - 1, int(round(p / 100 * (len(v) - 1))))] if v else float("nan")


def row(label, values):
    ms = [x / 1000 for x in values]
    print(f"| {label} | {len(ms)} | {pct(ms, 50):.2f} | {pct(ms, 95):.2f} | {max(ms) if ms else float('nan'):.2f} |")


for name in sys.argv[1:]:
    rows = list(csv.DictReader(open(os.path.join(REVIEW, name + ".csv"))))
    rows = [{k: float(v) for k, v in r.items()} for r in rows if r.get("shift") not in (None, "")][SKIP_FRAMES:]
    shift_idx = [i for i, r in enumerate(rows) if r["shift"] == 1]
    near = {j for i in shift_idx for j in range(i, min(i + 4, len(rows)))}
    print(f"\n## {name}: {len(rows)} frames, {len(shift_idx)} shifts")
    print("| Measure | n | median ms | p95 ms | worst ms |\n|---|---:|---:|---:|---:|")
    row("All frames, total", [r["frame_us"] for r in rows])
    row("Frames away from shifts, total", [r["frame_us"] for i, r in enumerate(rows) if i not in near])
    row("Shift frame, total", [rows[i]["frame_us"] for i in shift_idx])
    row("Frame after shift, total", [rows[i + 1]["frame_us"] for i in shift_idx if i + 1 < len(rows)])
    row("Shift frame, simulation", [rows[i]["sim_us"] for i in shift_idx])
    row("Shift frame, GPU buffer upload (CPU side)", [rows[i]["upload_us"] for i in shift_idx])
    print("Uploaded planes per shift frame, median:", pct([rows[i]["uploads"] for i in shift_idx], 50))
    for limit in (16.67, 33.33):
        print(f"Shift frames over {limit} ms: {sum(rows[i]['frame_us'] / 1000 > limit for i in shift_idx)} of {len(shift_idx)}; "
              f"other frames over: {sum(r['frame_us'] / 1000 > limit for i, r in enumerate(rows) if i not in near)}")
    path = os.path.join(REVIEW, name + ".csv.shifts.csv")
    if os.path.exists(path):
        s = list(csv.DictReader(open(path)))
        if s:
            print(f"Rewrite only, ms: median {pct([float(x['rewrite_us']) for x in s], 50) / 1000:.2f}, "
                  f"worst {max(float(x['rewrite_us']) for x in s) / 1000:.2f}. "
                  f"Worst plane error: {max(float(x['plane_err']) for x in s):.6f}")
    log = open(os.path.join(REVIEW, name + ".log"), errors="replace").read()
    sums = re.findall(r"TMSUM .*", log)
    print("Last check line:", sums[-1] if sums else "none")
    print("View jumps:", len(re.findall(r"TMVIEWJUMP", log)), "| Off-grid removals:", len(re.findall(r"DDTM offgrid", log)),
          "| Resolution:", (re.findall(r"Resolution: (.*)", log) or ["?"])[-1].strip(), "| Stop reached:", "DDTM stop" in log)
