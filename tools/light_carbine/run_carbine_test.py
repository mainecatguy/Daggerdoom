"""Checks the Light Carbine (mods/doomerfall/src/zscript/DoomerfallLightCarbine.zs).

usage: python tools/light_carbine/run_carbine_test.py <uzdoom.exe> <workdir> [--iwad WAD] [--mods DIR]

Builds doomerfall.pk3 into workdir and runs DOOM.WAD E1M1 through quiet_run.py with a private config:
  stock   doomerfall.pk3 only (no DRLA), +set dd_carbine_test 1: the carbine is given, reloads from an empty
          magazine, fires once per trigger pull, never faster than the Battle Rifle, does 6 x 1d3 per shot, and the
          reload key fills the magazine.
  drla    play_drlax.bat's DRLA set plus doomerfall.pk3, the same checks, and DRLA's Battle Rifle held for comparison
          (5 x 1d3 per shot, automatic, a shot every 4 tics).
  drops   the DRLA set, +set dd_carbine_test 2: about half the Battle Rifles the Battle Rifle monsters drop become
          carbines, and loose Battle Rifles stay Battle Rifles.
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
BAD = re.compile(r'Script error, "doomerfall\.pk3|doomerfall\.pk3:\S+, line \d+|\bFatal error|VM execution aborted', re.I)
CARBINE_DAMAGE = {6, 12, 18}   # 6 x 1d3: the Battle Rifle's 5, +20%.
RIFLE_DAMAGE = {5, 10, 15}     # DRLA's Battle Rifle, 5 x 1d3.
RIFLE_TICS = 4                 # The Battle Rifle's shot: Y Z V B (or W A), one tic each.


# The trigger script, one console line run by +exec (a ZScript handler cannot press buttons; the waits of one line
# run in order, counting game tics). After the handler has set up, a round: an alt-fire press (the handler starts on it, emptying the magazine), one pull on
# the empty gun, a 40-tic hold, 40 taps one tic down and one up, the reload key, and a last 40-tic hold for DRLA's
# Battle Rifle.
ROUND = ('wait 300; +altattack; wait 2; -altattack; wait 30; +attack; wait 2; -attack; wait 100; +attack; wait 40; -attack; wait 20; '
         + '+attack; wait 1; -attack; wait 1; ' * 40
         + 'wait 20; +reload; wait 2; -reload; wait 150; +attack; wait 40; -attack')


def run(exe, work, iwad, files, name, mode, timeout):
    log = os.path.join(work, name + '.log')
    if os.path.exists(log):
        os.remove(log)
    cmd = [sys.executable, QUIET, '--timeout', str(timeout), '--cwd', work, '--', exe, '-iwad', iwad, '-file', *files,
           '-config', os.path.join(work, name + '.ini'), '-nomonsters', '+i_pauseinbackground', '0',
           '+vid_activeinbackground', '1', '+vid_lowerinbackground', '0',
           '+set', 'dd_carbine_test', str(mode), '-skill', '3', '+map', 'E1M1']
    if mode == 1:
        cfg = os.path.join(work, 'carbine_trigger.cfg')
        with open(cfg, 'w', encoding='utf-8') as f:
            f.write(ROUND + '\n')
        cmd += ['+exec', cfg]
    out = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace').stdout
    with open(log, 'w', encoding='utf-8') as f:
        f.write(out)
    return out.splitlines()


def value(lines, pattern):
    for l in lines:
        m = re.search(pattern, l)
        if m:
            return tuple(int(g) for g in m.groups())
    return None


def events(lines):
    """(kind, tic, value) in log order: press/release/reloadpress per gun, hits, magazine readings."""
    out = []
    for l in lines:
        m = re.search(r'(CARBINE|BATTLERIFLE) (press|release|reloadpress) tic=(\d+)', l)
        if m:
            out.append((m.group(1) + ' ' + m.group(2), int(m.group(3)), None))
        m = re.search(r'(CARBINE|BATTLERIFLE) hit tic=(\d+) damage=(\d+)', l)
        if m:
            out.append((m.group(1) + ' hit', int(m.group(2)), int(m.group(3))))
        m = re.search(r'CARBINE mag=(\d+) reserve=(\d+) tic=(\d+)', l)
        if m:
            out.append(('CARBINE mag', int(m.group(3)), (int(m.group(1)), int(m.group(2)))))
    return out


def fire_checks(name, lines, checks, drla):
    checks.append((f'{name}: no script errors', not any(BAD.search(l) for l in lines), None))
    checks.append((f'{name}: finished', any('CARBINE done' in l for l in lines), None))
    checks.append((f'{name}: carbine given and tagged a rifle', any('CARBINE given rifle=1' in l for l in lines), None))
    ev = events(lines)
    presses = [i for i, e in enumerate(ev) if e[0] == 'CARBINE press']
    releases = [i for i, e in enumerate(ev) if e[0] == 'CARBINE release']
    reload_at = next((i for i, e in enumerate(ev) if e[0] == 'CARBINE reloadpress'), None)
    if len(presses) < 10 or len(releases) < 10 or reload_at is None:
        checks.append((f'{name}: the console trigger script reached the game', False, (len(presses), len(releases), reload_at)))
        return
    def between(i, j, kind):
        """Events of a kind from the tic of event i up to (not including) the tic of event j. A hit is logged before
        the press of the same tic (the gun fires while the player thinks; presses are seen after), so tics decide."""
        lo, hi = ev[i][1], ev[j][1] if j < len(ev) else 1 << 30
        return [e for e in ev if e[0] == kind and lo <= e[1] < hi]
    # 1. One pull on the empty magazine: no shot, the magazine fills to 20 from 100 bullets.
    first = between(presses[0], presses[1], 'CARBINE hit')
    mags = [e[2] for e in between(presses[0], presses[1], 'CARBINE mag')]
    checks.append((f'{name}: a pull on the empty magazine reloads it (20 loaded, 80 left) without firing',
                   not first and mags and mags[-1] == (20, 80), (first, mags)))
    # 2. Held 40 tics: one shot.
    hold_len = ev[releases[1]][1] - ev[presses[1]][1]
    held = between(presses[1], presses[2], 'CARBINE hit')
    checks.append((f'{name}: trigger held {hold_len} tics fires one shot', hold_len >= 35 and len(held) == 1, held))
    # 3. Taps: fires again, never faster than the Battle Rifle.
    taps = between(presses[2], reload_at, 'CARBINE hit')
    gaps = [b[1] - a[1] for a, b in zip(taps, taps[1:])]
    checks.append((f'{name}: fast tapping fires again, never faster than a shot every {RIFLE_TICS} tics',
                   len(taps) >= 5 and min(gaps) >= RIFLE_TICS, (len(taps), sorted(set(gaps)))))
    # 4. Reload key: the magazine fills from the reserve.
    before = [e[2] for e in between(0, reload_at, 'CARBINE mag')]
    after = [e[2] for e in between(reload_at, len(ev), 'CARBINE mag')]
    ok = before and after and after[-1][0] == 20 and after[-1][1] == before[-1][1] - (20 - before[-1][0])
    checks.append((f'{name}: the reload key fills the magazine from the reserve', bool(ok), (before[-1:], after[-1:])))
    damage = [e[2] for e in ev if e[0] == 'CARBINE hit']
    checks.append((f'{name}: every carbine hit is 6 x 1d3 (6, 12 or 18)', bool(damage) and set(damage) <= CARBINE_DAMAGE,
                   sorted(set(damage))))
    print(f'{name}: carbine hits {len(damage)}, damage values {sorted(set(damage))}, '
          f'mean {sum(damage) / max(1, len(damage)):.2f}, tap gaps {sorted(set(gaps))}')
    if drla:
        rifle = [e for e in ev if e[0] == 'BATTLERIFLE hit']
        rgaps = [b[1] - a[1] for a, b in zip(rifle, rifle[1:])]
        rdamage = [e[2] for e in rifle]
        print(f'{name}: Battle Rifle hits {len(rifle)}, damage values {sorted(set(rdamage))}, '
              f'mean {sum(rdamage) / max(1, len(rdamage)):.2f}, gaps {sorted(set(rgaps))}')
        checks.append((f'{name}: DRLA Battle Rifle held fires automatically, every {RIFLE_TICS} tics, 5 x 1d3',
                       len(rifle) >= 5 and min(rgaps) == RIFLE_TICS and set(rdamage) <= RIFLE_DAMAGE,
                       (len(rifle), sorted(set(rgaps)), sorted(set(rdamage)))))
        checks.append((f'{name}: carbine damage unit is the Battle Rifle unit +20%',
                       bool(damage and rdamage) and min(damage) * 5 == min(rdamage) * 6,
                       (min(damage or [0]), min(rdamage or [0]))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('exe')
    ap.add_argument('work')
    ap.add_argument('--iwad', default=r'D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD')
    ap.add_argument('--mods', default=r'D:\dev\DoomDaggerfall\GameMods')
    ap.add_argument('--only', choices=['stock', 'drla', 'drops'])
    a = ap.parse_args()
    os.makedirs(a.work, exist_ok=True)
    mod = os.path.join(a.work, 'doomerfall.pk3')
    subprocess.run([sys.executable, os.path.join(REPO, 'scripts', 'doomerfall', 'build_pk3.py'), mod], check=True)
    drla_files = [os.path.join(a.mods, f) for f in DRLA] + [mod]
    checks = []

    if a.only in (None, 'stock'):
        fire_checks('stock', run(a.exe, a.work, a.iwad, [mod], 'stock', 1, 45), checks, False)
    if a.only in (None, 'drla'):
        fire_checks('drla', run(a.exe, a.work, a.iwad, drla_files, 'drla', 1, 150), checks, True)
    if a.only in (None, 'drops'):
        lines = run(a.exe, a.work, a.iwad, drla_files, 'drops', 2, 150)
        checks.append(('drops: no script errors', not any(BAD.search(l) for l in lines), None))
        checks.append(('drops: finished', any('CARBINE done' in l for l in lines), None))
        checks.append(('drops: every Battle Rifle monster exists', not any('CARBDROP absent' in l for l in lines), None))
        k = value(lines, r'CARBDROP kills rifleSpawns=(\d+) carbineSpawns=(\d+) liveRifles=(\d+) liveCarbines=(\d+)')
        if k:
            rifles, carbines, live_rifles, live_carbines = k
            share = carbines / rifles if rifles else 0
            print(f'drops: {rifles} Battle Rifles dropped, {carbines} became carbines ({share:.0%}); '
                  f'on the floor {live_rifles} rifles, {live_carbines} carbines')
            checks.append(('drops: the monsters dropped at least 150 Battle Rifles', rifles >= 150, k))
            checks.append(('drops: about half became carbines (35% to 65%)', 0.35 <= share <= 0.65, k))
            checks.append(('drops: each swapped rifle is gone, a carbine in its place',
                           live_rifles == rifles - carbines and live_carbines == carbines, k))
        else:
            checks.append(('drops: kill count reported', False, None))
        loose = value(lines, r'CARBDROP loose rifleSpawns=(\d+) carbineSpawns=(\d+)')
        checks.append(('drops: 100 loose Battle Rifles stay Battle Rifles', loose == (100, 0), loose))

    for label, ok, detail in checks:
        print(('PASS ' if ok else 'FAIL ') + label + ('' if ok or detail is None else f'  (got {detail})'))
    failed = sum(1 for _, ok, _ in checks if not ok)
    print('RESULT', 'PASS' if not failed else f'FAIL ({failed})')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
