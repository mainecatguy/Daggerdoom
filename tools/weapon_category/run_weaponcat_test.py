"""Checks Doomerfall's weapon categories (mods/doomerfall/src/zscript/DoomerfallWeaponCategory.zs).

usage: python tools/weapon_category/run_weaponcat_test.py <uzdoom.exe> <workdir> [--iwad WAD] [--mods DIR]

Builds doomerfall.pk3 into workdir and runs DOOM.WAD E1M1 through quiet_run.py with a private config and
+set dd_weaponcat_test 1, which selects each sample gun and prints "WEAPCAT <class> <category> <slot> held=..
second=<category> <slot> uses=<slot>" (a weapon in two skills has a second category; "uses" is the skill it reads,
the first one here since there is no Daggerfall character):
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

# Fist is unarmed (Hand-to-Hand, slot 30), not Melee (backlog skills-in-doom.md: Hand-to-Hand governs the fist).
STOCK = {'Fist': 'unarmed', 'Chainsaw': 'melee', 'Pistol': 'pistol', 'Shotgun': 'shotgun', 'SuperShotgun': 'shotgun',
         'Chaingun': 'automatic', 'RocketLauncher': 'explosive', 'PlasmaRifle': 'energy', 'BFG9000': 'energy'}
# DRLA guns, from their tokens and ammo (GameMods/ExtractedData). Autoshotgun has both shotgun and rapid-fire
# tokens.
DRLA_EXPECT = {'RLPistol': 'pistol', 'RLShotgun': 'shotgun', 'RLCombatShotgun': 'shotgun', 'RLDoubleShotgun': 'shotgun',
               'RLAutoshotgun': 'shotgun', 'RLChaingun': 'automatic', 'RLMinigun': 'automatic',
               'RLRocketLauncher': 'explosive', 'RLMissileLauncher': 'explosive', 'RLGrenadeLauncher': 'explosive',
               'RLPlasmaRifle': 'energy', 'RLLaserRifle': 'energy', 'RLRailgun': 'energy',
               'RLChainsaw': 'melee', 'RLBFG9000': 'energy',
               # Pistols (owner 2026-11-26): DRLA's pistol-token guns are pistols (slot 7), including the Storm
               # Pistol (also shotgun token) and Plasma Pistol (cells). Not the Uzis (owner 2026-11-27: "It's an
               # Automatic. That's miscategorized."): they are Automatics, below.
               'RLStormPistol': 'pistol', 'RLPlasmaPistol': 'pistol',
               'RLCombatPistol': 'pistol', 'RLMarksmanPistol': 'pistol', 'RLHandcannon': 'pistol',
               'RLHuntingRevolver': 'pistol', 'RLSilencedPistol': 'pistol', 'RLPP7': 'pistol'}
# Rifles are never pistols ("no rifle is counted"). Their categories come from their DRLA tokens: rifle token ->
# precision, rapid-fire only -> automatic, the Sniper Rifle has neither -> other. No category has the Rifles slot (8)
# until Doomerfall's own rifle tag (todo rifletag 01) defines which guns are rifles.
RIFLES = {'RLMarksmanRifle': 'precision', 'RLBattleRifle': 'automatic', 'RLVanguardRifle': 'automatic',
          'RLSniperRifle': 'other', 'RLElephantGun': 'precision', 'RLGaussRifle': 'precision',
          'RLAntiMaterielRifle': 'precision'}
DRLA_EXPECT.update(RIFLES)
# Owner (backlog rifles-skill.md; 2026-11-26 "Those all sound like automatics"): these are Automatics, not rifles,
# although they carry DRLA's single-shot rifle token. They must never get the Rifles slot.
NOT_RIFLES = {'RLAssaultRifleChaingun': 'automatic', 'RLAssaultRifleMinigun': 'automatic', 'RLAutocannon': 'automatic'}
DRLA_EXPECT.update(NOT_RIFLES)
# The Uzi family (owner 2026-11-27): Automatics although DRLA gives them its pistol token. The cell-fed Plasma Uzi stays
# Pistol + Energy (below) until the owner decides what it should be.
UZIS = {'RLUzi': 'automatic', 'RLHighPowerUzi': 'automatic', 'RLStormUzi': 'automatic', 'RLBurstCannonUzi': 'automatic',
        'RLAssaultRifleUzi': 'automatic', 'RLDemolitionAmmoUzi': 'automatic', 'RLNanoManufactureAmmoUzi': 'automatic'}
DRLA_EXPECT.update(UZIS)
# Energy Weapons and Melee (skillcore placeholders, 2026-11-26). DRLA's fist is unarmed like the stock one; its melee
# weapons have the melee token (the Energysaw also uses cells, and Melee comes first). Energy guns that recharge
# instead of using cells are on Doomerfall's list; a self-charging energy pistol stays a pistol.
MELEE_ENERGY = {'RLFist': 'unarmed', 'RLDoubleChainsaw': 'melee', 'RLPiercingChainsaw': 'melee',
                'RLEnergysaw': 'melee', 'RLRipper': 'melee', 'RLNuclearPlasmaRifle': 'energy',
                'RLNuclearBFG9000': 'energy', 'RLBFGInfinity': 'energy', 'RLNanoManufactureAmmoLaserRifle': 'energy',
                'RLNuclearPlasmaPistol': 'pistol', 'RLLightweaver': 'energy', 'RLDragonslayer': 'melee',
                'RLNanoShrapnelPlasmaShotgun': 'energy'}
DRLA_EXPECT.update(MELEE_ENERGY)
# Weapons in two skills (owner 2026-11-26, gamedesign/decisions/20261126-two-skill-weapons-owner.md): a Pistol or
# Shotgun that is also an Energy Weapon. Every other sample's second category is 'other'. Energy pistols are pistols
# first; energy shotguns are energy first. A missile pistol stays a pistol only.
TWO_SKILL = {'RLPlasmaPistol': 'energy', 'RLNuclearPlasmaPistol': 'energy', 'RLBlaster': 'energy', 'RLPlasmaUzi': 'energy',
             'RLBaronBlaster': 'energy', 'RLStormNuclearPlasmaPistol': 'energy',
             'RLNanoShrapnelPlasmaShotgun': 'shotgun', 'RLLaserShotgun': 'shotgun', 'RLPlasmaShotgun': 'shotgun',
             'RLNuclearPlasmaShotgun': 'shotgun', 'RLHeavyPlasmaShotgun': 'shotgun'}
DRLA_EXPECT.update({'RLLaserShotgun': 'energy', 'RLPlasmaShotgun': 'energy', 'RLNuclearPlasmaShotgun': 'energy',
                    'RLHeavyPlasmaShotgun': 'energy', 'RLBlaster': 'pistol', 'RLPlasmaUzi': 'pistol',
                    'RLBaronBlaster': 'pistol', 'RLStormNuclearPlasmaPistol': 'pistol', 'RLMiniMissilePistol': 'pistol'})
SLOT ={'shotgun': 4, 'automatic': 5, 'explosive': 6, 'pistol': 7, 'energy': 9, 'melee': 10, 'unarmed': 30}
RIFLES_SLOT = 8


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
        m = re.search(r'WEAPCAT (\w+) ([\w-]+)(?: (-?\d+) held=(\w+) second=(\w+) (-?\d+) uses=(-?\d+))?', l)
        if m and m.group(1) != 'done':
            out[m.group(1)] = (m.group(2), int(m.group(3)) if m.group(3) else None, m.group(4),
                               m.group(5), int(m.group(6)) if m.group(6) else None, int(m.group(7)) if m.group(7) else None)
    return out


def check(name, got, expect, checks):
    for cls, cat in expect.items():
        g = got.get(cls)
        if cls == 'SuperShotgun' and g and g[0] == 'not-given':
            checks.append((f'{name}: {cls} not in this IWAD (DOOM.WAD has none)', True, g))
            continue
        second = TWO_SKILL.get(cls, 'other')
        # Without Daggerfall there is no character sheet, so a two-skill weapon uses its first category's skill.
        ok = (g is not None and g[0] == cat and g[1] == SLOT.get(cat, -1) and g[3] == second
              and g[4] == SLOT.get(second, -1) and g[5] == SLOT.get(cat, -1))
        label = f'{cat} + {second}' if second != 'other' else cat
        checks.append((f'{name}: {cls} is {label}', ok, g))


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

    drla = run(a.exe, a.work, a.iwad, [os.path.join(a.mods, f) for f in DRLA] + [mod], 'drla', 180)
    got = parse(drla)
    checks.append(('drla: no script errors', not any(BAD.search(l) for l in drla), None))
    checks.append(('drla: finished', any('WEAPCAT done' in l for l in drla), None))
    check('drla', got, DRLA_EXPECT, checks)
    checks.append(('drla: no rifle is a pistol or has the Pistols slot',
                   all(c in got and got[c][0] != 'pistol' and got[c][1] != SLOT['pistol'] for c in RIFLES),
                   {c: got.get(c) for c in RIFLES}))
    checks.append(('drla: no fist has the Melee slot',
                   all(c in got and got[c][1] != SLOT['melee'] for c in ('Fist', 'RLFist')),
                   {c: got.get(c) for c in ('Fist', 'RLFist')}))
    checks.append(('drla: Assault Rifle Chaingun/Minigun and Autocannon do not have the Rifles slot',
                   all(c in got and got[c][1] != RIFLES_SLOT for c in NOT_RIFLES), {c: got.get(c) for c in NOT_RIFLES}))

    for label, ok, detail in checks:
        print(('PASS ' if ok else 'FAIL ') + label + ('' if ok or detail is None else f'  (got {detail})'))
    failed = sum(1 for _, ok, _ in checks if not ok)
    print('RESULT', 'PASS' if not failed else f'FAIL ({failed})')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
