"""Runs the encounter budget test hook (+set dd_encounter_budgettest 1) and checks the plans (encounter design sections 6
and 7, card 3).

usage: python tools/encounter_planner/run_budget_test.py <uzdoom.exe> <workdir> [--wads DIR] [--mods DIR] [--chcompat PK3]

Runs, each minimized with a private config, stopped at "ENCBUD done" or on a fatal or doomerfall script error:
  stock    DOOM2.WAD with doomerfall.pk3 only
  chdrla   Colourful Hell + DRLA + ch-compat + doomerfall.pk3 (the project load order)
  chdrla2  the same with a different +rngseed and config: must print identical ENCBUD lines
Logs go to workdir/<run>.log and workdir/<run>.budget.txt (the ENCBUD lines).
"""
import argparse
import os
import re
import subprocess
import sys
import threading
import time
from collections import Counter, defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DRLA = ['DoomRL_Arsenal_1.1.5.pk3', 'DoomRL_Monsters_Beta_7.3.pk3', 'drlax_1.2b.pk3']
CH = 'ColourfulHell_1_04.pk3'
BAD = re.compile(r'Script error, "doomerfall\.pk3|doomerfall\.pk3:zscript/\S+, line \d+|\bFatal error|VM execution aborted|Execution could not continue', re.I)
AVG = {1: 3.5, 10: 20, 20: 42, 30: 90}


