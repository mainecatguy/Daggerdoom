"""Burn look candidates: screenshots and rendered frame times (tools/burn/candidates/zscript/BurnLookShots.zs).

usage: python tools/burn/look_shots.py --exe UZDOOM [--work DIR] [--shots] [--frames] [--drla] [--only S:T,...]
Each launch goes through scripts/overnight/quiet_run.py itself. DOOM2.WAD MAP15 by default, staged at the most open spot the scene finds (the game's IWAD; the Arch-vile flame
sprites are Doom II only). The candidate pack is built in --work from the zscript here plus the Schism FRPR flame
sprites from GameMods; it is never committed.
  --shots   scenes 1 (small), 2 (large), 3 (60 imps) x styles 5 (particles), 1 (Arch-vile), 2 (Schism lite), 0 (shipped look): PNGs
  --frames  scene 4 (400 ZombieMen) x styles 4 (not burning), 3 (look off), 5, 1, 2, 0: frame-time lines + a PNG after the window.
  Every run keeps its own log (log-<time>.txt) and appends its result line to <work>/results.txt.
"""
import argparse, os, re, subprocess, sys, time, zipfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.abspath(__file__))
QUIET = r'D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py'
MODS = r'D:\dev\DoomDaggerfall\GameMods'
IWAD = r'D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD'
FRPR = os.path.join(MODS, r'ExtractedData\Schism_097D\Sprites\FLAMES')
DRLA = ['DoomRL_Arsenal_1.1.5.pk3', 'DoomRL_Monsters_Beta_7.3.pk3', 'drlax_1.2b.pk3']
BAD = re.compile(r'Script error, "(doomerfall|burnlook)|\bFatal error|VM execution aborted|Execution could not continue', re.I)
NAMES = {4: 'notburning', 3: 'lookoff', 0: 'shipped', 5: 'particles', 1: 'archvile', 2: 'schismlite'}
SCENES = {1: 'small', 2: 'large', 3: 'pack', 4: 'frames'}


def build_candidates(path):
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('ZSCRIPT.txt', 'version "3.3"\n#include "zscript/BurnLookShots.zs"\n')
        z.writestr('CVARINFO.txt', 'server noarchive int dd_bls_scene = 0;\nserver noarchive int dd_bls_style = 0;\n')
        z.writestr('MAPINFO.txt', 'gameinfo\n{\n\tAddEventHandlers = "BurnLookShots"\n}\n')
        z.write(os.path.join(HERE, 'candidates', 'zscript', 'BurnLookShots.zs'), 'zscript/BurnLookShots.zs')
        for f in 'ABCDEFGH':
            z.write(os.path.join(FRPR, 'FRPR%s0' % f), 'sprites/FRPR%s0.png' % f)


def launch(exe, work, files, scene, style, tag, mapname):
    name = f'{tag}{SCENES[scene]}_{NAMES[style]}'
    out = os.path.join(work, name)
    os.makedirs(out, exist_ok=True)
    for old in os.listdir(out):
        if old.endswith('.png'):
            os.remove(os.path.join(out, old))
    if scene == 4:
        # Screenshot only after the frame-time window (it ends 455 tics after setup), so saving it is not measured.
        script = ['wait 480', 'screenshot', 'wait 10', 'quit']
    else:
        script = ['wait 140', 'screenshot', 'wait 25', 'screenshot', 'wait 10', 'quit']
    cfg = os.path.join(out, 'shots.cfg')
    with open(cfg, 'w') as f:
        f.write('; '.join(script) + '\n')
    look = '1' if style == 0 else '0'
    cmd = [exe, '-iwad', IWAD, '-file', *files, '-config', os.path.join(out, 'test.ini'), '-nosound', '-stdout',
           '-skill', '3', '-nomonsters', '-width', '1280', '-height', '720',
           '+logfile', 'log.txt', '+vid_fullscreen', '0', '+wipetype', '0', '+i_pauseinbackground', '0',
           '+vid_activeinbackground', '1', '+vid_lowerinbackground', '0', '+vid_scalemode', '5',
           '+vid_scale_customwidth', '1280', '+vid_scale_customheight', '720', '+screenblocks', '12',
           '+r_drawplayersprites', '0', '+screenshot_type', 'png', '+screenshot_dir', out,
           '+vid_vsync', '0', '+vid_maxfps', '1000', '+cl_capfps', '0',
           '+set', 'dd_burn_look', look, '+set', 'dd_bls_scene', str(scene), '+set', 'dd_bls_style', str(style),
           '+map', mapname, '+exec', cfg]
    res = subprocess.run([sys.executable, QUIET, '--cwd', out, '--timeout', '45', '--', *cmd], capture_output=True,
                         text=True, errors='replace')
    log = res.stdout or ''
    stamp = time.strftime('%Y%m%d-%H%M%S')
    with open(os.path.join(out, f'log-{stamp}.txt'), 'w', encoding='utf-8') as f:	# one log per run, kept
        f.write(log + res.stderr)
    errs = [l for l in log.splitlines() if BAD.search(l)]
    if not log:
        errs.append('no log (launch failed): ' + (res.stdout + res.stderr).strip()[-300:])
    bls = [l for l in log.splitlines() if l.startswith('BLS')]
    pngs = sorted(x for x in os.listdir(out) if x.endswith('.png'))
    line = f'== {stamp} {mapname} {name}: {len(pngs)} png, ' + ' | '.join(bls) + ('' if not errs else ' ERRORS: ' + ' / '.join(errs[:3]))
    print(line)
    with open(os.path.join(work, 'results.txt'), 'a', encoding='utf-8') as f:
        f.write(line + '\n')
    return not errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--exe', required=True)
    ap.add_argument('--work', default=r'D:\dev\DoomDaggerfall-build\burnlook')
    ap.add_argument('--shots', action='store_true')
    ap.add_argument('--frames', action='store_true')
    ap.add_argument('--drla', action='store_true', help='load the DRLA set first')
    ap.add_argument('--map', default='MAP15')
    ap.add_argument('--only', default='', help='scene:style pairs, e.g. 1:0,2:1')
    a = ap.parse_args()
    os.makedirs(a.work, exist_ok=True)
    mod = os.path.join(a.work, 'doomerfall.pk3')
    subprocess.run([sys.executable, os.path.join(REPO, 'scripts', 'doomerfall', 'build_pk3.py'), mod], check=True,
                   capture_output=True)
    cand = os.path.join(a.work, 'burnlook-candidates.pk3')
    build_candidates(cand)
    files = ([os.path.join(MODS, f) for f in DRLA] if a.drla else []) + [mod, cand]
    tag = 'drla_' if a.drla else ''
    runs = []
    if a.only:
        runs = [tuple(int(v) for v in p.split(':')) for p in a.only.split(',')]
    if a.shots:
        runs += [(s, t) for s in (1, 2, 3) for t in (5, 1, 2, 0)]
    if a.frames:
        runs += [(4, t) for t in (4, 3, 5, 1, 2, 0)]
    ok = all([launch(a.exe, a.work, files, s, t, tag, a.map) for s, t in runs])
    print('OK' if ok else 'ERRORS')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
