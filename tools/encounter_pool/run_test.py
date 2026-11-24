"""Dumps the encounter monster pool (doomerfall.pk3, +set dd_encounter_pooldump 1) in each mod setup and checks it.

usage: python tools/encounter_pool/run_test.py <uzdoom.exe> <workdir> [--wads DIR] [--mods DIR] [--chcompat PK3]

Runs, each minimized with a private config and stopped at "ENCPOOL done" or on a fatal or script error:
  stock     DOOM2.WAD MAP01, doomerfall.pk3 only: the 17 stock monsters, one per kind.
  drla      DOOM2.WAD MAP01, DRLA Arsenal + Monsters + DRLAX + doomerfall.pk3.
  chdrla    DOOM2.WAD MAP01, Colourful Hell + DRLA + ch-compat + doomerfall.pk3 (the project load order).
  e1m1      DOOM.WAD E1M1 with doomerfall.pk3, and e1m1drla with the DRLA set: the map still loads cleanly.
Logs go to workdir/<run>.log (whole console) and workdir/<run>.pool.txt (the ENCPOOL lines).
"""
import argparse
import os
import re
import subprocess
import sys
import threading
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DRLA = ['DoomRL_Arsenal_1.1.5.pk3', 'DoomRL_Monsters_Beta_7.3.pk3', 'drlax_1.2b.pk3']
CH = 'ColourfulHell_1_04.pk3'
# The mods print script errors of their own at load and run on, so script errors count only in our file.
BAD = re.compile(r'Script error, "doomerfall\.pk3|doomerfall\.pk3:zscript/\S+, line \d+|\bFatal error|VM execution aborted|Execution could not continue', re.I)
EXCLUDED = [re.compile(p, re.I) for p in (r'^RLCC', r'^RLDRPG', r'Reborn$')]


