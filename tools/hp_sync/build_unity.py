"""Builds Daggerfall Unity (windowed, as AGENTS.md requires) and prints the result line."""
import subprocess
from pathlib import Path

ROOT = Path(r"D:\dev\DoomDaggerfall-loop\worktree")
LOG = ROOT / "daggerfall-unity-master" / "Logs" / "cli-build.log"
LOG.unlink(missing_ok=True)
subprocess.call(["Unity.exe", "-projectPath", str(ROOT / "daggerfall-unity-master"), "-buildTarget", "Win64",
                 "-executeMethod", "CliBuild.BuildWindows64", "-logFile", str(LOG)])
text = LOG.read_text(errors="replace") if LOG.exists() else ""
print([line for line in text.splitlines() if "CliBuild result" in line or "error CS" in line][:20])
