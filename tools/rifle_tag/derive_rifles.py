"""Derives Doomerfall's rifle tag from the DRLA weapons themselves (todo: rifletag 01).

usage: python tools/rifle_tag/derive_rifles.py [--drla DIR] [--write | --check] [--table FILE]

The owner's definition (2026-11-26): a rifle is "any ballistic semi-automatic weapon that is not an explosive, energy
weapon, shotgun or pistol". This script reads every DRLA weapon's DECORATE and applies that rule from the gun's own
data:

  ballistic        an ammo type (magazine or reserve) descends from Doom's Clip or Shell.
  not explosive    no ammo type descends from RocketAmmo.
  not energy       no ammo type descends from Cell, and the gun is not on DoomerfallWeaponCategory's list of
                   self-charging energy guns.
  not shotgun      the gun does not give DRLA's RLShotgunTypeWeapon token (and is not a stock Shotgun).
  not pistol       the gun does not give DRLA's RLPistolTypeWeapon token.
  not melee        no MELEEWEAPON flag and no RLMeleeTypeWeapon token.
  semi-automatic   with fire held (no mods, no perks, ammo loaded), the closest two shots are at least SEMI_MIN_TICS
                   apart (trace_fire explains the walk). DRLA's automatics fire 1-4 tics apart, bursts 2 tics apart
                   inside the burst; its semi-autos 7 or more. Every DRLA gun keeps firing while fire is held, so the
                   time between shots is the sign, not a flag. A gun that never fires while fire is held (the
                   charge-and-release Gauss Rifle) needs a press per shot, so it is measured pressed once per shot.

Then a short exception list, each with the owner's reason (EXCEPTIONS below).

Checked against the rifles research (work/notes/20261126-003658.md): Marksman 7, High Power Marksman 8, Sniper 37
and Gauss tap 68 tics match it. The Anti-Materiel Rifle (22) and Elephant Gun (7) read shorter than the research,
because the reload after each shot is not walked; both are still well above the line.

--write puts the resulting class list into mods/doomerfall/src/zscript/DoomerfallRifleTag.zs between the GENERATED
markers. --check fails if that file's list differs from what the rule gives now. --table writes every candidate gun
(ballistic and not caught by an earlier category) with its cycle, shots, tokens and verdict, as Markdown.
"""
import argparse
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_DRLA = r'D:\dev\DoomDaggerfall\GameMods\ExtractedData\DoomRL_Arsenal_1.1.5'
TAG_FILE = os.path.join(REPO, 'mods', 'doomerfall', 'src', 'zscript', 'DoomerfallRifleTag.zs')
CATEGORY_FILE = os.path.join(REPO, 'mods', 'doomerfall', 'src', 'zscript', 'DoomerfallWeaponCategory.zs')

SEMI_MIN_TICS = 6

# Guns the rule tags or misses against the owner's definition. Kept as small as possible; each says why.
EXCEPTIONS = {
    # Owner, 2026-11-26 (goal rifletag): Automatics, not rifles. Each fires one bullet per 13-37 tic cycle, so the
    # rule reads them as semi-automatic: the chaingun and minigun Assault mods fire slowly, and the Autocannon is a
    # one-round chamber that reloads after each 10-bullet shot.
    'RLAssaultRifleChaingun': (False, 'owner: an Automatic (Assault mod of the Chaingun), not a rifle'),
    'RLAssaultRifleMinigun': (False, 'owner: an Automatic (Assault mod of the Minigun), not a rifle'),
    'RLAutocannon': (False, 'owner: an Automatic, not a rifle'),
}

STOCK_BASES = {'clip': 'Clip', 'shell': 'Shell', 'rocketammo': 'RocketAmmo', 'cell': 'Cell'}
SHOT = re.compile(r'\b(A_FireBullets|A_FireCustomMissile|A_FireProjectile|A_RailAttack|A_CustomRailgun|'
                  r'A_FireShotgun2?|A_FireCGun|A_FirePistol|A_CustomBulletAttack)\b', re.I)