def run(exe, work, iwad, files, name, warp, timeout=45):
    cmd = [exe, '-iwad', iwad, '-file', *files, '-config', os.path.join(work, 'pooltest.ini'), '-nosound', '-stdout',
           '-noactivate', '+vid_fullscreen', '0', '+i_pauseinbackground', '0', '+vid_activeinbackground', '1',
           '+vid_lowerinbackground', '0', '+set', 'dd_encounter_pooldump', '1', '-skill', '3', *warp]
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
        if any('ENCPOOL done' in l or BAD.search(l) for l in lines):
            time.sleep(0.5)
            break
        time.sleep(0.2)
    if proc.poll() is None:
        subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'], capture_output=True)
    th.join(2)
    lines.append(f'(run took {time.monotonic() - start:.1f} s, exit {proc.poll()})')
    with open(os.path.join(work, name + '.log'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    pool = [l for l in lines if l.startswith('ENCPOOL')]
    with open(os.path.join(work, name + '.pool.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(pool))
    return lines, pool


def monsters(pool):
    out = {}
    for l in pool:
        m = re.match(r'ENCPOOL monster (\S+) (.*)', l)
        if m:
            out[m.group(1)] = dict(kv.split('=', 1) for kv in m.group(2).split(' '))
    return out


def summary(pool):
    for l in pool:
        if l.startswith('ENCPOOL summary'):
            return dict(kv.split('=', 1) for kv in l.split(' ')[2:])
    return {}


def ch_stubs(mods):
    """Colourful Hell's wrapper stubs: names its Colourset spawners list that have no parent, Monster or Health."""
    root = os.path.join(mods, 'ExtractedData', 'ColourfulHell_1_04', 'decorate')
    if not os.path.isdir(root):
        return set()
    listed, real, cur = set(), set(), None
    for fn in os.listdir(root):
        for line in open(os.path.join(root, fn), encoding='latin-1'):
            s = line.split('//')[0]
            h = re.match(r'\s*actor\s+"?(\w+)"?\s*(:)?', s, re.I)
            if h:
                cur = h.group(1).lower()
                if h.group(2):
                    real.add(cur)  # has a parent class, so it is a real monster, not a selector
                continue
            d = re.match(r'\s*dropitem\s+"(\w+)"', s, re.I)
            if d and cur and cur.startswith('colourset'):
                listed.add(d.group(1).lower())
            if cur and re.match(r'\s*(monster|health)\b', s, re.I):
                real.add(cur)
    return {n for n in listed if n not in real}


def common_checks(name, lines, pool, checks):
    s = summary(pool)
    checks.append((f'{name}: pool dumped, no fatal or doomerfall script errors',
                   any('ENCPOOL done' in l for l in lines) and not any(BAD.search(l) for l in lines)))
    checks.append((f'{name}: data file parsed with no errors', s.get('data_errors') == '0'))
    mons = monsters(pool)
    bad = [n for n in mons if any(p.search(n) for p in EXCLUDED)]
    checks.append((f'{name}: no RLCC*, RLDRPG* or *Reborn class in the pool {bad[:5]}', not bad))
    noval = [n for n, m in mons.items() if float(m['points']) <= 0 or m['kind'] == '' or not (1 <= int(m['tier']) <= 8)]
    checks.append((f'{name}: every monster has a kind, a tier 1-8 and points above 0 {noval[:5]}', not noval))
    return mons


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
    doom2, doom1 = os.path.join(a.wads, 'DOOM2.WAD'), os.path.join(a.wads, 'DOOM.WAD')
    want = set(a.only.split(',')) if a.only else None
    checks = []

    if not want or 'stock' in want:
        lines, pool = run(a.exe, a.work, doom2, [mod], 'stock', ['+map', 'MAP01'])
        mons = common_checks('stock', lines, pool, checks)
        kinds = [l for l in pool if l.startswith('ENCPOOL kind ')]
        checks.append(('stock: 17 monsters, one of each kind, all Stock tier 1',
                       len(mons) == 17 and len(kinds) == 17 and all(l.endswith('count=1') for l in kinds)
                       and all(m['tier'] == '1' for m in mons.values())))
        checks.append(('stock: Arch-vile and Pain Elemental are not Civil War safe, Former Human is',
                       mons.get('Archvile', {}).get('civilwar', '').startswith('unsafe')
                       and mons.get('PainElemental', {}).get('civilwar', '').startswith('unsafe')
                       and mons.get('Zombieman', {}).get('civilwar') == 'safe'))

    if not want or 'drla' in want:
        lines, pool = run(a.exe, a.work, doom2, drla + [mod], 'drla', ['+map', 'MAP01'])
        mons = common_checks('drla', lines, pool, checks)
        checks.append(('drla: no stock class left in the pool (DRLA replaces them)',
                       not any(n in mons for n in ('Zombieman', 'DoomImp', 'Cyberdemon'))))
        checks.append(('drla: RLCyberneticLostSoul is capped and unsafe', mons.get('RLCyberneticLostSoul', {}).get('capped') == '1'
                       and mons['RLCyberneticLostSoul']['civilwar'].startswith('unsafe')))
        checks.append(('drla: RLStealth classes are stealthy', any(n.startswith('RLStealth') for n in mons)
                       and all('stealthy' in m['traits'] for n, m in mons.items() if n.startswith('RLStealth'))))
        checks.append(('drla: family tiers present (Standard 1, Nightmare 4, Technophobia 6, Armageddon 7)',
                       mons.get('RLImp', {}).get('tier') == '1' and mons.get('RLNightmareImp', {}).get('tier') == '4'
                       and mons.get('RLCyberneticImp', {}).get('tier') == '6' and mons.get('RLArmageddonImp', {}).get('tier') == '7'))

    if not want or 'chdrla' in want:
        files = [os.path.join(a.mods, CH)] + drla + [a.chcompat, mod]
        lines, pool = run(a.exe, a.work, doom2, files, 'chdrla', ['+map', 'MAP01'])
        mons = common_checks('chdrla', lines, pool, checks)
        stubs = ch_stubs(a.mods)
        found = [n for n in mons if n.lower() in stubs]
        checks.append((f'chdrla: no Colourful Hell wrapper stub in the pool ({len(stubs)} stubs known) {found[:5]}', stubs and not found))
        checks.append(('chdrla: BrownImp2 is a tier 5 DoomImp', mons.get('BrownImp2', {}).get('tier') == '5'
                       and mons['BrownImp2']['kind'] == 'DoomImp'))
        checks.append(('chdrla: BlackImpEX is a tier 8 titan of 140 points', mons.get('BlackImpEX', {}).get('tier') == '8'
                       and abs(float(mons['BlackImpEX']['points']) - 140) < 0.01))
        checks.append(('chdrla: DRLA monsters still in the pool', 'RLImp' in mons and 'RLCyberneticLostSoul' in mons))

    for name, iwad_files in (('e1m1', [mod]), ('e1m1drla', drla + [mod])):
        if want and name not in want:
            continue
        lines, pool = run(a.exe, a.work, doom1, iwad_files, name, ['+map', 'E1M1'])
        checks.append((f'{name}: DOOM.WAD E1M1 loads with no fatal or doomerfall script errors',
                       any('E1M1' in l for l in lines) and any('ENCPOOL done' in l for l in lines)
                       and not any(BAD.search(l) for l in lines)))

    failed = 0
    for name, ok in checks:
        failed += not ok
        print(('PASS ' if ok else 'FAIL ') + name)
    print(f'{len(checks) - failed}/{len(checks)} passed')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