def run(exe, work, iwad, files, name, extra, timeout=60):
    cmd = [exe, '-iwad', iwad, '-file', *files, '-config', os.path.join(work, name + '.ini'), '-nosound', '-stdout',
           '-noactivate', '+vid_fullscreen', '0', '+i_pauseinbackground', '0', '+vid_activeinbackground', '1',
           '+vid_lowerinbackground', '0', '+set', 'dd_encounter_pooldump', '1', '+set', 'dd_encounter_budgettest', '1',
           '-skill', '3', '+map', 'MAP01', *extra]
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 7  # SW_SHOWMINNOACTIVE
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, startupinfo=startup, cwd=work,
                            text=True, encoding='utf-8', errors='replace')
    lines = []
    th = threading.Thread(target=lambda: [lines.append(l.rstrip()) for l in proc.stdout], daemon=True)
    th.start()
    start = time.monotonic()
    while time.monotonic() - start < timeout and proc.poll() is None:
        if any('ENCBUD done' in l or BAD.search(l) for l in lines):
            time.sleep(0.5)
            break
        time.sleep(0.2)
    if proc.poll() is None:
        subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'], capture_output=True)
    th.join(2)
    took = time.monotonic() - start
    lines.append(f'(run took {took:.1f} s, exit {proc.poll()})')
    with open(os.path.join(work, name + '.log'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    out = [l for l in lines if l.startswith('ENCBUD') or l.startswith('ENCPOOL monster')]
    with open(os.path.join(work, name + '.budget.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))
    return lines, out, took


def kv(text):
    return dict(p.split('=', 1) for p in text.split(' ') if '=' in p)


def parse(out):
    pool, plans, places, squads, warns, other = {}, {}, defaultdict(list), defaultdict(list), [], {}
    for l in out:
        if l.startswith('ENCPOOL monster '):
            name, rest = l.split(' ', 3)[2:]
            pool[name] = kv(rest)
        elif l.startswith('ENCBUD plan '):
            d = kv(l[12:])
            plans[int(d['idx'])] = d
        elif l.startswith('ENCBUD place '):
            d = kv(l[13:])
            d['list'] = [(m.rsplit('x', 1)[0], int(m.rsplit('x', 1)[1].split('@')[0]), int(m.rsplit('@', 1)[1]))
                         for m in d['mooks'].split('|')] if d['mooks'] else []
            places[int(d['idx'])].append(d)
        elif l.startswith('ENCBUD squad '):
            d = kv(l[13:])
            squads[int(d['idx'])].append(d)
        elif l.startswith('ENCBUD warn '):
            warns.append(l)
        elif l.startswith('ENCBUD promote ') or l.startswith('ENCBUD movefull '):
            other[l.split()[1]] = kv(l)
    return pool, plans, places, squads, warns, other


def mook_id(hash_hi, hash_lo, member):
    h = ((hash_hi << 32) | hash_lo) & ((1 << 49) - 1)
    return (5 << 61) | (h << 12) | member


def check(name, lines, out, checks, stock):
    pool, plans, places, squads, warns, other = parse(out)
    I = lambda d, k: int(d[k])
    checks.append((f'{name}: ran with no fatal or doomerfall script errors', any('ENCBUD done' in l for l in lines) and not any(BAD.search(l) for l in lines)))
    checks.append((f'{name}: {len(plans)} plans printed', len(plans) >= 500))
    cost = {n: max(1, int(float(m['points']) * 100 + 0.5)) for n, m in pool.items() if 'points' in m}

    bad_total = [i for i, p in plans.items() if not (0 <= I(p, 'leftover') < max(1, I(p, 'cheapest')) * 2) or I(p, 'pool') != I(p, 'avg') * I(p, 'n')]
    checks.append((f'{name}: every pool = average x placements, and spent matches it to within the cheapest monster '
                   f'(bad: {bad_total[:5]})', not bad_total))
    split_ok = [i for i, p in plans.items() if I(p, 'reserve') + I(p, 'boss') + I(p, 'titan') + I(p, 'split') != I(p, 'pool') and I(p, 'split') > 0]
    checks.append((f'{name}: reserve + bosses + titan + split = pool (bad: {split_ok[:5]})', not split_ok))
    det = [i for i, p in plans.items() if p['digest'] != p['digest2']]
    checks.append((f'{name}: planning each request twice gives the same mooks and IDs (mismatch: {det[:5]})', not det))
    lone_missing = [i for i, p in plans.items() if I(p, 'mooks') < I(p, 'n')]
    checks.append((f'{name}: every plan has at least one mook per placement (by total)', not lone_missing))
    for p_id in (p for p in plans if plans[p]['level'] in ('1', '10', '20', '30')):
        p = plans[p_id]
        lvl = int(p['level'])
        if lvl in AVG and p['detail'] == '1':
            checks.append((f'{name}: idx {p_id} level {lvl} average is {I(p, "avg") / 100} (design {AVG[lvl]})', abs(I(p, 'avg') / 100 - AVG[lvl]) < 0.01))

    # Detailed plans: per placement.
    for idx, pl in places.items():
        p = plans[idx]
        empty = [q['p'] for q in pl if int(q['n']) < 1]
        members = [q['p'] for q in pl if q['members'] != '1']
        leader = [q['p'] for q in pl if q['leaderfits'] != '1']
        spent = sum(int(q['spent']) for q in pl)
        recount = sum(c * k for q in pl for _, k, c in q['list'])
        badcost = sorted({n for q in pl for n, _, c in q['list'] if n in cost and abs(cost[n] - c) > 1})
        ids_ok = all(int(q['id0'], 16) == mook_id(int(q['hash'][:8], 16), int(q['hash'][8:], 16), 0) and
                     int(q['idlast'], 16) == mook_id(int(q['hash'][:8], 16), int(q['hash'][8:], 16), int(q['n']) - 1) for q in pl)
        ids = [q['hash'] for q in pl]
        checks.append((f'{name}: idx {idx} ({p["type"]} L{p["level"]}, {len(pl)} placements): every placement has a monster '
                       f'{not empty}, members run 0..n-1 {not members}, the first monster fits at the origin {not leader}, '
                       f'placement spends sum to {spent} = plan {p["spent"]} = class costs {recount}, costs match the pool dump {not badcost}, '
                       f'mook IDs match the 3|49|12 layout {ids_ok}',
                       not badcost and not empty and not members and not leader and spent == I(p, 'spent') == recount and ids_ok and len(set(ids)) == len(ids)))
        boss_rows = [q for q in pl if q['role'] in ('boss', 'miniboss')]
        bosses = p['bosses'].split(',') if p['bosses'] != '-' else []
        ok = sorted(q['p'] for q in boss_rows) == sorted(bosses) or (p['titanat'] in bosses)
        if p['walk'] == '1' and bosses:
            deepest = pl[int(bosses[0])]
            far = max(int(q['walk']) for q in pl)
            ok = ok and int(deepest['walk']) >= 0.75 * far
        checks.append((f'{name}: idx {idx}: bosses {bosses} ({p["bossstyle"]}); the deepest boss is among the farthest on foot', ok))

    # Titans.
    rates = defaultdict(lambda: [0, 0])
    titan_bad = []
    for i, p in plans.items():
        lvl, has = int(p['level']), p['titanclass'] != 'none'
        if p['type'] == 'RuinedCastle':
            rates[lvl][0] += has
            rates[lvl][1] += 1
        if has and lvl < 20:
            titan_bad.append((i, 'below 20'))
        if has and I(p, 'titan') > 0.4 * I(p, 'pool') + 1:
            titan_bad.append((i, 'over 40%'))
        if has and p['type'] != 'DragonsDen' and p['titanat'] in p['bosses'].split(','):
            titan_bad.append((i, 'at a boss placement'))
    checks.append((f'{name}: no titan below level 20, none over 40% of the pool, none at a boss placement outside Dragon\'s Dens ({titan_bad[:5]})', not titan_bad))
    if not stock:
        r19, r25, r30 = (rates[l][0] / max(1, rates[l][1]) for l in (19, 25, 30))
        checks.append((f'{name}: titan rate {r19:.2f} at level 19, {r25:.2f} at 25, {r30:.2f} at 30 (design 0, about 0.2, about 0.3)',
                       r19 == 0 and 0.1 <= r25 <= 0.3 and 0.2 <= r30 <= 0.4))
        dens = [p for p in plans.values() if p['type'] == 'DragonsDen' and int(p['level']) >= 25]
        den_ok = [p for p in dens if p['titanclass'] != 'none' and p['titanat'] == p['bosses'].split(',')[0]]
        checks.append((f'{name}: Dragon\'s Dens at level 25+ with a titan as the deepest boss: {len(den_ok)}/{len(dens)}', len(den_ok) == len(dens) and dens))
    else:
        checks.append((f'{name}: stock Doom has no titans', all(p['titanclass'] == 'none' for p in plans.values())))

    # Squads: Pitman-Yor reuse at the 100-placement plan.
    if 105 in squads:
        ordinary = [s for s in squads[105] if s['note'] == '-']
        uses = sorted((int(s['uses']) for s in ordinary), reverse=True)
        checks.append((f'{name}: idx 105 (100 placements, novelty {plans[105]["novelty"]}): {len(ordinary)} ordinary squads, uses {uses[:12]}...',
                       2 <= len(ordinary) <= 70 and uses and uses[0] >= 3))
    # Hooks.
    pr = other.get('promote')
    if pr:
        ok = int(pr['after']) <= 5 and int(pr['sum']) == int(pr['totalafter']) and \
             int(pr['totalafter']) + int(pr['leftover']) == int(pr['pool']) and int(pr['moveto']) >= 0
        checks.append((f'{name}: Promote cut placement {pr["p"]} from {pr["before"]} to {pr["after"]} monsters, returned {pr["returned"]}, '
                       f'Move gave it to {pr["moveto"]}; spent + leftover = pool ({pr["totalafter"]} + {pr["leftover"]} = {pr["pool"]})', ok))
    mf = other.get('movefull')
    checks.append((f'{name}: Move with every placement full drops and reports the points', bool(mf) and mf['to'] == '-1' and mf['dropped'] == '500'))
    return out, plans, places


def summary(plans, places):
    """A readable digest of the showcase plans for the notes."""
    rows = []
    for idx in sorted(places):
        p = plans[idx]
        pl = places[idx]
        sizes = sorted(int(q['n']) for q in pl)
        roles = Counter(q['role'] for q in pl)
        rows.append(f'idx {idx} {p["type"]} L{p["level"]} n={p["n"]} pool={int(p["pool"]) / 100:g} reserve={int(p["reserve"]) / 100:g} '
                    f'boss={int(p["boss"]) / 100:g} titan={int(p["titan"]) / 100:g} ({p["titanclass"]}, {p["titanwhy"]}) split={int(p["split"]) / 100:g} '
                    f'spent={int(p["spent"]) / 100:g} leftover={int(p["leftover"]) / 100:g} normalpack={int(p["normalpack"]) / 100:g} '
                    f'bossstyle={p["bossstyle"]} bosses={p["bosses"]} squads={p["squads"]} mooks={p["mooks"]} '
                    f'pack sizes min/median/max={sizes[0]}/{sizes[len(sizes) // 2]}/{sizes[-1]} roles={dict(roles)}')
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('exe')
    ap.add_argument('work')
    ap.add_argument('--wads', default=r'D:\dev\DoomDaggerfall\GameResources\wads')
    ap.add_argument('--mods', default=r'D:\dev\DoomDaggerfall\GameMods')
    ap.add_argument('--chcompat', default=r'D:\dev\DoomDaggerfall-build\ch-compat.pk3')
    ap.add_argument('--only', default='')
    a = ap.parse_args()
    os.makedirs(a.work, exist_ok=True)
    subprocess.run([sys.executable, os.path.join(REPO, 'scripts', 'doomerfall', 'build_pk3.py'), os.path.join(a.work, 'doomerfall.pk3')], check=True)
    mod = os.path.join(a.work, 'doomerfall.pk3')
    drla = [os.path.join(a.mods, n) for n in DRLA]
    doom2 = os.path.join(a.wads, 'DOOM2.WAD')
    chfiles = [os.path.join(a.mods, CH)] + drla + [a.chcompat, mod]
    want = set(a.only.split(',')) if a.only else None
    checks, outs = [], {}
    for name, files, extra, stock in (('stock', [mod], [], True), ('chdrla', chfiles, ['+rngseed', '1'], False),
                                      ('chdrla2', chfiles, ['+rngseed', '4242'], False)):
        if want and name not in want:
            continue
        lines, out, took = run(a.exe, a.work, doom2, files, name, extra)
        outs[name], plans, places = check(name, lines, out, checks, stock)
        print(f'{name}: {took:.1f} s')
        with open(os.path.join(a.work, name + '.summary.txt'), 'w', encoding='utf-8') as f:
            f.write('\n'.join(summary(plans, places)))
    if 'chdrla' in outs and 'chdrla2' in outs:
        p1 = [l for l in outs['chdrla'] if l.startswith('ENCBUD') and not l.startswith('ENCBUD time')]
        p2 = [l for l in outs['chdrla2'] if l.startswith('ENCBUD') and not l.startswith('ENCBUD time')]
        checks.append((f'chdrla vs chdrla2 (different rngseed and config): {len(p1)} ENCBUD lines identical', p1 == p2 and len(p1) > 700))
    failed = 0
    for n, ok in checks:
        failed += not ok
        print(('PASS ' if ok else 'FAIL ') + n)
    print(f'{len(checks) - failed}/{len(checks)} passed')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
