"""Which monsters of a New Game stand in Privateer's Hold's hall with stairs, and are they all battle rifle Former Humans?

usage: check_stair_hall.py <hall-region log (run_hall_region.py's log-hall-region-log.txt)> <New Game log with +dd_enc_log 1>
A monster is in the hall when one of the hall's walk-grid nodes (HN lines) is within 8 units of it across and 24 in
height. Prints those monsters and PASS when every one is a battle rifle Former Human (or the stock zombieman without
DRLA) and none is a chaingunner, else FAIL."""
import re
import sys

OK = {"RLFormerHumanBattleRifle", "RLFormerHumanBattleRifle2", "RLFormerHumanBattleRifle3", "Zombieman"}
nodes = {}
for l in open(sys.argv[1], errors="replace"):
    m = re.match(r"HN (-?\d+) (-?\d+) (-?\d+)", l)
    if m:
        x, y, z = map(int, m.groups())
        nodes.setdefault((x // 8, y // 8), []).append((x, y, z))
if not nodes:
    sys.exit("no HN lines in " + sys.argv[1])


def in_hall(x, y, z):
    for cx in range(int(x // 8) - 2, int(x // 8) + 3):
        for cy in range(int(y // 8) - 2, int(y // 8) + 3):
            for nx, ny, nz in nodes.get((cx, cy), []):
                if abs(nx - x) <= 8 and abs(ny - y) <= 8 and abs(nz - z) <= 24:
                    return True
    return False


found, total = [], 0
for i, l in enumerate(open(sys.argv[2], errors="replace"), 1):
    m = re.match(r"DDENC mook (\S+) (\S+) p (\d+) m (\d+) at (-?[\d.]+),(-?[\d.]+),(-?[\d.]+)", l)
    if not m:
        continue
    total += 1
    x, y, z = float(m.group(5)), float(m.group(6)), float(m.group(7))
    if in_hall(x, y, z):
        found.append((i, m.group(2), int(m.group(3)), l.strip()))
print(f"{sum(len(v) for v in nodes.values())} hall nodes, {total} monsters in the log, {len(found)} in the hall:")
for i, cls, p, l in found:
    print(f"  line {i}: {l}")
bad = [f for f in found if f[1] not in OK or "chaingun" in f[1].lower()]
print("PASS" if found and not bad else f"FAIL ({'no monster in the hall' if not found else bad})")