FRAME = re.compile(r'^("?[#\-\w]{4}"?)\s+("?[\w\[\]\\#]+"?)\s+(-?\d+|random\s*\(\s*-?\d+\s*,\s*-?\d+\s*\))\s*(.*)$', re.I)
FLOW = re.compile(r'^(goto\s+([\w:.]+)(?:\s*\+\s*(\d+))?|loop|stop|wait|fail)\b', re.I)
LABEL = re.compile(r'^([\w.:]+)\s*:(?!:)\s*(.*)$')


def strip_comments(text):
    text = re.sub(r'/\*.*?\*/', ' ', text, flags=re.S)
    return re.sub(r'//[^\n]*', '', text)


class Actor:
    def __init__(self, name, parent, body, path):
        self.name, self.parent, self.body, self.path = name, parent, body, path
        self.props = {}
        self.flags = set()
        self.states = []   # list of (tics, rest-of-line) or ('goto', label, offset) / ('loop',) / ('stop',)
        self.labels = {}   # lower label -> index into states
        self.label_starts = []
        self._parse()

    def _parse(self):
        m = re.search(r'\bstates\s*\{', self.body, re.I)
        head = self.body[:m.start()] if m else self.body
        for line in head.splitlines():
            line = line.strip()
            for f in re.findall(r'([+-])([\w.]+)', line) if line.startswith(('+', '-')) else []:
                self.flags.add((f[0], f[1].lower().split('.')[-1]))
            pm = re.match(r'([\w.]+)\s+(.+?)\s*;?$', line)
            if pm and not line.startswith(('+', '-')):
                self.props[pm.group(1).lower()] = pm.group(2).strip().strip('"')
        if not m:
            return
        depth, i = 1, m.end()
        while i < len(self.body) and depth:
            depth += {'{': 1, '}': -1}.get(self.body[i], 0)
            i += 1
        last_label = None
        for raw in self.body[m.end():i - 1].splitlines():
            line = raw.strip()
            while line:
                lm = LABEL.match(line)
                if lm and not FRAME.match(line):
                    last_label = len(self.states)
                    self.labels[lm.group(1).lower()] = last_label
                    self.label_starts.append(last_label)
                    line = lm.group(2).strip()
                    continue
                fm = FLOW.match(line)
                if fm:
                    word = fm.group(1).split()[0].lower()
                    if word == 'goto':
                        self.states.append(('goto', fm.group(2), int(fm.group(3) or 0)))
                    elif word == 'loop':
                        self.states.append(('goto_index', last_label or 0))
                    else:
                        self.states.append((word,))
                    break
                fr = FRAME.match(line)
                if fr:
                    frames = fr.group(2).strip('"')
                    tics = fr.group(3)
                    rm = re.match(r'random\s*\(\s*(-?\d+)\s*,\s*(-?\d+)\s*\)', tics, re.I)
                    t = (int(rm.group(1)) + int(rm.group(2))) / 2 if rm else int(tics)
                    for _ in frames:
                        self.states.append(('frame', t, fr.group(4)))
                break


def load_actors(drla_dir):
    actors = {}
    for root, _, files in os.walk(os.path.join(drla_dir, 'actors')):
        for fn in files:
            if not fn.lower().endswith('.txt'):
                continue
            path = os.path.join(root, fn)
            with open(path, encoding='latin-1') as f:
                text = strip_comments(f.read())
            for m in re.finditer(r'^\s*actor\s+(\w+)(?:\s*:\s*(\w+))?[^{\n]*\s*\{', text, re.I | re.M):
                depth, i = 1, m.end()
                while i < len(text) and depth:
                    depth += {'{': 1, '}': -1}.get(text[i], 0)
                    i += 1
                a = Actor(m.group(1), m.group(2), text[m.end():i - 1], os.path.relpath(path, drla_dir))
                actors[a.name.lower()] = a
    return actors


def ancestors(actors, name):
    seen = []
    while name and name.lower() not in seen:
        seen.append(name.lower())
        a = actors.get(name.lower())
        name = a.parent if a else None
    return seen


def stock_base(actors, name):
    for n in ancestors(actors, name):
        if n in STOCK_BASES:
            return STOCK_BASES[n]
    return None


def prop(actors, a, key):
    for n in ancestors(actors, a.name):
        x = actors.get(n)
        if x and key in x.props:
            return x.props[key]
    return None


