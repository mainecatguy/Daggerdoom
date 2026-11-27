"""Runs the encounter planner test hook (+set dd_encounter_plantest 1) in each mod setup and checks genes and armies.

usage: python tools/encounter_planner/run_test.py <uzdoom.exe> <workdir> [--wads DIR] [--mods DIR] [--chcompat PK3]

Runs, each minimized with a private config, stopped at "ENCPLAN done" or on a fatal or doomerfall script error:
  stock      DOOM2.WAD MAP01 with doomerfall.pk3 only (the 17 stock monsters)
  drla       + DRLA Arsenal, Monsters and DRLAX
  chdrla     Colourful Hell + DRLA + ch-compat + doomerfall.pk3 (the project load order)
  drlaskill1 drla at skill 1: must print the same ENCPLAN lines as drla (skill 3)
  chdrla2    the same again with a different +rngseed and a different config: must print identical ENCPLAN lines
Logs go to workdir/<run>.log and workdir/<run>.plan.txt (the ENCPOOL and ENCPLAN lines).
"""
import argparse
import fnmatch
import os
import random
import re
import subprocess
import sys
import threading
import time
from collections import defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DRLA = ['DoomRL_Arsenal_1.1.5.pk3', 'DoomRL_Monsters_Beta_7.3.pk3', 'drlax_1.2b.pk3']
CH = 'ColourfulHell_1_04.pk3'
BAD = re.compile(r'Script error, "doomerfall\.pk3|doomerfall\.pk3:zscript/\S+, line \d+|\bFatal error|VM execution aborted|Execution could not continue', re.I)
FAMILIES = {'Standard', 'Nightmare', 'Technophobia', 'Armageddon'}
TITANS = {'EX', 'BlackWhite'}
HUMANOID = {'ZombieMan', 'ShotgunGuy', 'ChaingunGuy'}
PLAIN = {'Zombieman', 'ShotgunGuy', 'ChaingunGuy', 'RLFormerHumanPistol', 'RLFormerSergeantShotgun', 'RLFormerCommandoChaingun'}
STOCK17 = {'ZombieMan', 'ShotgunGuy', 'ChaingunGuy', 'DoomImp', 'Demon', 'Spectre', 'LostSoul', 'Cacodemon', 'HellKnight',
           'BaronOfHell', 'Arachnotron', 'PainElemental', 'Revenant', 'Fatso', 'Archvile', 'Cyberdemon', 'SpiderMastermind'}
RING = ('ZombieMan,ShotgunGuy,ChaingunGuy,DoomImp,Demon,Spectre,LostSoul,Cacodemon,PainElemental,HellKnight,BaronOfHell,'
        'Revenant,Archvile,Fatso,Arachnotron,SpiderMastermind,Cyberdemon').split(',')  # kind_ring in doomerfall_encounters.txt


