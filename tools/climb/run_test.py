"""Runs the scripted climbing test in UZDoom (no Daggerfall needed) and checks the results.

usage: python tools/climb/run_test.py <uzdoom.exe> <workdir> [--iwad DOOM.WAD]

Builds the Doomerfall mod pk3, the test map, and the harness into workdir, runs harness parts 1 to 3 minimized
with a private config (about 30 s each), and prints PASS or FAIL for each check.
"""
import argparse
import os
import re
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WALK_CLIMB = 8.3333 / 3  # Doom's top walking speed (units per tic) / 3, Daggerfall's climb ratio


def run_part(exe, work, iwad, part, timeout=35):
    cmd = [exe, '-iwad', iwad, '-file', os.path.join(work, 'doomerfall.pk3'), os.path.join(work, 'climbtest.wad'),
           os.path.join(work, 'climbharness.pk3'), '-config', os.path.join(work, 'climbtest.ini'), '-nosound', '-stdout',
           '-noactivate', '+vid_fullscreen', '0', '+i_pauseinbackground', '0', '+vid_activeinbackground', '1',
           '+vid_lowerinbackground', '0', '+set', 'climbtest_part', str(part), '+map', 'CLIMB01', '-skill', '3']
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 7  # SW_SHOWMINNOACTIVE
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, startupinfo=startup, cwd=work,
                            text=True, encoding='utf-8', errors='replace')
    lines = []
    deadline = time.monotonic() + timeout
    import threading

    def reader():
        for line in proc.stdout:
            lines.append(line.rstrip())
    th = threading.Thread(target=reader, daemon=True)
    th.start()
    while time.monotonic() < deadline and proc.poll() is None:
        if any(f'part{part} done' in l for l in lines) or any(('Script error' in l or 'Fatal' in l or 'error' in l.lower() and 'zscript' in l.lower()) for l in lines):
            break
        time.sleep(0.2)
    if proc.poll() is None:
        subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'], capture_output=True)
    th.join(2)
    with open(os.path.join(work, f'part{part}.log'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    return lines


def field(lines, tag, name):
    for l in lines:
        if l.startswith('CLIMBTEST ' + tag + ' ') or l == 'CLIMBTEST ' + tag:
            m = re.search(r'\b' + name + r'=(-?[\d.]+)', l)
            if m:
                return float(m.group(1))
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('exe')
    ap.add_argument('work')
    ap.add_argument('--iwad', default=r'D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD')
    a = ap.parse_args()
    os.makedirs(a.work, exist_ok=True)
    subprocess.run([sys.executable, os.path.join(REPO, 'scripts', 'doomerfall', 'build_pk3.py'), os.path.join(a.work, 'doomerfall.pk3')], check=True)
    subprocess.run([sys.executable, os.path.join(REPO, 'tools', 'climb', 'build_test.py'), a.work], check=True)

    lines = run_part(a.exe, a.work, a.iwad, 1) + run_part(a.exe, a.work, a.iwad, 2) + run_part(a.exe, a.work, a.iwad, 3, timeout=90)
    for l in lines:
        if 'CLIMBTEST' in l or 'DFCLIMB' in l or 'error' in l.lower():
            print(l)
    f = lambda t, n: field(lines, t, n)
    checks = [
        ('starts after pushing about 1 s (36-45 tics after contact)', lambda: 36 <= f('wall', 'start') <= 45),
        ('climbs at Doom walk speed / 3 (within 5%)', lambda: abs(f('wall', 'speed') - WALK_CLIMB) <= WALK_CLIMB * 0.05),
        ('tops out onto the 192-unit wall', lambda: f('wall', 'topped') == 1),
        ('70-degree slope limit on a Daggerfall map', lambda: abs(f('wall', 'steep') - 0.34202) < 1e-4),
        ('holding still sticks to the wall', lambda: abs(f('hold', 'dz')) < 0.5 and f('hold', 'climbing') == 1),
        ('weapon fires while climbing', lambda: f('hold', 'fired') >= 1),
        ('jump lets go and falls to the floor', lambda: f('jump', 'climbing') == 0 and f('jump', 'z') < 1),
        ('strafe moves along the wall without climbing', lambda: f('strafe', 'dy') < -40 and abs(f('strafe', 'dz')) < 1),
        ('skill uses reported', lambda: f('part1 done', 'uses') >= 1),
        ('failed continue roll slips to the ground', lambda: f('slip', 'slip') > f('slip', 'start') >= 0 and f('slip', 'climbing') == 0 and f('slip', 'z') < 1),
        ('75-degree slope is climbed', lambda: f('slope75', 'climbed') == 1 and f('slope75', 'z') > 20),
        ('60-degree slope is walked, not climbed', lambda: f('slope60', 'climbed') == 0 and f('slope60', 'z') > 150),
        ('no climbing off Daggerfall maps', lambda: f('off-wall', 'climbed') == 0),
        ('Doom slope limit restored off Daggerfall maps', lambda: f('off-slope60', 'climbed') == 0 and f('off-slope60', 'z') < 100 and abs(f('off-slope60', 'steep') - 0.70711) < 1e-3),
        ('too-steep staircase (32 risers, 12 treads) is one climb, walking', lambda: f('steepwalk', 'starts') == 1 and f('steepwalk', 'topped') == 1),
        ('too-steep staircase is one climb, running', lambda: f('steeprun', 'starts') == 1 and f('steeprun', 'topped') == 1),
        ('a 64-unit ledge still ends the climb (rests, then a new climb)', lambda: f('ledge64', 'rested') >= 20 and f('ledge64', 'starts') >= 2),
        ('a 24-unit ledge still ends the climb (wider than a 16-unit stair tread)', lambda: f('ledge24', 'rested') >= 20 and f('ledge24', 'starts') >= 2),
        ('failed roll mid-crossing falls, no hop up', lambda: f('cross-slip', 'crossing') == 1 and f('cross-slip', 'slipped') == 1 and f('cross-slip', 'rise') < 2 and f('cross-slip', 'dz') < 0),
        ('Back on a tread climbs down, no hop up', lambda: f('cross-back', 'crossing') == 1 and f('cross-back', 'rise') < 1 and f('cross-back', 'dz') < -5),
        ('a 40-unit ledge with a raised strip at the back still ends the climb', lambda: f('ledge-uneven', 'rested') >= 20 and f('ledge-uneven', 'starts') >= 2),
        ('strafing mid-crossing on steep stairs is not held in place', lambda: f('tread-strafe', 'crossing') == 1 and (abs(f('tread-strafe', 'dy')) > 5 or f('tread-strafe', 'climbing') == 0 and abs(f('tread-strafe', 'dz')) > 5)),
    ]
    failed = 0
    for name, check in checks:
        try:
            ok = bool(check())
        except TypeError:
            ok = False
        failed += not ok
        print(('PASS ' if ok else 'FAIL ') + name)
    print(f'{len(checks) - failed}/{len(checks)} passed')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
