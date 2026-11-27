"""Checks Doomerfall's rifle tag (mods/doomerfall/src/zscript/DoomerfallRifleTag.zs) against the owner's definition.

usage: python tools/rifle_tag/run_rifletag_test.py <uzdoom.exe> <workdir> [--iwad WAD] [--mods DIR]

1. derive_rifles.py --check: the committed list is what the rule gives from DRLA's own weapon files.
2. Builds doomerfall.pk3 into workdir and runs DOOM.WAD E1M1 through quiet_run.py with a private config and
   +set dd_rifletag_test 1, which lists every loaded weapon class the tag marks, then holds each one and prints its
   weapon category:
     stock   doomerfall.pk3 only (no DRLA): nothing is tagged and the game starts.
     drla    play_drlax.bat's DRLA set plus doomerfall.pk3: the tagged guns are exactly the owner's rifles, and none of
             them is an Automatic, Shotgun, Explosive, Energy Weapon, Pistol, melee weapon or fist.
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

# The test oracle, written from the owner's definition (goal rifletag, 2026-11-26) and the rifles research
# (work/notes/20261126-003658.md), not from the tool: "all ballistic semi-automatic weapons that are not explosives,
# energy weapons, shotguns or pistols"; heavy single-shot rifles count; the Elephant Gun is a rifle.
OWNER_RIFLES = {'RLMarksmanRifle', 'RLHighPowerMarksmanRifle', 'RLAssaultRifleBattleRifle', 'RLSniperRifle',
                'RLElephantGun', 'RLAntiMaterielRifle', 'RLGaussRifle',
                'DoomerfallLightCarbine'}  # the carbine is Doomerfall's own rifle (owner, 2026-11-26)
# Named by the owner or the research as not rifles: Automatics (the three Assault/Master guns by owner ruling, the
# automatic and burst rifles), the Steel Beast (shotgun), the Railgun and energy rifles (energy), rifle-family pistols.
NOT_RIFLES = {'RLAssaultRifleChaingun', 'RLAssaultRifleMinigun', 'RLAutocannon', 'RLSteelBeast', 'RLRailgun',
              'RLBattleRifle', 'RLHighPowerBattleRifle', 'RLStealthRifle', 'RLVanguardRifle', 'RLHighPowerVanguardRifle',
              'RLBulletstormRifle', 'RLBurstCannonBattleRifle', 'RLDemolitionAmmoBattleRifle',
              'RLNanomanufactureAmmoBattleRifle', 'RLChameleonRifle', 'RLMarathonAssaultRifle', 'RLSoulstormRifle',
              'RLAssaultRiflePlasmaRifle', 'RLAssaultRifleLaserRifle', 'RLAssaultRifleNuclearPlasmaRifle',
              'RLPlasmaRifle', 'RLLaserRifle', 'RLDuke2Rifle', 'RLAssaultRifleUzi', 'RLChaingun', 'RLMinigun',
              'RLPistol', 'RLUzi', 'RLShotgun'}
# Categories a rifle must never have (DoomerfallWeaponCategory labels). 'precision' (DRLA's single-shot rifle token)
# and 'other' are allowed: those are the rifle-ish leftovers the tag sorts out.
FORBIDDEN = {'automatic', 'shotgun', 'explosive', 'energy', 'pistol', 'melee', 'unarmed'}


def run(exe, work, iwad, files, name, timeout):
    log = os.path.join(work, name + '.log')
    if os.path.exists(log):
        os.remove(log)
    cmd = [sys.executable, QUIET, '--timeout', str(timeout), '--cwd', work, '--', exe, '-iwad', iwad, '-file', *files,
           '-config', os.path.join(work, name + '.ini'), '-nomonsters', '+i_pauseinbackground', '0',
           '+vid_activeinbackground', '1', '+vid_lowerinbackground', '0',
           '+set', 'dd_rifletag_test', '1', '-skill', '3', '+map', 'E1M1']
    out = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace').stdout
    with open(log, 'w', encoding='utf-8') as f:  # quiet_run passes the game's console output through.
        f.write(out)
    return out.splitlines()


def parse(lines):
    weapons, tagged, held = None, [], {}
    for l in lines:
        m = re.search(r'RIFLETAG weapons (\d+)', l)
        if m:
            weapons = int(m.group(1))
        m = re.search(r'RIFLETAG tagged (\w+)', l)
        if m:
            tagged.append(m.group(1))
        m = re.search(r'RIFLETAG held (\w+) (\S+)(?: (\S+) heldclass=(\w+))?', l)
        if m:
            held[m.group(1)] = (m.group(2), m.group(3), m.group(4))
    return weapons, tagged, held


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('exe')
    ap.add_argument('work')
    ap.add_argument('--iwad', default=r'D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD')
    ap.add_argument('--mods', default=r'D:\dev\DoomDaggerfall\GameMods')
    a = ap.parse_args()
    os.makedirs(a.work, exist_ok=True)
    checks = []

    derive = subprocess.run([sys.executable, '-I', os.path.join(REPO, 'tools', 'rifle_tag', 'derive_rifles.py'), '--check'],
                            capture_output=True, text=True)
    print(derive.stdout, end='')
    checks.append(('derive: committed list matches the rule on DRLA\'s weapon files', derive.returncode == 0, None))

    mod = os.path.join(a.work, 'doomerfall.pk3')
    subprocess.run([sys.executable, os.path.join(REPO, 'scripts', 'doomerfall', 'build_pk3.py'), mod], check=True)

    stock = run(a.exe, a.work, a.iwad, [mod], 'stock', 30)
    weapons, tagged, held = parse(stock)
    checks.append(('stock: no script errors', not any(BAD.search(l) for l in stock), None))
    checks.append(('stock: E1M1 started and the test finished', any('RIFLETAG done' in l for l in stock), None))
    checks.append(('stock: weapon classes were listed', bool(weapons), weapons))
    checks.append(('stock: only the Light Carbine is tagged without DRLA', tagged == ['DoomerfallLightCarbine'], tagged))

    drla = run(a.exe, a.work, a.iwad, [os.path.join(a.mods, f) for f in DRLA] + [mod], 'drla', 60)
    weapons, tagged, held = parse(drla)
    for l in tagged:
        print('TAGGED', l, held.get(l))
    checks.append(('drla: no script errors', not any(BAD.search(l) for l in drla), None))
    checks.append(('drla: finished', any('RIFLETAG done' in l for l in drla), None))
    checks.append(('drla: weapon classes were listed', bool(weapons), weapons))
    checks.append(('drla: tagged guns are exactly the owner\'s rifles', set(tagged) == OWNER_RIFLES,
                   {'extra': sorted(set(tagged) - OWNER_RIFLES), 'missing': sorted(OWNER_RIFLES - set(tagged))}))
    checks.append(('drla: no named non-rifle is tagged', not (set(tagged) & NOT_RIFLES), sorted(set(tagged) & NOT_RIFLES)))
    bad = {c: held.get(c) for c in tagged
           if c not in held or held[c][2] != c or held[c][0] in FORBIDDEN or held[c][1] in FORBIDDEN}
    checks.append(('drla: no tagged gun is held as an Automatic, Shotgun, Explosive, Energy, Pistol or melee weapon',
                   not bad, bad))

    for label, ok, detail in checks:
        print(('PASS ' if ok else 'FAIL ') + label + ('' if ok or detail is None else f'  (got {detail})'))
    failed = sum(1 for _, ok, _ in checks if not ok)
    print('RESULT', 'PASS' if not failed else f'FAIL ({failed})')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
