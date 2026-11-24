"""Checks that DRLA guns whose magazine empties in one shot reload by themselves with doomerfall.pk3 loaded.

usage: python tools/autoreload/run_test.py <uzdoom.exe> <workdir> [--iwad DOOM.WAD] [--mods GameMods]

Builds doomerfall.pk3 and the test harness into workdir, then runs DOOM.WAD E1M1 minimized with a private config:
  stock     doomerfall.pk3 without DRLA: the map loads and DRLA's option does not exist.
  control   the DRLA set without doomerfall.pk3: DRLA's option is off and the guns stay empty after one shot.
  drla      the DRLA set with doomerfall.pk3, in parts of about 25 s: every gun reloads after one shot.
Each run stops at once on a script or fatal error. Logs go to workdir/<run>.log.
"""
import argparse
import os
import re
import subprocess
import sys
import threading
import time
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DRLA = ['DoomRL_Arsenal_1.1.5.pk3', 'DoomRL_Monsters_Beta_7.3.pk3', 'drlax_1.2b.pk3']  # play.bat's DRLA set
GUNS = 31     # harness Guns[] size
PART = 8      # guns per run, to keep each run near 25 s
# The DRLA set prints script errors of its own at every load (an empty translation, menu entries, optional addon
# classes) and the game runs on, so script errors count only in our files. Real stops count from anywhere.
BAD = re.compile(r'Script error, "(doomerfall|reloadharness)\.pk3|\bFatal error|VM execution aborted|Execution could not continue', re.I)


def build(work):
    subprocess.run([sys.executable, os.path.join(REPO, 'scripts', 'doomerfall', 'build_pk3.py'), os.path.join(work, 'doomerfall.pk3')], check=True)
    src = os.path.join(REPO, 'tools', 'autoreload', 'harness')
    with zipfile.ZipFile(os.path.join(work, 'reloadharness.pk3'), 'w', zipfile.ZIP_DEFLATED) as z:
        for name in os.listdir(src):
            z.write(os.path.join(src, name), name)


def run(exe, work, iwad, files, name, extra=(), timeout=90):
    cmd = [exe, '-iwad', iwad, '-file', *files, '-config', os.path.join(work, 'reloadtest.ini'), '-nosound', '-stdout',
           '-noactivate', '-nomonsters', '+vid_fullscreen', '0', '+i_pauseinbackground', '0', '+vid_activeinbackground', '1',
           '+vid_lowerinbackground', '0', *extra, '+map', 'E1M1', '-skill', '3']
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 7  # SW_SHOWMINNOACTIVE
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, startupinfo=startup, cwd=work,
                            text=True, encoding='utf-8', errors='replace')
    lines = []
    th = threading.Thread(target=lambda: [lines.append(l.rstrip()) for l in proc.stdout], daemon=True)
    th.start()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and proc.poll() is None:
        if any('RELOADTEST done' in l or BAD.search(l) for l in lines):
            break
        time.sleep(0.2)
    if proc.poll() is None:
        subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'], capture_output=True)
    th.join(2)
    lines.append(f'(run took {time.monotonic() - deadline + timeout:.1f} s, exit {proc.poll()})')
    with open(os.path.join(work, name + '.log'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    return lines


def results(lines):
    return {m.group(1): (m.group(2), l) for l in lines for m in [re.search(r'RELOADTEST gun=(\w+) result=(\w+)', l)] if m}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('exe')
    ap.add_argument('work')
    ap.add_argument('--iwad', default=r'D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD')
    ap.add_argument('--mods', default=r'D:\dev\DoomDaggerfall\GameMods')
    a = ap.parse_args()
    os.makedirs(a.work, exist_ok=True)
    build(a.work)
    mod, harness = os.path.join(a.work, 'doomerfall.pk3'), os.path.join(a.work, 'reloadharness.pk3')
    drla = [os.path.join(a.mods, n) for n in DRLA]
    checks = []

    stock = run(a.exe, a.work, a.iwad, [mod, harness], 'stock')
    checks.append(('stock: E1M1 loads with doomerfall.pk3, no script errors',
                   any('E1M1' in l for l in stock) and any('RELOADTEST done' in l for l in stock) and not any(BAD.search(l) for l in stock)))
    checks.append(('stock: DRLA option does not exist', any('option=missing' in l for l in stock)))

    control = run(a.exe, a.work, a.iwad, drla + [harness], 'control', ['+set', 'reloadtest_count', '2'])
    got = results(control)
    checks.append(('control (no doomerfall.pk3): DRLA option off', any('option=off' in l for l in control)))
    checks.append(('control: RLShotgun and RLDoubleShotgun stay empty after one shot',
                   got.get('RLShotgun', ('',))[0] == 'empty' and got.get('RLDoubleShotgun', ('',))[0] == 'empty'))

    control2 = run(a.exe, a.work, a.iwad, drla + [harness], 'control2', ['+set', 'reloadtest_from', str(GUNS - 2)])
    got = results(control2)
    checks.append(('control: RLBaronBlaster and RLMarathonShotguns stay empty after one shot',
                   got.get('RLBaronBlaster', ('',))[0] == 'empty' and got.get('RLMarathonShotguns', ('',))[0] == 'empty'))

    # The player turns DRLA's option off: DRLA's own guns and this mod's two extra guns both stop reloading.
    optout = run(a.exe, a.work, a.iwad, drla + [mod, harness], 'optout',
                 ['+set', 'reloadtest_optout', '1', '+set', 'reloadtest_from', str(GUNS - 2)])
    got = results(optout)
    checks.append(('option off: RLBaronBlaster and RLMarathonShotguns stay empty',
                   any('option=off' in l for l in optout) and got.get('RLBaronBlaster', ('',))[0] == 'empty'
                   and got.get('RLMarathonShotguns', ('',))[0] == 'empty'))

    got, errors = {}, False
    for start in range(0, GUNS, PART):
        lines = run(a.exe, a.work, a.iwad, drla + [mod, harness], f'drla{start}',
                    ['+set', 'reloadtest_from', str(start), '+set', 'reloadtest_count', str(PART)])
        got.update(results(lines))
        errors |= any(BAD.search(l) for l in lines) or not any('option=on' in l for l in lines)
    for gun, (res, line) in got.items():
        print(line)
    checks.append(('drla: option on and no script errors in any part', not errors))
    checks.append((f'drla: all {GUNS} guns reload after one shot', len(got) == GUNS and all(r == 'reloaded' for r, _ in got.values())))

    failed = 0
    for name, ok in checks:
        failed += not ok
        print(('PASS ' if ok else 'FAIL ') + name)
    print(f'{len(checks) - failed}/{len(checks)} passed')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
