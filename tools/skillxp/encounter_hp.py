"""Monster HP per encounter placement and per plan, from an encounter budget test log.

usage: python tools/skillxp/encounter_hp.py <log>
The log is UZDoom's stdout with +set dd_encounter_pooldump 1 +set dd_encounter_budgettest 1 (see
tools/encounter_planner/run_budget_test.py). Needs the ENCPOOL monster lines (health) and ENCBUD plan/place lines.
Used for work/notes/20261126-010200.md (Skill XP research).
"""
import re, sys, collections, statistics
path = sys.argv[1]
hp, pts = {}, {}
plans = {}
rows = []
for l in open(path, encoding='utf-8', errors='replace'):
    l = l.strip()
    m = re.match(r'ENCPOOL monster (\S+) .*points=([\d.]+) health=(\d+)', l)
    if m:
        hp[m.group(1).lower()] = int(m.group(3)); pts[m.group(1).lower()] = float(m.group(2)); continue
    m = re.match(r'ENCBUD plan idx=(\d+) type=(\S+) level=(\d+) n=(\d+)', l)
    if m:
        plans[m.group(1)] = (m.group(2), int(m.group(3)), int(m.group(4))); continue
    m = re.match(r'ENCBUD place idx=(\d+) p=\d+ role=(\S+) .* mooks=(\S*)', l)
    if m:
        rows.append((m.group(1), m.group(2), m.group(3)))
# per level: monsters, total HP, placements
lv = collections.defaultdict(lambda: [0, 0, 0, []])
for idx, role, mooks in rows:
    if idx not in plans: continue
    L = plans[idx][1]
    n = 0; h = 0
    for part in mooks.split('|'):
        m = re.match(r'(\S+)x(\d+)@', part)
        if not m: continue
        c = m.group(1).lower(); k = int(m.group(2))
        n += k; h += k * hp.get(c, 0)
        lv[L][3].extend([hp.get(c, 0)] * k)
    lv[L][0] += n; lv[L][1] += h; lv[L][2] += 1
per = collections.defaultdict(lambda: [0, 0])
for idx, role, mooks in rows:
    for part in mooks.split('|'):
        m = re.match(r'(\S+)x(\d+)@', part)
        if m:
            per[idx][0] += int(m.group(2)); per[idx][1] += int(m.group(2)) * hp.get(m.group(1).lower(), 0)
print('plan type level placements monsters totalHP  XPuses(HP/250)  DFuses(placements*6.5)  ratio')
for idx in sorted(per, key=lambda i: (plans[i][1], plans[i][2])):
    t, L, n = plans[idx]
    print('%4s %-14s L%-2d %4d %6d %8d %8.0f %8.0f %6.2f' % (idx, t, L, n, per[idx][0], per[idx][1], per[idx][1] / 250, n * 6.5, per[idx][1] / 250 / (n * 6.5)))
print('level placements monsters/placement hp/placement meanhp medianhp')
for L in sorted(lv):
    n, h, p, all_ = lv[L]
    if not n: continue
    print('%3d %5d %8.1f %9.0f %7.0f %7.0f' % (L, p, n / p, h / p, h / n, statistics.median(all_)))