def find_label(actors, a, label):
    """Returns (actor, index) of a state label, looking up the parents (Super:: and inherited labels)."""
    label = label.lower()
    names = ancestors(actors, a.name)
    if label.startswith('super::'):
        names, label = names[1:], label[7:]
    for n in names:
        x = actors.get(n)
        if x and label in x.labels:
            return x, x.labels[label]
    return None, None


def frame_offset(owner, i, n):
    """The index of the n-th state after index i. Goto, Loop and Stop are not states (they set the previous state's
    next state), so DECORATE's jump offsets and Goto Label+N count frames only."""
    while i < len(owner.states) and owner.states[i][0] != 'frame':
        i += 1  # A label that starts with a Goto: land on the next real state.
    while n > 0 and i < len(owner.states):
        i += 1
        if i < len(owner.states) and owner.states[i][0] == 'frame':
            n -= 1
    return i


def trace_fire(actors, a, ammo, debug=False, held=True, start='Fire', inv0=None, ready_fires=False):
    """Fires the gun with the trigger held forever and finds the loop it settles into.

    The walk follows each state's next state. It keeps the gun's own counters (A_GiveInventory, A_TakeInventory and
    A_JumpIfInventory on items other than ammo), because burst and spin-up guns count shots that way. Ammo is always
    loaded: a jump that checks the gun's own magazine or ammo is taken, A_JumpIfNoAmmo is not, and the reload is not
    walked. Every other jump is not taken (no mods, no perks, no powerups, ACS checks false), except A_Jump(256).
    With fire held, A_ReFire goes to Hold (or the state it names), or Fire; reaching Ready goes back to Fire. A state's
    action runs as the state is entered, so a state that refires never waits out its own tics. Shots in the same tic
    (a 6-bullet volley, a bullet plus a rail effect) count as one.

    With held=False the trigger is pressed again at Ready but let go at every A_ReFire (it falls through): that is
    how a charge gun that fires on release (the Gauss Rifle) is fired.

    Options used by tools/automatics/derive_bands.py (the defaults keep this file's own table unchanged):
    start='AltFire' fires the alternate fire instead (A_ReFire then goes to AltHold, else AltFire); inv0 presets the
    gun's own counters (a firing-mode item, or DRLA's synth-fire button items); ready_fires=True makes every
    A_WeaponReady that allows this fire go back to the fire state, as the engine does with the button held (the
    psprite ticks, then CheckWeaponFire runs in the same tic, so it costs no tics).

    Returns (shortest tics between shots in the loop, shots per loop, loop tics, note)."""
    alt = start.lower() == 'altfire'
    owner, i = find_label(actors, a, start)
    if owner is None:
        return None, 0, 0, 'no %s state' % start
    ready_owner, ready_i = find_label(actors, a, 'Ready')
    hold = 'AltHold' if alt else 'Hold'
    block = 'WRF_NOSECONDARY' if alt else 'WRF_NOPRIMARY'
    inv = dict(inv0 or {})
    tics, steps, shot_tics = 0, 0, []
    seen = {}

    def maxamount(item):
        x = actors.get(item)
        v = prop(actors, x, 'inventory.maxamount') if x else None
        return int(v) if v and v.lstrip('-').isdigit() else 1

    def go(label):
        return find_label(actors, a, label)

    while steps < 20000:
        steps += 1
        if owner is ready_owner and i == ready_i:
            owner, i = go(start)
        key = (id(owner), i, tuple(sorted(inv.items())))
        if key in seen:
            t0, n0 = seen[key]
            loop, length = shot_tics[n0:], tics - t0
            if not loop:
                return None, 0, length, 'no shot while fire is held'
            gaps = [y - x for x, y in zip(loop, loop[1:])] + [loop[0] + length - loop[-1]]
            return min(gaps), len(loop), length, 'loops'
        seen[key] = (tics, len(shot_tics))
        if i >= len(owner.states):
            return None, 0, 0, 'ran off the end'
        st = owner.states[i]
        kind = st[0]
        if kind == 'goto':
            o2, j = go(st[1]) if '::' not in st[1] else find_label(actors, owner, st[1])
            if o2 is None:
                return None, 0, 0, 'unknown goto ' + st[1]
            owner, i = o2, (frame_offset(o2, j, st[2]) if st[2] else j)
            continue
        if kind == 'goto_index':
            i = st[1]
            continue
        if kind in ('stop', 'wait', 'fail'):
            return None, 0, 0, kind
        _, t, rest = st
        if debug:
            print(f'  {owner.name}[{i}] tic {tics} {t} {rest[:90]}  inv={inv}')
        if t < 0:
            return None, 0, 0, 'stops (-1 tics)'
        if SHOT.search(rest) and (not shot_tics or shot_tics[-1] != tics):
            shot_tics.append(tics)
        for m in re.finditer(r'\bA_(Give|Take)Inventory\s*\(\s*"(\w+)"\s*(?:,\s*(\d+))?', rest, re.I):
            item = m.group(2).lower()
            if item in ammo:
                continue
            n = int(m.group(3)) if m.group(3) else (1 if m.group(1).lower() == 'give' else 0)
            if m.group(1).lower() == 'give':
                inv[item] = min(inv.get(item, 0) + n, maxamount(item))
            else:
                inv[item] = 0 if n == 0 else max(inv.get(item, 0) - n, 0)
            if inv[item] == 0:
                del inv[item]
        rm = re.search(r'\bA_ReFire\b\s*(?:\(\s*"?([\w.:]*)"?\s*\))?', rest, re.I)
        if rm and held:
            o2, j = go(rm.group(1) or hold)
            owner, i = (o2, j) if o2 is not None else go(start)
            continue
        wm = re.search(r'\bA_WeaponReady\b\s*(?:\(([^)]*)\))?', rest, re.I)
        wf = (wm.group(1) or '').strip() if wm else ''
        if wf.isdigit():  # WRF_NOPRIMARY 4, WRF_NOSECONDARY 8
            wf = block if int(wf) & (8 if alt else 4) else ''
        if wm and held and ready_fires and not re.search(r'WRF_NOFIRE|' + block, wf, re.I):
            owner, i = go(start)
            continue
        tics += t
        jm = re.search(r'\bA_Jump\s*\(\s*(\d+)\s*,\s*("?[\w.:]+"?)', rest, re.I)
        im = re.search(r'\bA_JumpIfInventory\s*\(\s*"(\w+)"\s*,\s*(\d+)\s*,\s*("?[\w.:]+"?)', rest, re.I)
        target = None
        if jm and int(jm.group(1)) >= 256:
            target = jm.group(2)
        elif im:
            item, amount = im.group(1).lower(), int(im.group(2))
            have = inv.get(item, 0)
            if item in ammo:
                taken = amount > 0
            elif amount == 0:
                taken = have > 0 and have >= maxamount(item)
            else:
                taken = have >= amount
            if taken:
                target = im.group(3)
        if target:
            target = target.strip('"')
            if target.isdigit():
                i = frame_offset(owner, i, int(target))
            else:
                owner, i = go(target)
                if owner is None:
                    return None, 0, 0, 'unknown jump ' + target
            continue
        i += 1
    return None, 0, 0, 'too many steps'


