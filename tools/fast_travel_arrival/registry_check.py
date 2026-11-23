"""Fingerprints the owner's real Daggerfall Unity registry key, read only.

usage: registry_check.py save|compare
"""
import hashlib
import sys
import winreg
from pathlib import Path

KEY = r"Software\Daggerfall Workshop\Daggerfall Unity"
STORE = Path(r"D:\dev\DoomDaggerfall-loop\review\fast-travel-arrival\run\registry-before.txt")


def fingerprint():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY) as handle:
            count = winreg.QueryInfoKey(handle)[1]
            values = sorted(repr(winreg.EnumValue(handle, i)) for i in range(count))
    except FileNotFoundError:
        return "key absent"
    return f"{count} values {hashlib.sha256(chr(10).join(values).encode()).hexdigest()}"


now = fingerprint()
if sys.argv[1] == "save":
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(now)
    print("saved:", now)
else:
    before = STORE.read_text()
    print("unchanged" if before == now else "CHANGED", "| before:", before, "| after:", now)
