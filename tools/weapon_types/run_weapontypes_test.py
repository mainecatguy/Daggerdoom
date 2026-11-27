"""Checks the weapon types and brief description Doom sends for Daggerfall's gun descriptions (todo: weapontypes 01).

usage: python tools/weapon_types/run_weapontypes_test.py <uzdoom.exe> <workdir> [--iwad WAD] [--mods DIR]

1. derive_weapon_tokens.py --check: the committed DRLA token table is what DRLA's weapon files give.
2. Builds doomerfall.pk3 into workdir and runs DOOM.WAD E1M1 through quiet_run.py with a private config and
   +set dd_weapontypes_test 1 (zscript/DoomerfallWeaponTypesTest.zs):
     stock   doomerfall.pk3 only: stock guns get their types and no brief, and the game starts.
     drla    play_drlax.bat's DRLA set plus doomerfall.pk3: sample guns get the types the owner's rules give, the DRLA
             pistol gets its PDA summary as its brief, and for every gun with DRLA tokens (and every stock gun) the
             class-based answer the description uses equals the skill code's answer for the held gun.
The drla run holds about 180 guns one after another, so it needs a few minutes rather than the usual 30 seconds.
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

# Oracles from the owner's rules (manual.md "Weapon skills" and "Weapons that belong to two skills", rifletag goal),
# not from the code under test. Order is first category, second category, then Rifle.
STOCK = {'Fist': 'Hand-to-Hand', 'Chainsaw': 'Melee', 'Pistol': 'Pistol', 'Shotgun': 'Shotgun',
         'SuperShotgun': 'Shotgun', 'Chaingun': 'Automatic', 'RocketLauncher': 'Explosive', 'PlasmaRifle': 'Energy',
         'BFG9000': 'Energy'}
DRLA_SAMPLES = dict(STOCK)
DRLA_SAMPLES.update({
    'RLFist': 'Hand-to-Hand', 'RLChainsaw': 'Melee', 'RLPistol': 'Pistol', 'RLCombatPistol': 'Pistol',
    'RLUzi': 'Pistol', 'RLShotgun': 'Shotgun', 'RLCombatShotgun': 'Shotgun', 'RLDoubleShotgun': 'Shotgun',
    'RLChaingun': 'Automatic', 'RLMinigun': 'Automatic', 'RLRocketLauncher': 'Explosive', 'RLPlasmaRifle': 'Energy',
    'RLLaserRifle': 'Energy', 'RLRailgun': 'Energy', 'RLBFG9000': 'Energy', 'RLNuclearPlasmaRifle': 'Energy',
    'RLPlasmaPistol': 'Pistol, Energy', 'RLBlaster': 'Pistol, Energy', 'RLLaserShotgun': 'Energy, Shotgun',
    'RLPlasmaShotgun': 'Energy, Shotgun', 'RLMarksmanRifle': 'Rifle', 'RLSniperRifle': 'Rifle',
    'RLGaussRifle': 'Rifle', 'RLElephantGun': 'Rifle',
})
# Not sampled: the Assault Rifle Chaingun, Assault Rifle Minigun and Autocannon are Automatics by the owner's ruling,
# but carry DRLA's single-shot rifle token, so the skill code reads them as Precision (no skill yet;
# DoomerfallWeaponCategory's header). The description follows the skill code, so they show "Types: none".
PISTOL_BRIEF = 'Your trusty 10mm pistol. It may be nice, but better find something stronger.'
PLASMA_PISTOL_BRIEF = 'Experiments into creating scalar plasma weapon technology resulted in the Plasma Pistol.'


def run(exe, work, iwad, files, name, timeout):
    log = os.path.join(work, name + '.log')
    if os.path.exists(log):
        os.remove(log)
    cmd = [sys.executable, QUIET, '--timeout', str(timeout), '--cwd', work, '--', exe, '-iwad', iwad, '-file', *files,
           '-config', os.path.join(work, name + '.ini'), '-nomonsters', '+i_pauseinbackground', '0',
           '+vid_activeinbackground', '1', '+vid_lowerinbackground', '0',
           '+set', 'dd_weapontypes_test', '1', '-skill', '3', '+map', 'E1M1']
    out = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace').stdout
    with open(log, 'w', encoding='utf-8') as f:  # quiet_run passes the game's console output through.
        f.write(out)
    return out.splitlines()


def parse(lines):
    classes, held = {}, {}
    for l in lines:
        m = re.search(r'WEAPTYPES class (\w+) types=(.*?) brief=(.*)$', l)
        if m:
            classes[m.group(1)] = (m.group(2).strip(), m.group(3).strip())
        m = re.search(r'WEAPTYPES held (\w+) (\S+) (\S+) heldclass=(\w+)', l)
        if m:
            held[m.group(1)] = (m.group(2), m.group(3), m.group(4))
    return classes, held


def common(checks, name, lines, classes, held, samples):
    checks.append((name + ': no script errors', not any(BAD.search(l) for l in lines), None))
    checks.append((name + ': E1M1 started and the test finished', any('WEAPTYPES done' in l for l in lines), None))
    checks.append((name + ': weapon classes were listed', bool(classes), len(classes)))
    wrong = {c: classes.get(c, ('missing',))[0] for c, want in samples.items() if classes.get(c, ('',))[0] != want}
    checks.append((name + ': sample guns show the types the owner\'s rules give', not wrong, wrong))
    unsettled = {c: v for c, v in held.items() if v[2] != c}
    checks.append((name + ': every tested gun was held', not unsettled and bool(held), unsettled))
    differ = {c: v[:2] for c, v in held.items() if v[2] == c and v[0] != v[1]}
    checks.append((name + ': the description\'s types equal the skill code\'s for the held gun', not differ, differ))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('exe')
    ap.add_argument('work')
    ap.add_argument('--iwad', default=r'D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD')
    ap.add_argument('--mods', default=r'D:\dev\DoomDaggerfall\GameMods')
    a = ap.parse_args()
    os.makedirs(a.work, exist_ok=True)
    checks = []

    derive = subprocess.run([sys.executable, '-I', os.path.join(REPO, 'tools', 'weapon_types', 'derive_weapon_tokens.py'),
                             '--check'], capture_output=True, text=True)
    print(derive.stdout + derive.stderr, end='')
    checks.append(('derive: committed token table matches DRLA\'s weapon files', derive.returncode == 0, None))

    mod = os.path.join(a.work, 'doomerfall.pk3')
    subprocess.run([sys.executable, os.path.join(REPO, 'scripts', 'doomerfall', 'build_pk3.py'), mod], check=True)

    stock = run(a.exe, a.work, a.iwad, [mod], 'stock', 40)
    classes, held = parse(stock)
    common(checks, 'stock', stock, classes, held, STOCK)
    briefs = {c: b for c, (_, b) in classes.items() if b}
    checks.append(('stock: no gun has a brief without DRLA', not briefs, briefs))

    drla = run(a.exe, a.work, a.iwad, [os.path.join(a.mods, f) for f in DRLA] + [mod], 'drla', 420)
    classes, held = parse(drla)
    common(checks, 'drla', drla, classes, held, DRLA_SAMPLES)
    checks.append(('drla: the pistol\'s brief is its PDA summary', classes.get('RLPistol', ('', ''))[1] == PISTOL_BRIEF,
                   classes.get('RLPistol')))
    plasma = classes.get('RLPlasmaPistol', ('', ''))[1]
    checks.append(('drla: a gun with no quoted summary gets its first sentence', plasma == PLASMA_PISTOL_BRIEF, plasma))
    tested = [c for c in held if c.startswith('RL')]
    nobrief = sorted(c for c in tested if not classes.get(c, ('', ''))[1])
    checks.append(('drla: every DRLA gun with type tokens has a brief', not nobrief, nobrief))
    long = sorted(c for c, (_, b) in classes.items() if len(b.encode('utf-8')) > 255)
    checks.append(('drla: every brief fits the bridge\'s 255 bytes', not long, long))
    notypes = sorted(c for c in tested if not classes.get(c, ('', ''))[0])
    print('DRLA guns held: %d; with no types (no weapon skill): %s' % (len(tested), notypes))
    for c in sorted(DRLA_SAMPLES):
        print('SAMPLE %s types=%s brief=%s' % (c, *classes.get(c, ('?', '?'))))

    for label, ok, detail in checks:
        print(('PASS ' if ok else 'FAIL ') + label + ('' if ok or detail is None else f'  (got {detail})'))
    failed = sum(1 for _, ok, _ in checks if not ok)
    print('RESULT', 'PASS' if not failed else f'FAIL ({failed})')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