def energy_list():
    with open(CATEGORY_FILE, encoding='utf-8') as f:
        text = f.read()
    m = re.search(r'energyGuns\[\]\s*=\s*\{(.*?)\};', text, re.S)
    return {n.lower() for n in re.findall(r'"(\w+)"', strip_comments(m.group(1)))}


def tokens(a):
    return {t.lower() for t in re.findall(r'A_GiveInventory\s*\(\s*"RL(\w+?)TypeWeapon"', a.body, re.I)}


def classify(actors):
    energy = energy_list()
    rows = []
    for key, a in sorted(actors.items()):
        anc = ancestors(actors, a.name)
        if 'weapon' not in anc and 'rlweapon' not in anc:
            continue
        if not a.labels.get('fire') and key in ('rlweapon', 'rlbaseweapon'):
            continue
        if find_label(actors, a, 'Fire')[0] is None or 'fire' not in a.labels:
            continue  # Base classes and items with no Fire state of their own.
        toks = tokens(a)
        ammo = [prop(actors, a, k) for k in ('weapon.ammotype', 'weapon.ammotype1', 'weapon.ammotype2')]
        bases = {stock_base(actors, x) for x in ammo if x}
        melee = ('+', 'meleeweapon') in a.flags or 'melee' in toks
        reason = None
        if melee:
            reason = 'melee'
        elif 'pistol' in toks:
            reason = 'pistol token'
        elif 'RocketAmmo' in bases:
            reason = 'explosive (rocket ammo)'
        elif 'Cell' in bases or key in energy:
            reason = 'energy (cells or self-charging list)'
        elif 'shotgun' in toks:
            reason = 'shotgun token'
        elif not bases & {'Clip', 'Shell'}:
            reason = 'not ballistic (no bullet or shell ammo)'
        if reason:
            rows.append((a, toks, bases, None, 0, '', False, reason))
            continue
        ammo_set = {x.lower() for x in ammo if x}
        gap, shots, length, note = trace_fire(actors, a, ammo_set)
        if shots == 0:
            # It never fires while fire is held, so it needs a press per shot (charge guns fire on release).
            gap, shots, length, note = trace_fire(actors, a, ammo_set, held=False)
            note = 'no shot while held; pressed per shot: ' + note
        semi = shots > 0 and gap >= SEMI_MIN_TICS
        if shots == 0:
            verdict = f'no shot found with fire held ({note})'
        elif not semi:
            verdict = f'automatic ({shots} shots per {length}-tic loop, {gap} tics apart at the closest)'
        else:
            verdict = f'semi-automatic ({gap} tics between shots)'
        cycle = gap
        rifle = semi
        if key in {k.lower() for k in EXCEPTIONS}:
            rifle, why = next(v for k, v in EXCEPTIONS.items() if k.lower() == key)
            verdict += '; exception: ' + why
        rows.append((a, toks, bases, cycle, shots, note, rifle, verdict))
    return rows


