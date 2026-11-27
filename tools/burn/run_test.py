"""Burn damage test (mods/doomerfall/src/zscript/DoomerfallBurnTest.zs).

usage: python tools/burn/run_test.py [--exe UZDOOM] [--work DIR] [--count N]
Run it through scripts/overnight/quiet_run.py. Builds doomerfall.pk3, then runs DOOM.WAD E1M1 with dd_burn_test N:
  look      dd_burn_look 1, doomerfall.pk3 only
  nolook    dd_burn_look 0: the damage must be the same
  drla      look on, with the DRLA set (Arsenal, Monsters, DRLAX) loaded first
Each run must print three PASS lines (pack, take, player). Logs go to <work>/<name>.log.
"""
import argparse, os, re, subprocess, sys, threading, time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODS = r'D:\dev\DoomDaggerfall\GameMods'
WAD = r'D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD'
DRLA = ['DoomRL_Arsenal_1.1.5.pk3', 'DoomRL_Monsters_Beta_7.3.pk3', 'drlax_1.2b.pk3']
BAD = re.compile(r'Script error, "doomerfall\.pk3|doomerfall\.pk3:zscript/\S+, line \d+|\bFatal error|VM execution aborted|Execution could not continue', re.I)


def run(exe, work, files, name, look, count, timeout=40):
    cmd = [exe, '-iwad', WAD, '-file', *files, '-config', os.path.join(work, 'burntest.ini'), '-nosound', '-stdout',
           '-noactivate', '+vid_fullscreen', '0', '+i_pauseinbackground', '0', '+vid_activeinbackground', '1',
           '+vid_lowerinbackground', '0', '+set', 'dd_burn_test', str(count), '+set', 'dd_burn_look', str(look),
           '-skill', '3', '-nomonsters', '+map', 'E1M1']
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=work, text=True,
                            encoding='utf-8', errors='replace')
    lines = []
    th = threading.Thread(target=lambda: [lines.append(l.rstrip()) for l in proc.stdout], daemon=True)
    th.start()
    start = time.monotonic()
    while time.monotonic() - start < timeout and proc.poll() is None:
        if any('BURNTEST done' in l or BAD.search(l) for l in lines):
            time.sleep(0.3)
            break
        time.sleep(0.2)
    if proc.poll() is None:
        subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'], capture_output=True)
    th.join(2)
    with open(os.path.join(work, name + '.log'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--exe', default=r'D:\dev\DoomDaggerfall-build\uzdoom\Release\uzdoom.exe')
    ap.add_argument('--work', default=r'D:\dev\DoomDaggerfall-build\burntest')
    ap.add_argument('--count', type=int, default=400)
    a = ap.parse_args()
    os.makedirs(a.work, exist_ok=True)
    mod = os.path.join(a.work, 'doomerfall.pk3')
    subprocess.run([sys.executable, os.path.join(REPO, 'scripts', 'doomerfall', 'build_pk3.py'), mod], check=True)
    drla = [os.path.join(MODS, f) for f in DRLA]
    failed = 0
    for name, files, look in (('look', [mod], 1), ('nolook', [mod], 0), ('drla', drla + [mod], 1)):
        lines = run(a.exe, a.work, files, name, look, a.count)
        out = [l for l in lines if l.startswith('BURNTEST')]
        errs = [l for l in lines if BAD.search(l)]
        passes = sum(1 for l in out if l.endswith('PASS'))
        ok = passes == 3 and not errs and any('BURNTEST done' in l for l in out)
        failed += not ok
        print(f'== {name}: {"PASS" if ok else "FAIL"}')
        for l in out + errs[:5]:
            print('  ' + l)
    print('ALL PASS' if not failed else f'{failed} run(s) FAILED')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