def run(exe, work, iwad, files, name, extra, timeout=40, skill='3'):
    cmd = [exe, '-iwad', iwad, '-file', *files, '-config', os.path.join(work, name + '.ini'), '-nosound', '-stdout',
           '-noactivate', '+vid_fullscreen', '0', '+i_pauseinbackground', '0', '+vid_activeinbackground', '1',
           '+vid_lowerinbackground', '0', '+set', 'dd_encounter_pooldump', '1', '+set', 'dd_encounter_plantest', '1',
           '-skill', skill, '+map', 'MAP01', *extra]
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
        if any('ENCPLAN done' in l or BAD.search(l) for l in lines):
            time.sleep(0.5)
            break
        time.sleep(0.2)
    if proc.poll() is None:
        subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'], capture_output=True)
    th.join(2)
    lines.append(f'(run took {time.monotonic() - start:.1f} s, exit {proc.poll()})')
    with open(os.path.join(work, name + '.log'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    out = [l for l in lines if l.startswith('ENCPLAN') or l.startswith('ENCPOOL')]
    with open(os.path.join(work, name + '.plan.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))
    return lines, out


def kv(text):
    return dict(p.split('=', 1) for p in text.split(' ') if '=' in p)


def parse(out):
    pool, genes, plans, armies, warns = {}, {}, {}, defaultdict(dict), []
    for l in out:
        if l.startswith('ENCPOOL monster '):
            name, rest = l.split(' ', 3)[2:]
            pool[name] = kv(rest)
        elif l.startswith('ENCPLAN genes '):
            v = list(map(int, l.split()[2:]))
            genes[v[0]] = v[1:]
        elif l.startswith('ENCPLAN plan '):
            d = kv(l[len('ENCPLAN plan '):])
            plans[int(d['idx'])] = d
        elif l.startswith('ENCPLAN army '):
            d = kv(l[len('ENCPLAN army '):])
            d['list'] = [dict(zip(('role', 'cls', 'kind', 'group', 'tier', 'share', 'parent'), e.split(':')))
                         for e in d['entries'].split('|')] if d['entries'] else []
            armies[int(d['idx'])][d['side']] = d
        elif l.startswith('ENCPLAN warn '):
            warns.append(l)
    return pool, genes, plans, armies, warns


def appendix_genes(idx):
    i = (idx % 4232 * 2897 + 1013) % 4232
    s, n = (0 if i < 2197 else 1), i % 2197
    a, b, c = n % 13, (n // 13) % 13, n // 169
    return [(a + b * j + c * j * j + s * j ** 3) % 13 for j in range(10)]


def is_colour(e):
    return int(e['tier']) < 8 and e['group'] not in FAMILIES and e['group'] not in TITANS and e['group'] != 'Stock'


def cost(pm):
    return max(1, int(float(pm['points']) * 100 + 0.5))


def ring_distance(a, b):
    n = len(RING)
    d = abs(RING.index(a) - RING.index(b))
    return min(d, n - d)   # the kind ring wraps, as the planner's RingDistance


def load_themes():
    """Theme rows of the data file: {name: (kinds, lower-case class patterns, traits)}."""
    themes = {}
    with open(os.path.join(REPO, 'mods', 'doomerfall', 'src', 'doomerfall_encounters.txt'), encoding='utf-8') as f:
        for line in f:
            p = line.split()
            if len(p) >= 2 and p[0] == 'theme':
                kv_ = dict(x.split('=', 1) for x in p[2:] if '=' in x)
                themes[p[1]] = tuple(set(filter(None, kv_.get(k, '').split(','))) for k in ('kinds', 'classes', 'traits'))
                themes[p[1]] = (themes[p[1]][0], {c.lower() for c in themes[p[1]][1]}, themes[p[1]][2])
    return themes


def theme_matches(theme, cls, pm):
    kinds, classes, traits = theme
    return (pm['kind'] in kinds or any(fnmatch.fnmatchcase(cls.lower(), c) for c in classes)
            or bool(traits & set(pm['traits'].split(','))))


def check_standin(name, pool, plans, armies, warns, out, checks):
    """Stand-in for an unpurchasable regional favourite. A kind with a purchasable class is left to the old rule.
    A kind with none always gets one affordable stand-in of another kind, theme-fitting whenever an eligible
    affordable theme-fitting monster exists."""
    themes = load_themes()
    # Story themes (only=1) narrow every role, the stand-in included, and outrank a favourite outside them; their own
    # checks cover them (only theme members, no warnings), so this rule is checked in the other themes.
    with open(os.path.join(REPO, 'mods', 'doomerfall', 'src', 'doomerfall_encounters.txt'), encoding='utf-8') as f:
        story = {l.split()[1] for l in f if l.startswith('theme ') and ' only=1' in l}
    problems, standins, themed, fits = [], 0, 0, 0
    for idx, plan in plans.items():
        a = armies[idx].get('A')
        if not a or plan['regionkind'] == '-' or plan['type'] in story:
            continue
        kind, afford, cw = plan['regionkind'], int(plan['regionafford']), plan['civilwar'] == '1'
        ok_use = lambda pm: pm['capped'] == '0' and pm['group'] not in TITANS and (not cw or pm['civilwar'] == 'safe')
        cheapest = min((cost(pm) for pm in pool.values() if pm['kind'] == kind and ok_use(pm)), default=None)
        unbuyable = cheapest is not None and cheapest > afford
        if unbuyable != (a['region'] == 'standin'):
            problems.append(f'{idx} {kind} cheapest {cheapest} afford {afford} but region={a["region"]}')
            continue
        if not unbuyable:
            continue
        standins += 1
        st = [e for e in a['list'] if e['role'] == 'standin']   # the stand-in and its DRLA family variants
        top = [e for e in st if e['parent'] == '-']
        ref = pool.get(a['regionref'])
        if len(top) != 1 or not ref or ref['kind'] != kind:
            problems.append(f'{idx} standin entries {len(top)} ref {a["regionref"]}')
            continue
        s = top[0]
        if s['kind'] == kind or any(cost(pool[e['cls']]) > afford for e in st):
            problems.append(f'{idx} standin {[e["cls"] for e in st]} for {a["regionref"]} at afford {afford}')
        # Theme: the army as it stood before the stand-in, then every eligible affordable candidate.
        before = [e for e in a['list'] if e['role'] != 'standin']
        colour = {}
        for e in before:
            if e['role'] != 'wildcard' and is_colour(e):
                colour.setdefault(e['kind'], e['group'])
        famkinds = {e['kind'] for e in before if e['group'] in FAMILIES}
        inarmy = {e['cls'] for e in before}
        th = themes.get(plan['type'])
        def eligible(c, pm):
            if pm['kind'] == kind or not ok_use(pm) or cost(pm) > afford or c in inarmy:
                return False
            if is_colour(pm) and colour.get(pm['kind'], pm['group']) != pm['group']:
                return False
            return not (pm['group'] in FAMILIES and pm['kind'] in famkinds)
        if th and any(eligible(c, pm) and theme_matches(th, c, pm) for c, pm in pool.items()):
            if not theme_matches(th, s['cls'], pool[s['cls']]):
                problems.append(f'{idx} {plan["type"]} standin {s["cls"]} misses the theme though a fitting one was affordable')
            themed += 1
        fits += ref['group'] == s['group'] or ring_distance(kind, s['kind']) <= 2
    checks.append((f'{name}: an unpurchasable favourite kind (and only that) gets one affordable stand-in of another kind, '
                   f'theme-fitting whenever one is available ({standins} stand-ins, {themed} with a theme fit available, '
                   f'{fits} share colour/family or sit within 2 on the kind ring) {problems[:4]}',
                   not problems and standins > 0))
    rw = [w for w in warns if 'region' in w]
    checks.append((f'{name}: no regional favourite warnings {rw[:3]}', not rw))
    cell = next((l.split('cell=')[1] for l in out if l.startswith('ENCPLAN ladder ')), '-')
    ladder = sorted((int(plans[i]['level']), i) for i in plans if 3790 <= i <= 3860 and plans[i]['cell'] == cell)
    rows = []
    for lvl, i in ladder:
        a = armies[i]['A']
        e = next((e for e in a['list'] if e['role'] == 'standin'), None) or \
            next((e for e in a['list'] if e['kind'] == plans[i]['regionkind']), None)
        rows.append((lvl, a['region'], e['cls'] if e else '-'))
    print(f'{name}: cell {cell} ladder, favourite {plans[ladder[0][1]]["regionkind"] if ladder else "-"}: '
          + ', '.join(f'L{l} {h} {c}' for l, h, c in rows))
    lw = [w for w in warns if 3790 <= int(w.split('idx=')[1].split()[0]) <= 3860]
    # Every rung's stand-in-or-favourite is checked above; here the ladder must show both, in order.
    first_fav = next((k for k, r in enumerate(rows) if r[1] != 'standin'), len(rows))
    ok = (len(rows) == 11 and rows[0][1] == 'standin' and rows[-1][1] != 'standin'
          and all(r[1] != 'standin' for r in rows[first_fav:]) and not lw)
    checks.append((f'{name}: cell {cell} level ladder: stand-in at every level below {rows[first_fav][0] if first_fav < len(rows) else "-"}, '
                   f'the favourite itself from there up ({sum(r[1] == "standin" for r in rows)}/{len(rows)} stand-ins), '
                   f'no planner warnings {lw[:2]}', ok))


def check_setup(name, lines, out, checks, stock=False):
    pool, genes, plans, armies, warns = parse(out)
    checks.append((f'{name}: planner ran with no fatal or doomerfall script errors',
                   any('ENCPLAN done' in l for l in lines) and not any(BAD.search(l) for l in lines)))
    checks.append((f'{name}: genome printed for all 4232 dungeons and matches appendix A',
                   len(genes) == 4232 and all(genes[i] == appendix_genes(i) for i in genes)))
    rnd = random.Random(1)
    sample = rnd.sample(sorted(genes), min(900, len(genes)))
    worst = min((sum(x != y for x, y in zip(genes[p], genes[q])) for k, p in enumerate(sample) for q in sample[k + 1:]), default=0)
    checks.append((f'{name}: any two of 900 sampled dungeons differ in at least 7 of 10 genes (fewest: {worst})', worst >= 7))
    triples = {(genes[i][0], genes[i][4], genes[i][9]) for i in genes}
    checks.append((f'{name}: every setting triple of genes 0, 4, 9 occurs ({len(triples)}/2197)', len(triples) == 2197))

    problems = []
    for idx, sides in armies.items():
        plan = plans[idx]
        cw = plan['civilwar'] == '1'
        for side, a in sides.items():
            ents = a['list']
            if not ents:
                problems.append(f'{idx}{side} empty army')
                continue
            if sum(int(e['share']) for e in ents) != 1000 or any(int(e['share']) <= 0 for e in ents):
                problems.append(f'{idx}{side} shares {[e["share"] for e in ents]}')
            for e in ents:
                if e['cls'] not in pool:
                    problems.append(f'{idx}{side} {e["cls"]} not in pool')
                    continue
                pm = pool[e['cls']]
                if e['group'] in TITANS:
                    problems.append(f'{idx}{side} titan {e["cls"]} in army')
                if pm['capped'] == '1' and e['role'] in ('anchor', 'core'):
                    problems.append(f'{idx}{side} capped {e["cls"]} as {e["role"]}')
                if pm['capped'] == '1' and int(e['share']) > 100:
                    problems.append(f'{idx}{side} capped {e["cls"]} share {e["share"]}')
                if cw and pm['civilwar'] != 'safe':
                    problems.append(f'{idx}{side} civil war army has unsafe {e["cls"]}')
                if stock and e['cls'] not in STOCK17 and e['cls'] != 'Zombieman':
                    problems.append(f'{idx}{side} non-stock {e["cls"]} in stock run')
            colours = defaultdict(set)
            for e in ents:
                if e['role'] != 'wildcard' and is_colour(e):
                    colours[e['kind']].add(e['group'])
            for k, cs in colours.items():
                if len(cs) > 1:
                    problems.append(f'{idx}{side} kind {k} has colours {cs}')
            fams = defaultdict(set)
            for e in ents:
                if e['role'] != 'wildcard' and e['group'] in FAMILIES:
                    fams[e['kind']].add(e['group'])
            if side == 'A' and a['theme'] == 'unmet' and plan['type'] in ('DragonsDen', 'VampireHaunt'):
                problems.append(f'{idx} theme unmet')
            if side == 'A' and a['region'] == 'unmet':
                problems.append(f'{idx} region unmet')
        if cw:
            if 'B' not in sides:
                problems.append(f'{idx} civil war without side B')
            else:
                a0, b0 = sides['A']['list'][0], sides['B']['list'][0]
                if a0['kind'] == b0['kind'] and abs(int(a0['tier']) - int(b0['tier'])) < 2:
                    problems.append(f'{idx} sides look alike {a0["cls"]} vs {b0["cls"]}')
    checks.append((f'{name}: {len(armies)} plans: every army uses pool classes, shares sum to 1000, no titans, caps kept, '
                   f'Civil War armies all safe and visibly different, one colour per kind, regional kind present '
                   f'{problems[:6]}', len(armies) > 300 and not problems))

    for typ in ('DragonsDen', 'VampireHaunt'):
        idxs = [i for i, p in plans.items() if p['type'] == typ]
        fit = sum(armies[i]['A']['anchorthemed'] == '1' for i in idxs)
        met = sum(armies[i]['A']['theme'] != 'unmet' for i in idxs)
        checks.append((f'{name}: {typ}: anchor follows the theme in {fit}/{len(idxs)} with exceptions, theme present in {met}/{len(idxs)}',
                       len(idxs) == 120 and 0.5 * len(idxs) <= fit < len(idxs) and met == len(idxs)))
    cells = defaultdict(list)
    for i, p in plans.items():
        cells[p['cell']].append(i)
    cluster = cells.get('10,5', [])
    shared = {plans[i]['regionkind'] for i in cluster}
    present = all(armies[i]['A']['region'] != 'unmet' for i in cluster)
    gmin = min((sum(x != y for x, y in zip(plans[p]['genes'].split(','), plans[q]['genes'].split(',')))
                for k, p in enumerate(cluster) for q in cluster[k + 1:]), default=0)
    checks.append((f'{name}: {len(cluster)} neighbours in cell 10,5 share favourite kind {shared}, present in every army, '
                   f'and otherwise differ (fewest differing genes {gmin})', len(cluster) >= 10 and len(shared) == 1 and present and gmin >= 7))
    # The Humanoid story theme (only=1): every member of every army, both Civil War sides, is a Former Human kind.
    humanoid, typ, bad = 0, None, []
    for l in out:
        if l.startswith('ENCPLAN plan '):
            typ = kv(l[len('ENCPLAN plan '):])['type']
            humanoid += typ == 'Humanoid'
        elif l.startswith('ENCPLAN army ') and typ == 'Humanoid':
            d = kv(l[len('ENCPLAN army '):])
            ents = [e.split(':') for e in d['entries'].split('|')] if d['entries'] else []
            if not ents:
                bad.append(f'{d["idx"]}{d["side"]} empty')
            bad += [f'{d["idx"]}{d["side"]} {e[1]}' for e in ents if e[2] not in HUMANOID]
        elif l.startswith('ENCPLAN warn ') and typ == 'Humanoid':
            bad.append(l)
    checks.append((f'{name}: {humanoid} Humanoid plans hold only Former Human kinds {bad[:6]}', humanoid == 35 and not bad))
    # The PlainHumanoid story theme (Privateer's Hold): only plain Former Human classes, never stealthy (invisible).
    plain, cwp, typ, bad, seen = 0, 0, None, [], set()
    for l in out:
        if l.startswith('ENCPLAN plan '):
            d = kv(l[len('ENCPLAN plan '):])
            typ = d['type']
            plain += typ == 'PlainHumanoid'
            cwp += typ == 'PlainHumanoid' and d['civilwar'] == '1'
        elif l.startswith('ENCPLAN army ') and typ == 'PlainHumanoid':
            d = kv(l[len('ENCPLAN army '):])
            ents = [e.split(':') for e in d['entries'].split('|')] if d['entries'] else []
            if not ents:
                bad.append(f'{d["idx"]}{d["side"]} empty')
            for e in ents:
                seen.add(e[1])
                if e[1] not in PLAIN or 'stealthy' in pool.get(e[1], {}).get('traits', 'stealthy'):
                    bad.append(f'{d["idx"]}{d["side"]} {e[1]}')
        elif l.startswith('ENCPLAN warn ') and typ == 'PlainHumanoid':
            bad.append(l)
    checks.append((f'{name}: {plain} PlainHumanoid plans ({cwp} Civil War) hold only plain, visible Former Humans '
                   f'{sorted(seen)} {bad[:6]}', plain == 33 and cwp > 0 and not bad))
    # PlainHumanoid (seedas=Humanoid) narrows the classes only: Privateer's Hold's plan keeps Humanoid's leanings.
    ph = {}
    for l in out:
        if l.startswith('ENCPLAN plan '):
            d = kv(l[len('ENCPLAN plan '):])
            if d['idx'] == '1506' and d['seed'] == '0' and d['level'] == '1':
                ph[d['type']] = d
    keys = ('genes', 'themed', 'civilwar', 'tierlean', 'size', 'placement', 'awareness')
    same = len(ph) == 2 and all(ph['Humanoid'][k] == ph['PlainHumanoid'][k] for k in keys)
    checks.append((f'{name}: Privateer\'s Hold PlainHumanoid plan keeps Humanoid\'s genes, themed, placement and awareness '
                   f'{[(k, ph.get("Humanoid", {}).get(k), ph.get("PlainHumanoid", {}).get(k)) for k in keys]}', same))
    check_standin(name, pool, plans, armies, warns, out, checks)
    ncw = sum(p['civilwar'] == '1' for p in plans.values())
    checks.append((f'{name}: Civil War in {ncw}/{len(plans)} plans (design: about 35%)', 0.2 * len(plans) < ncw < 0.5 * len(plans)))
    return out, warns


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('exe')
    ap.add_argument('work')
    ap.add_argument('--wads', default=r'D:\dev\DoomDaggerfall\GameResources\wads')
    ap.add_argument('--mods', default=r'D:\dev\DoomDaggerfall\GameMods')
    ap.add_argument('--chcompat', default=r'D:\dev\DoomDaggerfall-build\ch-compat.pk3')
    ap.add_argument('--only', default='', help='comma-separated run names')
    a = ap.parse_args()
    os.makedirs(a.work, exist_ok=True)
    subprocess.run([sys.executable, os.path.join(REPO, 'scripts', 'doomerfall', 'build_pk3.py'), os.path.join(a.work, 'doomerfall.pk3')], check=True)
    mod = os.path.join(a.work, 'doomerfall.pk3')
    drla = [os.path.join(a.mods, n) for n in DRLA]
    doom2 = os.path.join(a.wads, 'DOOM2.WAD')
    chfiles = [os.path.join(a.mods, CH)] + drla + [a.chcompat, mod]
    want = set(a.only.split(',')) if a.only else None
    checks = []
    plans = {}
    for name, files, extra, stock, skill in (('stock', [mod], [], True, '3'), ('drla', drla + [mod], [], False, '3'),
                                             ('drlaskill1', drla + [mod], [], False, '1'),
                                             ('chdrla', chfiles, ['+rngseed', '1'], False, '3'),
                                             ('chdrla2', chfiles, ['+rngseed', '4242'], False, '3')):
        if want and name not in want:
            continue
        lines, out = run(a.exe, a.work, doom2, files, name, extra, skill=skill)
        plans[name], warns = check_setup(name, lines, out, checks, stock)
        print(f'{name}: {len(warns)} planner warnings, e.g. {warns[:3]}')
    for one, two, why in (('chdrla', 'chdrla2', 'different rngseed and config'), ('drla', 'drlaskill1', 'skill 3 and skill 1')):
        if one in plans and two in plans:
            p1 = [l for l in plans[one] if l.startswith('ENCPLAN')]
            p2 = [l for l in plans[two] if l.startswith('ENCPLAN')]
            checks.append((f'{one} vs {two} ({why}): {len(p1)} ENCPLAN lines identical', p1 == p2 and len(p1) > 4000))

    failed = 0
    for name, ok in checks:
        failed += not ok
        print(('PASS ' if ok else 'FAIL ') + name)
    print(f'{len(checks) - failed}/{len(checks)} passed')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