def write_table(rows, path):
    lines = ['| Gun | File | Ammo | Tokens | Closest shots (tics) | Shots per loop | Trace | Rifle | Why |', '|---|---|---|---|---:|---:|---|---|---|']
    for a, toks, bases, cycle, shots, note, rifle, verdict in rows:
        if verdict in ('melee', 'pistol token', 'explosive (rocket ammo)', 'energy (cells or self-charging list)',
                       'shotgun token') and not rifle:
            continue
        lines.append(f'| {a.name} | {a.path} | {"/".join(sorted(b for b in bases if b)) or "-"} | '
                     f'{", ".join(sorted(toks)) or "-"} | {cycle if cycle is not None else "-"} | {shots} | {note} | '
                     f'{"yes" if rifle else "no"} | {verdict} |')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')


def generated_block(names):
    body = ''.join(f'\t\t\t"{n}",\n' for n in names)
    return f'\t\t// GENERATED by tools/rifle_tag/derive_rifles.py --write. Do not edit by hand.\n{body}\t\t\t// END GENERATED\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--drla', default=DEFAULT_DRLA)
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--table')
    a = ap.parse_args()
    actors = load_actors(a.drla)
    rows = classify(actors)
    rifles = [r[0].name for r in rows if r[6]]
    for r in rows:
        if r[6]:
            print('RIFLE', r[0].name, '-', r[7])
    print(f'{len(rifles)} rifles from {len(rows)} DRLA weapons')
    if a.table:
        write_table(rows, a.table)
    with open(TAG_FILE, encoding='utf-8') as f:
        text = f.read()
    pat = re.compile(r'\t\t// GENERATED by.*?// END GENERATED\n', re.S)
    new = generated_block(rifles)
    if a.write:
        with open(TAG_FILE, 'w', encoding='utf-8', newline='\n') as f:
            f.write(pat.sub(lambda _: new, text))
        print('wrote', TAG_FILE)
    if a.check:
        m = pat.search(text)
        ok = m and m.group(0) == new
        print('CHECK', 'PASS' if ok else 'FAIL: DoomerfallRifleTag.zs differs from the rule; run --write')
        return 0 if ok else 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
