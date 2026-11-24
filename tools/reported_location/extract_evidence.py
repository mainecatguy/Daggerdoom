"""Writes the evidence lines of a kept run (run_location.py <row> <label>) to a text file, with the build that made them.

usage: extract_evidence.py <label> <output file>
"""
import hashlib
import sys
from pathlib import Path

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\reported-location")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16] if path.exists() else "missing"


def main():
    label, out = sys.argv[1], Path(sys.argv[2])
    kept = REVIEW / f"evidence-{label}"
    dfu = REVIEW / "dfu" / "DaggerfallUnity_Data" / "Managed" / "Assembly-CSharp.dll"
    lines = [f"# Evidence from review/reported-location/evidence-{label}",
             f"# Daggerfall Assembly-CSharp.dll sha256 {digest(dfu)} (staged build that produced these logs)",
             f"# uzdoom.exe sha256 {digest(REVIEW / 'uzdoom' / 'uzdoom.exe')}", ""]
    lines += ["## Doom route steps (log-route.txt)"]
    lines += [l for l in (kept / "log-route.txt").read_text(errors="replace").splitlines() if l.startswith(("LOCSTEP", "DDTRANSITION", "DDSTITCH arrive"))]
    lines += ["", "## Daggerfall (df.log)"]
    lines += [l for l in (kept / "df.log").read_text(errors="replace").splitlines() if "locprobe" in l or "travel:" in l or "new game:" in l or "transition" in l]
    out.write_text("\n".join(lines) + "\n")
    print("wrote", out, len(lines), "lines")


if __name__ == "__main__":
    main()
