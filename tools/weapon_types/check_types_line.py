"""Checks the first line of a Doom gun's Daggerfall Info text (DoomerfallDoomItem.TypesLine in
daggerfall-unity-master/Assets/Scripts/Doomerfall/DoomerfallDoomItems.cs): "Type:" for one type, "Types:" for two,
"Types: none" for none.

usage: python tools/weapon_types/check_types_line.py

Copies the method out of the C# file, compiles it with PowerShell's Add-Type (no Unity needed) and runs it on samples.
"""
import os
import re
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(REPO, 'daggerfall-unity-master', 'Assets', 'Scripts', 'Doomerfall', 'DoomerfallDoomItems.cs')

# (Doom name, types Doom sends, expected line), from the owner's rule (2026-11-26: "it should be Type: if it is
# singular").
CASES = [
    ('Plasma Rifle', 'Energy', 'Plasma Rifle. Type: Energy'),
    ('Laser Shotgun', 'Energy, Shotgun', 'Laser Shotgun. Types: Energy, Shotgun'),
    ('Plasma Pistol', 'Pistol, Energy', 'Plasma Pistol. Types: Pistol, Energy'),
    ('Autocannon', 'Automatic', 'Autocannon. Type: Automatic'),
    ('Nanomachic Armament Generator', '', 'Nanomachic Armament Generator. Types: none'),
]


def main():
    text = open(SRC, encoding='utf-8').read()
    m = re.search(r'internal static string TypesLine\(string doomName, string types\)\s*\{.*?\n        \}', text, re.S)
    if not m:
        print('FAIL TypesLine not found in', SRC)
        return 1
    method = m.group(0).replace('internal static', 'public static')
    calls = '\n'.join('[TypesLineCheck]::TypesLine("%s", "%s")' % (n, t) for n, t, _ in CASES)
    ps = "Add-Type -TypeDefinition @'\npublic static class TypesLineCheck {\n%s\n}\n'@\n%s\n" % (method, calls)
    with tempfile.TemporaryDirectory() as tmp:  # -Command - reads line by line and breaks the here-string.
        script = os.path.join(tmp, 'typesline.ps1')
        with open(script, 'w', encoding='utf-8') as f:
            f.write(ps)
        out = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File',
                              script], capture_output=True, text=True)
    got = [l.strip() for l in out.stdout.splitlines() if l.strip()]
    failed = 0
    for i, (_, _, want) in enumerate(CASES):
        g = got[i] if i < len(got) else '(missing)'
        ok = g == want
        failed += not ok
        print(('PASS ' if ok else 'FAIL ') + want + ('' if ok else '  (got %s)' % g))
    if out.returncode or out.stderr.strip():
        print(out.stderr)
        failed += 1
    print('RESULT', 'PASS' if not failed else 'FAIL (%d)' % failed)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
