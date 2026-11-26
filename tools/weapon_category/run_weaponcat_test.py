"""Checks Doomerfall's weapon categories (mods/doomerfall/src/zscript/DoomerfallWeaponCategory.zs).

usage: python tools/weapon_category/run_weaponcat_test.py <uzdoom.exe> <workdir> [--iwad WAD] [--mods DIR]

Builds doomerfall.pk3 into workdir and runs DOOM.WAD E1M1 through quiet_run.py with a private config and
+set dd_weaponcat_test 1, which selects each sample gun and prints "WEAPCAT <class> <category> <slot>":
  stock   doomerfall.pk3 only (no DRLA): stock guns get their categories, DRLA samples are absent.
  drla    play_drlax.bat's DRLA set plus doomerfall.pk3: DRLA guns get their categories from DRLA's tokens and ammo.
Logs go to workdir/<run>.log.
"""
import argparse
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
QUIET = r'D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py'
DRLA = ['DoomRL_Arsenal_1.1.5.pk3', 'DoomRL_Monsters_Beta_7.3.pk3', 'drlax_1.2b.pk3']
BAD = re.compile(r'Script error, "doomerfall\.pk3|doomerfall\.pk3:zscript/\S+, line \d+|\bFatal error|VM execution aborted', re.I)

STOCK = {'Fist': 'melee', 'Chainsaw': 'melee', 'Pistol': 'pistol', 'Shotgun': 'shotgun', 'SuperShotgun': 'shotgun',
         'Chaingun': 'automatic', 'RocketLauncher': 'explosive', 'PlasmaRifle': 'energy', 'BFG9000': 'energy'}
# DRLA guns, from their tokens and ammo (GameMods/ExtractedData). Autoshotgun has both shotgun and rapid-fire
# tokens; Plasma Pistol has pistol and cell ammo.
DRLA_EXPECT = {'RLPistol': 'pistol', 'RLShotgun': 'shotgun', 'RLCombatShotgun': 'shotgun', 'RLDoubleShotgun': 'shotgun',
               'RLAutoshotgun': 'shotgun', 'RLChaingun': 'automatic', 'RLMinigun': 'automatic',
               'RLRocketLauncher': 'explosive', 'RLMissileLauncher': 'explosive', 'RLGrenadeLauncher': 'explosive',
               'RLPlasmaRifle': 'energy', 'RLPlasmaPistol': 'energy', 'RLLaserRifle': 'energy', 'RLRailgun': 'energy',
               'RLUzi': 'automatic', 'RLChainsaw': 'melee', 'RLBFG9000': 'energy'}
SLOT = {'shotgun': 4, 'automatic': 5, 'explosive': 6}


def run(exe, work, iwad, files, name, timeout):
    log = os.path.join(work, name + '.log')
    if os.path.exists(log):
        os.remove(log)
    cmd = [sys.executable, QUIET, '--timeout', str(timeout), '--cwd', work, '--', exe, '-iwad', iwad, '-file', *files,
           '-config', os.path.join(work, name + '.ini'), '-nomonsters', '+i_pauseinbackground', '0',
           '+vid_activeinbackground', '1', '+vid_lowerinbackground', '0',
           '+set', 'dd_weaponcat_test', '1', '-skill', '3', '+map', 'E1M1']
    out = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace').stdout
    with open(log, 'w', encoding='utf-8') as f:  # quiet_run passes the game's console output through.
        f.write(out)
    return out.splitlines()


def parse(lines):
    out = {}
    for l in lines:
        m = re.search(r'WEAPCAT (\w+) ([\w-]+)(?: (-?\d+) held=(\w+))?', l)
        if m and m.group(1) != 'done':
            out[m.group(1)] = (m.group(2), int(m.group(3)) if m.group(3) else None, m.group(4))
    return out


def check(name, got, expect, checks):
    for cls, cat in expect.items():
        g = got.get(cls)
        if cls == 'SuperShotgun' and g and g[0] == 'not-given':
            checks.append((f'{name}: {cls} not in this IWAD (DOOM.WAD has none)', True, g))
            continue
        ok = g is not None and g[0] == cat and g[1] == SLOT.get(cat, -1)
        checks.append((f'{name}: {cls} is {cat}', ok, g))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('exe')
    ap.add_argument('work')
    ap.add_argument('--iwad', default=r'D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD')
    ap.add_argument('--mods', default=r'D:\dev\DoomDaggerfall\GameMods')
    a = ap.parse_args()
    os.makedirs(a.work, exist_ok=True)
    mod = os.path.join(a.work, 'doomerfall.pk3')
    subprocess.run([sys.executable, os.path.join(REPO, 'scripts', 'doomerfall', 'build_pk3.py'), mod], check=True)
    checks = []

    stock = run(a.exe, a.work, a.iwad, [mod], 'stock', 45)
    got = parse(stock)
    checks.append(('stock: no script errors', not any(BAD.search(l) for l in stock), None))
    checks.append(('stock: finished', any('WEAPCAT done' in l for l in stock), None))
    check('stock', got, STOCK, checks)
    checks.append(('stock: DRLA samples absent', all(got.get(c, ('?',))[0] == 'absent' for c in DRLA_EXPECT), None))

    drla = run(a.exe, a.work, a.iwad, [os.path.join(a.mods, f) for f in DRLA] + [mod], 'drla', 100)
    got = parse(drla)
    checks.append(('drla: no script errors', not any(BAD.search(l) for l in drla), None))
    checks.append(('drla: finished', any('WEAPCAT done' in l for l in drla), None))
    check('drla', got, DRLA_EXPECT, checks)

    for label, ok, detail in checks:
        print(('PASS ' if ok else 'FAIL ') + label + ('' if ok or detail is None else f'  (got {detail})'))
    failed = sum(1 for _, ok, _ in checks if not ok)
    print('RESULT', 'PASS' if not failed else f'FAIL ({failed})')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
